from aws_cdk import (
    Stage,
)
from constructs import Construct
from eks.keypairs import KeypairStack
from eks.network import EksNetworkStack
from eks.iam import EksIamStack
from eks.cluster import EksClusterStack
from eks.clusterparams import EksSSMParametersStack
from typing import Any

class KeypairDeploymentStage(Stage):
    """Deploys the Keypair Stack in a specified stage of the pipeline.

    Attributes:
        keypair_stack (KeypairStack): The stack that creates a keypair for EC2 instances.
    """

    def __init__(
            self,
            scope: Construct,
            id: str,
            config: dict,
            phase: str,
            **kwargs: Any
        ) -> None:
        """Initializes the KeypairDeploymentStage.

        Args:
            scope (Construct): The scope in which this construct is defined.
            id (str): The scoped construct ID.
            config (dict): Configuration parameters for the deployment.
            phase (str): The deployment phase (e.g., 'dev', 'prod').
            **kwargs (Any): Additional keyword arguments.
        """
        super().__init__(scope, id, **kwargs)
        env = kwargs.get("env")
        self.keypair_stack = KeypairStack(
            self,
            "KeypairStack",
            description="Keypair for EC2 instances",
            config=config,
            env=env,
        )

class EksClusterDeploymentStage(Stage):
    """Deploys the EKS Cluster and its dependencies in a specified stage of the pipeline.

    Attributes:
        eks_network_stack (EksNetworkStack): The stack that sets up the network infrastructure for EKS.
        eks_iam_stack (EksIamStack): The stack that sets up IAM roles and policies for EKS.
        eks_cluster_stack (EksClusterStack): The stack that creates the EKS cluster.
        eks_params (EksSSMParametersStack): The stack that stores EKS cluster parameters in SSM.
    """

    def __init__(
            self,
            scope: Construct,
            id: str,
            config: dict,
            phase: str,
            **kwargs) -> None:
        """Initializes the EksClusterDeploymentStage.

        Args:
            scope (Construct): The scope in which this construct is defined.
            id (str): The scoped construct ID.
            config (dict): Configuration parameters for the deployment.
            phase (str): The deployment phase (e.g., 'dev', 'prod').
            **kwargs (Any): Additional keyword arguments.
        """
        super().__init__(scope, id, **kwargs)
        env = kwargs.get("env")

        self.eks_network_stack = EksNetworkStack(
            self,
            "EksNetworkStack",
            config=config,
            phase=phase,
            description="EKS Network Stack",
            env=env,
        )

        self.eks_iam_stack = EksIamStack(
            self,
            "EksIamStack",
            config=config,
            description="EKS IAM Stack",
            env=env,
        )

        self.eks_cluster_stack = EksClusterStack(
            self,
            "EksClusterStack",
            policy_kms_cross_account_usage=self.eks_iam_stack.policy_kms_cross_account_usage,
            network_stack=self.eks_network_stack,
            config=config,
            phase=phase,
            description="EKS Cluster Stack",
            env=env,
        )
        self.eks_cluster_stack.add_dependency(self.eks_network_stack)
        self.eks_cluster_stack.add_dependency(self.eks_iam_stack)

        self.eks_params = EksSSMParametersStack(
            self,
            "EksSSMParametersStack",
            cluster=self.eks_cluster_stack.cluster
        )
        self.eks_params.add_dependency(self.eks_cluster_stack)