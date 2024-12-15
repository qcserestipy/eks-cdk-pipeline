from aws_cdk import (
    Stack,
    aws_eks as eks,
    aws_ssm as ssm
)
from constructs import Construct
from typing import Any


class EksSSMParametersStack(Stack):
    """Stores EKS cluster parameters in AWS SSM Parameter Store.

    This stack creates SSM parameters for various EKS cluster properties, making them accessible
    to other stacks or services that need to reference the cluster details.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        cluster: eks.Cluster,
        **kwargs: Any
    ) -> None:
        """Initializes the EksSSMParametersStack.

        Args:
            scope (Construct): The scope in which this construct is defined.
            id (str): The scoped construct ID.
            cluster (eks.Cluster): The EKS cluster whose parameters are to be stored.
            **kwargs (Any): Additional keyword arguments.
        """
        super().__init__(scope, id, **kwargs)

        # Extract cluster details
        cluster_name = cluster.cluster_name
        cluster_arn = cluster.cluster_arn
        # cluster_certificate_authority_data = cluster.cluster_certificate_authority_data  # Uncomment if needed
        cluster_endpoint = cluster.cluster_endpoint
        security_groups = cluster.cluster_security_group_id

        # Create SSM Parameters for each of the values

        ssm.StringParameter(
            self,
            "EksClusterNameParam",
            parameter_name="/eks/clusterName",
            string_value=cluster_name
        )

        ssm.StringParameter(
            self,
            "EksClusterArnParam",
            parameter_name="/eks/clusterArn",
            string_value=cluster_arn
        )

        # Uncomment if needed
        # ssm.StringParameter(
        #     self,
        #     "EksClusterCertAuthDataParam",
        #     parameter_name="/eks/clusterCertificateAuthorityData",
        #     string_value=cluster_certificate_authority_data
        # )

        ssm.StringParameter(
            self,
            "EksClusterEndpointParam",
            parameter_name="/eks/clusterEndpoint",
            string_value=cluster_endpoint
        )

        ssm.StringParameter(
            self,
            "EksClusterSecurityGroupsParam",
            parameter_name="/eks/clusterSecurityGroup",
            string_value=security_groups
        )

        ssm.StringParameter(
            self,
            "EksClusterOIDCProviderArn",
            parameter_name="/eks/oidc/provider_arn",
            string_value=cluster.open_id_connect_provider.open_id_connect_provider_arn
        )

        ssm.StringParameter(
            self,
            "EksClusterKubectlLambdaRoleArn",
            parameter_name="/eks/kubectl/lambda/role_arn",
            string_value=cluster.kubectl_lambda_role.role_arn
        )

        ssm.StringParameter(
            self,
            "EksClusterKubectlRoleArn",
            parameter_name="/eks/kubectl/role_arn",
            string_value=cluster.kubectl_role.role_arn
        )

        ssm.StringParameter(
            self,
            "EksClusterKubectlSgId",
            parameter_name="/eks/kubectl/sg_id",
            string_value=cluster.kubectl_security_group.security_group_id
        )
