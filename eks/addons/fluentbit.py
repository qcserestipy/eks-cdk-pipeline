from aws_cdk import (
    aws_iam as iam,
    aws_eks as eks,
)
from constructs import Construct
from ..helm import EksHelmDeployWithPodIdentity 

class EksAwsFluentBitLogger(Construct):
    def __init__(
        self,
        scope: Construct, 
        id: str,
        cluster: eks.Cluster,
        account: str,
        region: str,
        **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self.serviceaccountname = "aws-for-fluent-bit"
        self.release = "aws-for-fluent-bit"
        self.namespace = "kube-system"
        self.version = "0.1.34"
        self.repository = "https://aws.github.io/eks-charts"

        self.helm_deploy = EksHelmDeployWithPodIdentity(
            self,
            "EksAwsFluentBitLogger",
            cluster=cluster,
            chart="aws-for-fluent-bit",
            release=self.release,
            repository=self.repository,
            namespace=self.namespace,
            version=self.version,
            serviceaccountname=self.serviceaccountname,
            role_policy_statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "logs:PutLogEvents",
                        "logs:DescribeLogStreams",
                        "logs:DescribeLogGroups",
                        "logs:CreateLogStream",
                        "logs:CreateLogGroup",
                    ],
                    resources=["*"]
                )
            ],
            values = {
                "cloudWatch": {
                    "enabled": True,
                    "region": region,
                    "logGroupName": "/eks/application-log/",
                    "logStreamPrefix": "log-",
                },
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
                ],
                "resources": {
                    "limits": {
                        "cpu": "200m",
                        "memory": "256Mi"
                    },
                    "requests": {
                        "cpu": "50m",
                        "memory": "50Mi"
                    }
                }
            }
        )