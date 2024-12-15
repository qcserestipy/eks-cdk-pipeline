from aws_cdk import (
    aws_eks as eks,
    aws_iam as iam,
)
from constructs import Construct

class EksAwsClusterAutoscaler(Construct):
    def __init__(
        self,
        scope: Construct, 
        id: str,
        cluster: eks.Cluster,
        region: str,
        account: str,
        **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self.role = self.create_role(region, account)

        self.cfn_pod_identity_association = eks.CfnPodIdentityAssociation(self, "EksAutoScalerPodIdentityAssociation",
            cluster_name=cluster.cluster_name,
            namespace="kube-system",
            role_arn=self.role.role_arn,
            service_account="cluster-autoscaler",
        )

        cluster.add_service_account("cluster-autoscaler",
            name="cluster-autoscaler",
            namespace="kube-system",
            annotations={
                "eks.amazonaws.com/role-arn": self.role.role_arn
            }
        )

        cluster.add_helm_chart("EksAwsClusterAutoscaler",
            chart="cluster-autoscaler",
            repository="https://kubernetes.github.io/autoscaler", 
            release="cluster-autoscaler",
            namespace="kube-system",
            values={
                "autoDiscovery": {
                    "clusterName": cluster.cluster_name
                },
                "awsRegion": region,
                "rbac": {
                    "serviceAccount": {
                        "create": False,
                        "name": "cluster-autoscaler",
                        "annotations": {
                            "eks.amazonaws.com/role-arn": self.role.role_arn
                        }
                    }
                },
                "replicaCount": "0",
                "resources": {
                    "limits": {
                        "cpu": "200m",
                        "memory": "128Mi"
                    },
                    "requests": {
                        "cpu": "100m",
                        "memory": "128Mi"
                    }
                },
                "extraArgs": {
                    "skip-nodes-with-local-storage": "false",
                    "scan-interval": "10s",
                    "balance-similar-node-groups": "true",
                    "expander": "least-waste"
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
                # "serviceMonitor": {
                #     "enabled": True,
                #     "namespace": "grafana"
                # },
                # "prometheusRule": {
                #     "enabled": True,
                #     "namespace": "grafana"
                # },
                "extraArgs":{
                    "scale-down-utilization-threshold": 0.6,
                    "scale-down-non-empty-candidates-count": 30,
                    "scale-down-delay-after-add": "3m",
                    "scale-down-delay-after-delete": "0s",
                    "scale-down-unneeded-time": "7m",
                    "skip-nodes-with-local-storage": True,
                    "skip-nodes-with-system-pods": True,
                    "expander": "least-waste"
                }
            }
        )

    def create_role(self, region, account):
        # IAM Role for Cluster Autoscaler with pod identity webhook
        autoscaler_role = iam.Role(
            self, "EksAwsClusterAutoscalerRole",
            assumed_by=iam.ServicePrincipal("pods.eks.amazonaws.com"),
            role_name="EksAwsClusterAutoscalerRole"
        )
        # Override the trust policy
        autoscaler_role.assume_role_policy.add_statements(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("pods.eks.amazonaws.com")],
                actions=["sts:AssumeRole", "sts:TagSession"]
            )
        )
        policy_statements = [
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "autoscaling:DescribeAutoScalingGroups",
                    "autoscaling:DescribeAutoScalingInstances",
                    "autoscaling:DescribeLaunchConfigurations",
                    "autoscaling:DescribeScalingActivities",
                    "autoscaling:DescribeTags",
                    "ec2:DescribeImages",
                    "ec2:DescribeInstanceTypes",
                    "ec2:DescribeLaunchTemplateVersions",
                    "ec2:GetInstanceTypesFromInstanceRequirements",
                    "eks:DescribeNodegroup",
                    "iam:PassRole"
                ],
                resources=["*"]
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "autoscaling:SetDesiredCapacity",
                    "autoscaling:TerminateInstanceInAutoScalingGroup"
                ],
                resources=["*"]
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "autoscaling:DescribeAutoScalingGroups",
                    "autoscaling:DescribeAutoScalingInstances",
                    "autoscaling:DescribeLaunchConfigurations",
                    "autoscaling:DescribeScalingActivities",
                    "autoscaling:SetDesiredCapacity",
                    "autoscaling:TerminateInstanceInAutoScalingGroup",
                    "eks:DescribeNodegroup"
                ],
                resources=[
                    f"arn:aws:autoscaling:{region}:{account}:autoScalingGroup:*:autoScalingGroupName/*"
                ]
            )
        ]
    
        for statement in policy_statements:
            autoscaler_role.add_to_principal_policy(statement)
        return autoscaler_role