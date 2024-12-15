from aws_cdk import (
    aws_eks as eks,
)
import json
from constructs import Construct
from typing import Any

class EksPodIdentityAddOn(Construct):
    """Enables IAM Roles for Service Accounts (IRSA) on an EKS cluster.

    This construct deploys the EKS Pod Identity webhook as an add-on,
    allowing pods to assume IAM roles via service accounts.

    Attributes:
        cluster (eks.Cluster): The EKS cluster where the Pod Identity add-on is deployed.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        cluster: eks.Cluster,
        **kwargs: Any
    ) -> None:
        """Initializes the EksPodIdentityAddOn.

        Args:
            scope (Construct): The scope in which this construct is defined.
            id (str): The scoped construct ID.
            cluster (eks.Cluster): The EKS cluster to enable Pod Identity on.
            **kwargs (Any): Additional keyword arguments.
        """
        super().__init__(scope, id, **kwargs)

        pod_id_config = {
            "resources": {
                "limits": {
                    "cpu": "200m",
                    "memory": "256Mi"
                },
                "requests": {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            },
        }
        # Enable Pod Identity agent add-on
        _ = eks.CfnAddon(
            self, "EksPodIdentityAddon",
            cluster_name=cluster.cluster_name,
            addon_name="eks-pod-identity-agent",
            addon_version="v1.3.4-eksbuild.1",
            resolve_conflicts="OVERWRITE",
            preserve_on_delete=False,
            configuration_values=json.dumps(pod_id_config)
        )