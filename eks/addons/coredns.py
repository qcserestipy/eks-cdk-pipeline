from aws_cdk import (
    aws_eks as eks,
)
from constructs import Construct
import json
from typing import Any
class EksCoreDnsAddOn(Construct):
    """Deploys the CoreDNS add-on to an EKS cluster.

    This construct configures and deploys the CoreDNS add-on to the specified EKS cluster,
    customizing resource requests, limits, replica count, node affinity, and tolerations.

    Attributes:
        cluster (eks.Cluster): The EKS cluster where the CoreDNS add-on is deployed.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        cluster: eks.Cluster,
        **kwargs: Any
    ) -> None:
        """Initializes the EksCoreDnsAddOn.

        Args:
            scope (Construct): The scope in which this construct is defined.
            id (str): The scoped construct ID.
            cluster (eks.Cluster): The EKS cluster to deploy the CoreDNS add-on to.
            **kwargs (Any): Additional keyword arguments.
        """
        super().__init__(scope, id, **kwargs)
        coredns_addon_config = {
            "resources": {
                "requests": {
                    "cpu": "100m",
                    "memory": "70Mi"
                },
                "limits": {
                    "cpu": "100m",
                    "memory": "170Mi"
                }
            },
            "replicaCount": 1,
            "affinity": {
                "nodeAffinity": {
                    "requiredDuringSchedulingIgnoredDuringExecution": {
                        "nodeSelectorTerms": [
                            {
                                "matchExpressions": [
                                    {
                                        "key": "purpose",
                                        "operator": "In",
                                        "values": [
                                            "admin"
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
            "tolerations": [
                {
                    "key": "purpose",
                    "operator": "Equal",
                    "value": "admin",
                    "effect": "NoSchedule"
                }
            ]
        }
        # Create CoreDNS add-on
        _ = eks.CfnAddon(
            self, "EksCoreDnsAddOn",
            cluster_name=cluster.cluster_name,
            addon_name="coredns",
            addon_version="v1.11.3-eksbuild.2",
            resolve_conflicts="OVERWRITE",
            preserve_on_delete=False,
            configuration_values=json.dumps(coredns_addon_config),
        )