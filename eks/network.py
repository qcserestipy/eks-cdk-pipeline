from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ssm as ssm,
    Tags,
    CfnOutput,
)
from constructs import Construct
from typing import Any, Dict


class EksNetworkStack(Stack):
    """Creates the network infrastructure for the EKS cluster.

    This stack sets up a VPC with public and private subnets, and tags them appropriately for EKS and ELB usage.
    It also stores the VPC ID in SSM Parameter Store.

    Attributes:
        vpc (ec2.Vpc): The VPC created for the EKS cluster.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        config: Dict[str, Any],
        phase: str,
        **kwargs: Any
    ) -> None:
        """Initializes the EksNetworkStack.

        Args:
            scope (Construct): The scope in which this construct is defined.
            id (str): The scoped construct ID.
            config (dict): Configuration parameters, including cluster name.
            phase (str): Deployment phase (e.g., 'dev', 'prod').
            **kwargs (Any): Additional keyword arguments.
        """
        super().__init__(scope, id, **kwargs)

        env = kwargs.get("env")
        region = env.region
        account = env.account

        # Create a VPC with public and private subnets in two availability zones
        self.vpc = ec2.Vpc(
            self,
            "EksVpc",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PUBLIC,
                    name="PublicSubnet",
                    cidr_mask=19
                ),
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    name="PrivateSubnet",
                    cidr_mask=19
                )
            ]
        )

        cluster_name = config['eks']['cluster_name']
        # Tag subnets for the EKS cluster and ELB
        Tags.of(self.vpc).add("Name", f"EksClusterStack/EksCluster/DefaultVpc")

        for subnet in self.vpc.public_subnets:
            Tags.of(subnet).add("Name", f"EksClusterStack/EksCluster/DefaultVpc/PublicSubnet")
            Tags.of(subnet).add(f"kubernetes.io/cluster/{cluster_name}", "shared")
            Tags.of(subnet).add("kubernetes.io/role/elb", "1")

        for subnet in self.vpc.private_subnets:
            Tags.of(subnet).add("Name", f"EksClusterStack/EksCluster/DefaultVpc/PrivateSubnet")
            Tags.of(subnet).add(f"kubernetes.io/cluster/{cluster_name}", "shared")
            Tags.of(subnet).add("kubernetes.io/role/internal-elb", "1")

        ssm.StringParameter(
            self,
            "EksVpcId",
            parameter_name="/eks/vpc_id",
            string_value=self.vpc.vpc_id
        )

        # Output the VPC ID
        CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
