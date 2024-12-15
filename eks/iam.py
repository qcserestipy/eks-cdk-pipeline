from aws_cdk import (
    Stack,
    aws_iam as iam,
)
from constructs import Construct
from typing import Any, Dict


class EksIamStack(Stack):
    """Creates IAM resources for the EKS cluster.

    This stack defines IAM policies necessary for the EKS cluster to function,
    including cross-account KMS key usage policies.

    Attributes:
        policy_kms_cross_account_usage (iam.ManagedPolicy): Managed policy allowing cross-account KMS key usage.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        config: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Initializes the EksIamStack.

        Args:
            scope (Construct): The scope in which this construct is defined.
            id (str): The scoped construct ID.
            config (dict): Configuration parameters, including account IDs.
            **kwargs (Any): Additional keyword arguments.
        """
        super().__init__(scope, id, **kwargs)

        self.policy_kms_cross_account_usage = iam.ManagedPolicy(
            self,
            "EksKmsCrossAccountUsagePolicy",
            path="/eks/",
            managed_policy_name="EksKmsCrossAccountUsagePolicy",
            document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "kms:CreateGrant",
                            "kms:Decrypt",
                            "kms:DescribeKey",
                            "kms:GenerateDataKeyWithoutPlainText",
                            "kms:ReEncrypt*"
                        ],
                        resources=[f"arn:aws:kms:*:{config['accounts']['tooling']['id']}:key/*"],
                    )
                ]
            ),
        )
