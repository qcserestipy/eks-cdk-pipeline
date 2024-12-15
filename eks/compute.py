from aws_cdk import (
    aws_iam as iam,
    aws_eks as eks,
    aws_ec2 as ec2,
)
from constructs import Construct
from typing import Any

class EksNodeGroups(Construct):
    """Creates managed node groups for the EKS cluster.

    This construct sets up both spot and on-demand node groups with specific configurations
    for instance types, capacity types, labels, and taints.

    Attributes:
        spot_ng_name (str): Name of the spot node group.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        cluster: eks.Cluster,
        node_role: iam.Role,
        private_subnet_selection: ec2.SubnetSelection,
        config: dict,
        **kwargs: Any
    ) -> None:
        """Initializes the EksNodeGroups.

        Args:
            scope (Construct): The scope in which this construct is defined.
            id (str): The scoped construct ID.
            cluster (eks.Cluster): The EKS cluster to add node groups to.
            node_role (iam.Role): IAM role for the EKS worker nodes.
            private_subnet_selection (ec2.SubnetSelection): Subnet selection for node groups.
            config (dict): Configuration parameters for the node groups.
            **kwargs (Any): Additional keyword arguments.
        """
        super().__init__(scope, id, **kwargs)

        # Create spot node group
        spot_ng = eks.Nodegroup(
            self,
            "compute-ng-spot",
            nodegroup_name="computengspot",
            ami_type=eks.NodegroupAmiType.AL2_ARM_64,
            cluster=cluster,
            subnets=private_subnet_selection,
            node_role=node_role,
            capacity_type=eks.CapacityType.SPOT,
            labels={
                "purpose": "general"
            },
            instance_types=[
                ec2.InstanceType("t4g.small"),
            ],
            max_size=1,
            min_size=1,
        )
        self.spot_ng_name = spot_ng.nodegroup_name

        # Create on-demand node group with taints
        # ondemand_ng = eks.Nodegroup(
        #     self,
        #     "compute-ng-ond",
        #     nodegroup_name="computengond",
        #     ami_type=eks.NodegroupAmiType.AL2_ARM_64,
        #     cluster=cluster,
        #     subnets=private_subnet_selection,
        #     node_role=node_role,
        #     capacity_type=eks.CapacityType.SPOT,
        #     labels={
        #         "purpose": "admin"
        #     },
        #     taints=[
        #         eks.TaintSpec(
        #             effect=eks.TaintEffect.NO_SCHEDULE,
        #             key="purpose",
        #             value="admin"
        #         )
        #     ],
        #     instance_types=[
        #         ec2.InstanceType("t4g.medium"),
        #     ],
        #     max_size=1,
        #     min_size=1,
        # )
