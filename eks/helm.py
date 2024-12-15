from aws_cdk import (
    aws_iam as iam,
    aws_eks as eks,
)
from constructs import Construct
from typing import Any, Dict, List


class EksHelmDeployWithPodIdentity(Construct):
    """Deploys a Helm chart to an EKS cluster with IAM Roles for Service Accounts (IRSA).

    This construct automates the deployment of a Helm chart to an EKS cluster and sets up
    IAM roles for service accounts to allow pods to assume AWS IAM roles.

    Attributes:
        cluster (eks.Cluster): The EKS cluster where the Helm chart is deployed.
        chart (str): The name of the Helm chart.
        release (str): The release name for the Helm chart.
        repository (str): The Helm chart repository URL.
        namespace (str): The Kubernetes namespace where the chart is deployed.
        serviceaccountname (str): The name of the Kubernetes service account.
        role_policy_statements (List[iam.PolicyStatement]): IAM policy statements attached to the role.
        values (Dict[str, Any]): Values passed to the Helm chart.
        version (str): Version of the Helm chart.
        role (iam.Role): IAM role associated with the service account.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        cluster: eks.Cluster,
        chart: str,
        release: str,
        repository: str,
        namespace: str,
        values: Dict[str, Any],
        version: str = None,
        serviceaccountname: str = "helm-deploy-serviceaccount",
        role_policy_statements: List[iam.PolicyStatement] = [],
        **kwargs: Any
    ) -> None:
        """Initializes the EksHelmDeployWithPodIdentity construct.

        Args:
            scope (Construct): The scope in which this construct is defined.
            id (str): The scoped construct ID.
            cluster (eks.Cluster): The EKS cluster to deploy to.
            chart (str): The name of the Helm chart.
            release (str): The release name for the Helm chart.
            repository (str): The Helm chart repository URL.
            namespace (str): The Kubernetes namespace where the chart is deployed.
            values (Dict[str, Any]): Values passed to the Helm chart.
            version (str, optional): Version of the Helm chart.
            serviceaccountname (str, optional): Name of the Kubernetes service account. Defaults to "helm-deploy-serviceaccount".
            role_policy_statements (List[iam.PolicyStatement], optional): IAM policy statements attached to the role.
            **kwargs (Any): Additional keyword arguments.
        """
        super().__init__(scope, id, **kwargs)

        self.cluster = cluster
        self.chart = chart
        self.release = release
        self.repository = repository
        self.namespace = namespace
        self.serviceaccountname = serviceaccountname
        self.role_policy_statements = role_policy_statements
        self.values = values
        self.version = version

        # A role is required for the pod to assume
        self.role = self.create_role(self.role_policy_statements)
        # The Helm deploy construct adds the service account block itself
        self.add_service_account_to_values()
        self.create_helm_chart()

    def create_role(self, role_policy_statements: List[iam.PolicyStatement] = []) -> iam.Role:
        """Creates an IAM role for the service account with specified policy statements.

        Args:
            role_policy_statements (List[iam.PolicyStatement], optional): IAM policy statements to attach to the role.

        Returns:
            iam.Role: The IAM role created.
        """
        # IAM Role
        role = iam.Role(
            self,
            f"{self.release}-Role",
            assumed_by=iam.ServicePrincipal("pods.eks.amazonaws.com"),
            role_name=f"{self.release}-Role"
        )
        # Override the trust policy
        role.assume_role_policy.add_statements(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("pods.eks.amazonaws.com")],
                actions=["sts:AssumeRole", "sts:TagSession"]
            )
        )
        # Add additional statements
        for statement in role_policy_statements:
            role.add_to_policy(statement)
        # Pod Identity Association
        _ = eks.CfnPodIdentityAssociation(
            self,
            f"{self.release}-PodIdentityAssociation",
            cluster_name=self.cluster.cluster_name,
            namespace=self.namespace,
            role_arn=role.role_arn,
            service_account=self.serviceaccountname,
        )
        return role

    def add_service_account_to_values(self) -> None:
        """Adds the service account configuration to the Helm chart values."""
        service_account = self.values.setdefault('serviceAccount', {})
        service_account.setdefault('name', self.serviceaccountname)
        service_account.setdefault('create', True)
        annotations = service_account.setdefault('annotations', {})
        annotations['eks.amazonaws.com/role-arn'] = self.role.role_arn

    def create_helm_chart(self) -> None:
        """Deploys the Helm chart to the EKS cluster."""
        self.cluster.add_helm_chart(
            id=f"{self.release}-Chart",
            release=self.release,
            chart=self.chart,
            repository=self.repository,
            namespace=self.namespace,
            create_namespace=True,
            values=self.values,
            version=self.version
        )
