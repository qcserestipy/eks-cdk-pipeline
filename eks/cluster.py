from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_eks as eks,
)
from aws_cdk.aws_ec2 import SubnetSelection
from constructs import Construct
from aws_cdk.lambda_layer_kubectl_v31 import KubectlV31Layer
from typing import Any
from .karpenter import EksKarpenter
from .addons.coredns import EksCoreDnsAddOn
from .addons.ebscsi import EksEbsCSIDriverAddOn
from .addons.albcontroller import EksAwsAlbControllerAddOn
from .addons.podidentity import EksPodIdentityAddOn
from .clusterautoscaler import EksAwsClusterAutoscaler
from .bastion import EksBastionHost
from .compute import EksNodeGroups


class EksClusterStack(Stack):
    """Creates an EKS Cluster along with its associated resources.

    This stack sets up the EKS cluster, node groups, and various add-ons required
    for the cluster's operation.

    Attributes:
        config (dict): Configuration parameters for the cluster.
        phase (str): Deployment phase (e.g., 'dev', 'prod').
        cluster (eks.Cluster): The EKS cluster instance.
        node_role (iam.Role): IAM role for the EKS worker nodes.
        _region (str): AWS region where the cluster is deployed.
        _account (str): AWS account ID where the cluster is deployed.
        eks_coredns_addon (EksCoreDnsAddOn): The CoreDNS add-on construct.
        eks_pod_identity_addon (EksPodIdentityAddOn): The Pod Identity add-on construct.
        eks_alb_controller_addon (EksAwsAlbControllerAddOn): The AWS ALB Controller add-on construct.
        eks_bastion_host (EksBastionHost): The Bastion Host construct.
        eks_node_groups (EksNodeGroups): The Node Groups construct.
        eks_karpenter (EksKarpenter): The Karpenter auto-scaling construct.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        policy_kms_cross_account_usage: iam.ManagedPolicy,
        network_stack: Stack,
        config: dict,
        phase: str,
        **kwargs: Any
    ) -> None:
        """Initializes the EksClusterStack.

        Args:
            scope (Construct): The scope in which this construct is defined.
            id (str): The scoped construct ID.
            policy_kms_cross_account_usage (iam.ManagedPolicy): Managed policy for cross-account KMS key usage.
            network_stack (Stack): The network stack providing VPC and subnet information.
            config (dict): Configuration parameters for the cluster.
            phase (str): Deployment phase (e.g., 'dev', 'prod').
            **kwargs (Any): Additional keyword arguments.
        """
        super().__init__(scope, id, **kwargs)

        self.config = config
        self.phase = phase
        env = kwargs.get("env")
        self._region = env.region
        self._account = env.account

        # Create the EKS cluster
        self.cluster = eks.Cluster(
            self,
            id=config['eks']['cluster_name'],
            cluster_name=config['eks']['cluster_name'],
            version=eks.KubernetesVersion.V1_31,
            vpc=network_stack.vpc,
            vpc_subnets=[SubnetSelection(subnets=network_stack.vpc.private_subnets)],
            role=self.create_controller_role(),
            kubectl_layer=KubectlV31Layer(self, "kubectl"),
            default_capacity=0,
            endpoint_access=eks.EndpointAccess.PRIVATE
        )

        # Add CoreDNS add-on
        self.eks_coredns_addon = EksCoreDnsAddOn(
            self,
            "EksCoreDnsAddOn",
            cluster=self.cluster,
        )

        # Add Pod Identity add-on
        self.eks_pod_identity_addon = EksPodIdentityAddOn(
            self,
            "EksPodIdentityAddOn",
            cluster=self.cluster,
        )

        # Note: Fluent Bit does not currently support EKS Pod identities
        # See https://github.com/aws/aws-for-fluent-bit/issues/784
        # self.eks_fluent_bit_logger = EksAwsFluentBitLogger(
        #     self,
        #     "EksAwsFluentBitLogger",
        #     cluster=self.cluster,
        #     region=self._region,
        #     account=self._account,
        # )

        # Add AWS Load Balancer Controller
        self.eks_alb_controller_addon = EksAwsAlbControllerAddOn(
            self,
            "EksAwsAlbControllerAddOn",
            cluster=self.cluster,
            vpc=network_stack.vpc,
            account=self._account,
            region=self._region
        )

        # Create the IAM role for the EKS nodes
        self.node_role = self.create_eks_node_role(
            policy_kms_cross_account_usage,
            self.eks_alb_controller_addon.alb_policy_list()
        )

        # Create Node Groups
        self.eks_node_groups = EksNodeGroups(
            self,
            "EksNodeGroups",
            cluster=self.cluster,
            node_role=self.node_role,
            private_subnet_selection=SubnetSelection(subnets=network_stack.vpc.private_subnets),
            config=config,
        )

        # Create a Bastion Host
        self.eks_bastion_host = EksBastionHost(
            self,
            "EksBastionHost",
            cluster=self.cluster,
            vpc=network_stack.vpc,
            config=config,
        )

        # Add EBS CSI Driver if needed
        # self.eks_ebs_csi_driver_addon = EksEbsCSIDriverAddOn(
        #     self,
        #     "EksEbsCSIDriverAddOn",
        #     cluster=self.cluster,
        # )

        # Deploy the Cluster Autoscaler if needed
        # self.eks_autoscaler = EksAwsClusterAutoscaler(
        #     self,
        #     "EksAwsClusterAutoscaler",
        #     cluster=self.cluster,
        #     region=self._region,
        #     account=self._account,
        # )

        # Deploy Karpenter for auto-scaling
        self.eks_karpenter = EksKarpenter(
            self,
            "EksKarpenterDeployConstruct",
            cluster=self.cluster,
            account=self._account,
            region=self._region,
        )

        self.eks_karpenter.node.add_dependency(self.eks_node_groups)
        self.eks_karpenter.node.add_dependency(self.eks_alb_controller_addon)


    def create_eks_node_role(self, policy_kms_cross_account_usage, alb_policies) -> iam.Role:
        """Creates an IAM role for EKS worker nodes.

        This role is attached to the Auto Scaling Group instances and needs to be defined in
        the same stack as the cluster that uses it to avoid circular dependencies.

        Args:
            policy_kms_cross_account_usage (iam.ManagedPolicy): Managed policy for cross-account KMS key usage.
            alb_policies (list): List of IAM policy statements required by the AWS Load Balancer Controller.

        Returns:
            iam.Role: The IAM role for EKS worker nodes.
        """
        eks_node_role = iam.Role(
            self, "EKSWorkerNodeRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ec2.amazonaws.com")
            ),
            managed_policies=[
                policy_kms_cross_account_usage,
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryReadOnly"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKS_CNI_Policy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSWorkerNodePolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchAgentServerPolicy"),
            ]
        )
        # Attach policies for ELB to node role
        for statement in alb_policies:
            eks_node_role.add_to_principal_policy(statement)
        return eks_node_role

    def create_controller_role(self) -> iam.Role:
        """Creates an IAM role for the EKS control plane.

        Returns:
            iam.Role: The IAM role for the EKS cluster control plane.
        """
        return iam.Role(
            self, "EksClusterRole",
            assumed_by=iam.ServicePrincipal("eks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSClusterPolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSServicePolicy"),
            ]
        )
