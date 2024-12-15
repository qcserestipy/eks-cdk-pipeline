from aws_cdk import (
    aws_ec2 as ec2,
    aws_eks as eks,
    aws_iam as iam,
    CfnOutput
)
from constructs import Construct
from typing import Any

class EksBastionHost(Construct):
    """Creates a bastion host for accessing the EKS cluster.

    This construct sets up an EC2 instance as a bastion host with necessary configurations
    to manage the EKS cluster securely.

    Attributes:
        role (iam.Role): IAM role assigned to the bastion host.
        security_group (ec2.SecurityGroup): Security group for the bastion host.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        cluster: eks.Cluster,
        vpc: ec2.Vpc,
        config: dict,
        **kwargs: Any
    ) -> None:
        """Initializes the EksBastionHost.

        Args:
            scope (Construct): The scope in which this construct is defined.
            id (str): The scoped construct ID.
            cluster (eks.Cluster): The EKS cluster to manage.
            vpc (ec2.Vpc): The VPC where the bastion host is deployed.
            config (dict): Configuration parameters, including key name for SSH access.
            **kwargs (Any): Additional keyword arguments.
        """
        super().__init__(scope, id, **kwargs)

        self.role = self.create_role()
        cluster.aws_auth.add_masters_role(self.role)
        self.security_group = self.create_sg(vpc, cluster.cluster_security_group)
        self.create_host(vpc, self.security_group, self.role, config["admin"]["key_name"])

    def create_role(self) -> iam.Role:
        """Creates an IAM role for the bastion host.

        Returns:
            iam.Role: The IAM role assigned to the bastion host.
        """
        return iam.Role(
            self, "EksBastionRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ec2.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ReadOnlyAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSClusterPolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSServicePolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSWorkerNodePolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSVPCResourceController"),
            ]
        )

    def create_sg(self, vpc, cluster_sg) -> ec2.SecurityGroup:
        """Creates a security group for the bastion host.

        Args:
            vpc (ec2.Vpc): The VPC where the bastion host is deployed.
            cluster_sg (ec2.SecurityGroup): Security group of the EKS cluster.

        Returns:
            ec2.SecurityGroup: The security group for the bastion host.
        """
        bastion_sg = ec2.SecurityGroup(
            self, "EksBastionSecurityGroup",
            vpc=vpc,
            description="Security group for bastion host",
            allow_all_outbound=True
        )
        # Allow traffic from the bastion host to the EKS cluster API server
        cluster_sg.add_ingress_rule(
            peer=bastion_sg,
            connection=ec2.Port.tcp(443),
            description="Allow access from bastion host to EKS cluster API server"
        )
        return bastion_sg

    def create_host(self, vpc, bastion_sg, bastion_role, key_name) -> ec2.Instance:
        """Creates the EC2 instance serving as the bastion host.

        Args:
            vpc (ec2.Vpc): The VPC where the bastion host is deployed.
            bastion_sg (ec2.SecurityGroup): Security group for the bastion host.
            bastion_role (iam.Role): IAM role assigned to the bastion host.
            key_name (str): Name of the EC2 key pair for SSH access.
        """
        # Create the EC2 instance (Bastion Host)
        bastion_instance = ec2.Instance(
            self, "EksBastionInstance",
            instance_type=ec2.InstanceType("t4g.nano"),
            machine_image=ec2.AmazonLinuxImage(
                generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
                cpu_type=ec2.AmazonLinuxCpuType.ARM_64
            ),
            vpc=vpc,
            role=bastion_role,
            security_group=bastion_sg,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            key_pair=ec2.KeyPair.from_key_pair_attributes(
                self, "EksBastionKeyPair",
                key_pair_name=key_name,
                type=ec2.KeyPairType.RSA
            )
        )

        # Add user data to install necessary tools
        bastion_instance.add_user_data(
            "#!/bin/bash",
            "yum update -y",
            "yum install -y jq curl git",
            "curl https://s3.us-west-2.amazonaws.com/amazon-eks/1.29.3/2024-04-19/bin/linux/arm64/kubectl -o /bin/kubectl",
            "chmod +x /bin/kubectl",
            "/bin/kubectl completion bash > /etc/bash_completion.d/kubectl",
            "curl -sSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash",
            "yum install -y amazon-ssm-agent",
            "systemctl enable amazon-ssm-agent",
            "systemctl start amazon-ssm-agent",
            "yum remove awscli",
            "curl https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip -o awscliv2.zip",
            "unzip awscliv2.zip",
            "./aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli --update",
            "echo 'export PATH=/usr/local/bin:$PATH' >> /home/ec2-user/.bashrc",
            "echo 'export PATH=\"${KREW_ROOT:-$HOME/.krew}/bin:$PATH\"' >> /home/ec2-user/.bashrc",
            "echo 'alias kns=\"kubectl ns\"' >> /home/ec2-user/.bashrc",
            "echo 'alias kctx=\"kubectl ctx\"' >> /home/ec2-user/.bashrc",
            "echo 'alias k=\"kubectl\"' >> /home/ec2-user/.bashrc",
            "echo 'source <(kubectl completion bash)' >> /home/ec2-user/.bashrc",
            "echo 'complete -F __start_kubectl k' >> /home/ec2-user/.bashrc",
        )

        CfnOutput(self, "BastionInstancePublicIp", value=bastion_instance.instance_public_ip)