from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
)
from constructs import Construct
from typing import Any, Dict


class KeypairStack(Stack):
    """Creates an EC2 Key Pair resource.

    This stack creates an AWS EC2 Key Pair that can be used to access EC2 instances securely.

    Attributes:
        admin_key_pair (ec2.CfnKeyPair): The CloudFormation Key Pair resource.
    """

    def __init__(
            self, 
            scope: Construct, 
            id: str, 
            config: Dict[str, Any], 
            **kwargs: Any
        ) -> None:
        """Initializes the KeypairStack.

        Args:
            scope (Construct): The scope in which this construct is defined.
            id (str): The scoped construct ID.
            config (dict): Configuration parameters containing key pair details.
            **kwargs (Any): Additional keyword arguments.
        """
        super().__init__(scope, id, **kwargs)
        self.admin_key_pair = ec2.CfnKeyPair(
            self,
            "AdminKeyPair",
            key_name=config["admin"]["key_name"],
            public_key_material=config["admin"]["key_material"],
        )
