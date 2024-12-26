from aws_cdk import (
    CfnJson,
    aws_eks as eks,
    Duration,
    aws_sqs as sqs,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
)
from constructs import Construct
from typing import Any

class EksKarpenter(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        cluster: eks.Cluster,
        account: str,
        region: str,
        **kwargs: Any
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self._region = region
        self._account = account

        # Create a dedicated service account for Karpenter using IRSA
        self._namespace = "karpenter"
        self._releasename = "karpenter"
        self._serviceaccountname = "karpenter"
        namespace_manifest = cluster.add_manifest(
            "KarpenterNamespace",
            {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": self._namespace
                }
            }
        )

        service_account = cluster.add_service_account(
            "KarpenterServiceAccount",
            name=self._serviceaccountname,
            namespace=self._namespace
        )

        # enforce namespace is created before service account
        service_account.node.add_dependency(namespace_manifest)

        self.role = self.create_role(
            cluster,
            service_account.role,
        )

        cluster.aws_auth.add_role_mapping(
            service_account.role,
            username='system:node:{{EC2PrivateDNSName}}',
            groups=[
               "system:bootstrappers",
               "system:nodes"
            ]
        )

        # Create interruption queue and attach SQS policies
        _ = self.add_interruption_queue(cluster.cluster_name, service_account.role)

        # Deploy Karpenter via Helm, referencing the IRSA role
        karpenter_helm_chart = cluster.add_helm_chart("EksKarpenterHelmChart",
            chart="karpenter",
            repository="oci://public.ecr.aws/karpenter/karpenter",
            version="1.1.1",
            release=self._releasename,
            create_namespace=False,
            namespace=self._namespace,
            values={
                "replicas": 1,
                "serviceAccount": {
                    "name": self._serviceaccountname,
                    "create": False,  # We create it via CDK
                    "annotations": {
                        "eks.amazonaws.com/role-arn": service_account.role.role_arn
                    }
                },
                "settings": {
                    "clusterName": cluster.cluster_name,
                    "clusterEndpoint": cluster.cluster_endpoint,
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
                        "operator": "Exists",
                        "effect": "NoSchedule"
                    }
                ]
                # "serviceMonitor": {
                #     "enabled": True,
                #     "endpointConfig": {
                #         "port": "8080",
                #         "interval": "30s",
                #         "scrapeTimeout": "10s",
                #         "scheme": "http"
                #     }
                # }
            }
        )
        karpenter_helm_chart.node.add_dependency(namespace_manifest)
        karpenter_helm_chart.node.add_dependency(self.role)

    def create_role(self, cluster, karpenter_role) -> iam.Role:
        # Attach policies to the service account's role
        # Add managed policies
        karpenter_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSWorkerNodePolicy"))
        karpenter_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKS_CNI_Policy"))
        karpenter_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryReadOnly"))
        karpenter_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"))
        karpenter_role.assume_role_policy.add_statements(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("pods.eks.amazonaws.com")],
                actions=["sts:AssumeRole", "sts:TagSession"]
            )
        )
        karpenter_role.assume_role_policy.add_statements(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("ec2.amazonaws.com")],
                actions=["sts:AssumeRole"]
            )
        )
        karpenter_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:DescribeLaunchTemplateVersions",
                    "ec2:RunInstances",
                    "ec2:CreateFleet",
                    "ec2:TerminateInstances",
                    "ec2:DescribeInstances",
                    "ec2:DescribeSecurityGroups",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeInstanceTypes",
                    "eks:DescribeNodegroup",
                    "eks:DescribeCluster",
                    "iam:PassRole",
                    "ssm:GetParameter",
                    "autoscaling:DescribeAutoScalingGroups",
                    "autoscaling:UpdateAutoScalingGroup",
                    "iam:PassRole",
                    "pricing:GetProducts",
                ],
                resources=["*"]
            )
        )
        karpenter_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ec2:TerminateInstances"],
                effect=iam.Effect.ALLOW,
                resources=["*"],
                conditions={
                    "StringLike": {
                        "ec2:ResourceTag/karpenter.sh/nodepool": "*"
                    }
                }
            )
        )
        karpenter_role.add_to_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                effect=iam.Effect.ALLOW,
                resources=[
                    f"arn:aws:iam::{self._account}:role/KarpenterNodeRole-{cluster.cluster_name}"
                ]
            )
        )
        karpenter_role.add_to_policy(
            iam.PolicyStatement(
                actions=["eks:DescribeCluster"],
                effect=iam.Effect.ALLOW,
                resources=[
                    f"arn:aws:eks:{self._region}:{self._account}:cluster/{cluster.cluster_name}"
                ]
            )
        )
        karpenter_role.add_to_policy(
            iam.PolicyStatement(
                actions=["iam:CreateInstanceProfile"],
                effect=iam.Effect.ALLOW,
                resources=["*"],
                conditions={
                    "StringEquals": CfnJson(
                        self,
                        "ClusterNameTagCreateInstanceProfile",
                        value = {
                            f"aws:RequestTag/kubernetes.io/cluster/{cluster.cluster_name}": "owned",
                            "aws:RequestTag/topology.kubernetes.io/region": self._region
                        },
                    ),
                    "StringLike": CfnJson(
                        self,
                        "EC2NodeClassTagCreateInstanceProfile",
                        value = {
                            "aws:RequestTag/karpenter.k8s.aws/ec2nodeclass": "*"
                        }
                    )
                }
            )
        )
        karpenter_role.add_to_policy(iam.PolicyStatement(
            actions=["iam:TagInstanceProfile"],
            effect=iam.Effect.ALLOW,
            resources=["*"],
            conditions={
                "StringEquals": CfnJson(
                    self,
                    "ResourceTagTagInstanceProfile",
                    value = {
                        "aws:ResourceTag/kubernetes.io/cluster/{}".format(cluster.cluster_name): "owned",
                        "aws:ResourceTag/topology.kubernetes.io/region": self._region,
                        "aws:RequestTag/kubernetes.io/cluster/{}".format(cluster.cluster_name): "owned",
                        "aws:RequestTag/topology.kubernetes.io/region": self._region
                    },
                ),
                "StringLike": CfnJson(
                    self,
                    "RequestTagTagInstanceProfile",
                    value = {
                        "aws:ResourceTag/karpenter.k8s.aws/ec2nodeclass": "*",
                        "aws:RequestTag/karpenter.k8s.aws/ec2nodeclass": "*"
                    },
                ),
            }
        ))
        karpenter_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "iam:AddRoleToInstanceProfile",
                "iam:RemoveRoleFromInstanceProfile",
                "iam:DeleteInstanceProfile"
            ],
            effect=iam.Effect.ALLOW,
            resources=["*"],
            conditions={
                "StringEquals": CfnJson(
                    self,
                    "TagAddRoleToInstanceProfile",
                    value = {
                        "aws:ResourceTag/kubernetes.io/cluster/{}".format(cluster.cluster_name): "owned",
                        "aws:ResourceTag/topology.kubernetes.io/region": self._region
                    },
                ),
                "StringLike": {
                    "aws:ResourceTag/karpenter.k8s.aws/ec2nodeclass": "*"
                }
            }
        ))
        karpenter_role.add_to_policy(iam.PolicyStatement(
            actions=["iam:GetInstanceProfile"],
            effect=iam.Effect.ALLOW,
            resources=["*"]
        ))
        karpenter_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:RunInstances",
                    "ec2:CreateFleet",
                    "ec2:CreateLaunchTemplate"
                ],
                resources=[
                    f"arn:aws:ec2:{self._region}:{self._account}:fleet/*",
                    f"arn:aws:ec2:{self._region}:{self._account}:instance/*",
                    f"arn:aws:ec2:{self._region}:{self._account}:volume/*",
                    f"arn:aws:ec2:{self._region}:{self._account}:network-interface/*",
                    f"arn:aws:ec2:{self._region}:{self._account}:launch-template/*",
                    f"arn:aws:ec2:{self._region}:{self._account}:spot-instances-request/*"
                ],
                conditions={
                    "StringEquals": CfnJson(
                        self, "AllowScopedEC2InstanceActionsWithTags",
                        value={
                            f"aws:RequestTag/kubernetes.io/cluster/{cluster.cluster_name}": "owned"
                        }
                    ),
                    "StringLike": CfnJson(
                        self, "RequestTagEC2NodeClass",
                        value={
                            "aws:RequestTag/karpenter.sh/nodepool": "*"
                        }
                    )
                }
            )
        )
        karpenter_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ec2:CreateTags"],
                resources=[
                    f"arn:aws:ec2:{self._region}:{self._account}:fleet/*",
                    f"arn:aws:ec2:{self._region}:{self._account}:instance/*",
                    f"arn:aws:ec2:{self._region}:{self._account}:volume/*",
                    f"arn:aws:ec2:{self._region}:{self._account}:network-interface/*",
                    f"arn:aws:ec2:{self._region}:{self._account}:launch-template/*",
                    f"arn:aws:ec2:{self._region}:{self._account}:spot-instances-request/*"
                ],
                conditions={
                    "StringEquals": CfnJson(
                        self, "AllowScopedResourceCreationTagging",
                        value={
                            f"aws:RequestTag/kubernetes.io/cluster/{cluster.cluster_name}": "owned",
                            "ec2:CreateAction": [
                                "RunInstances",
                                "CreateFleet",
                                "CreateLaunchTemplate"
                            ]
                        }
                    ),
                    "StringLike": CfnJson(
                        self, "ResourceTagEC2NodeClass",
                        value={
                            "aws:RequestTag/karpenter.sh/nodepool": "*"
                        }
                    )
                }
            )
        )
        karpenter_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ec2:CreateTags"],
                resources=[f"arn:aws:ec2:{self._region}:{self._account}:instance/*"],
                conditions={
                    "StringEquals": CfnJson(
                        self, "AllowScopedResourceTagging",
                        value={
                            f"aws:ResourceTag/kubernetes.io/cluster/{cluster.cluster_name}": "owned"
                        }
                    ),
                    "StringLike": CfnJson(
                        self, "RequestTagScopedResourceTagging",
                        value={
                            "aws:ResourceTag/karpenter.sh/nodepool": "*"
                        }
                    ),
                    "ForAllValues:StringEquals": CfnJson(
                        self, "AllowTagKeysResourceTagging",
                        value={
                            "aws:TagKeys": ["karpenter.sh/nodeclaim", "Name"]
                        }
                    )
                }
            )
        )
        karpenter_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ec2:TerminateInstances", "ec2:DeleteLaunchTemplate"],
                resources=[
                    f"arn:aws:ec2:{self._region}:{self._account}:instance/*",
                    f"arn:aws:ec2:{self._region}:{self._account}:launch-template/*"
                ],
                conditions={
                    "StringEquals": CfnJson(
                        self, "AllowScopedDeletion",
                        value={
                            f"aws:ResourceTag/kubernetes.io/cluster/{cluster.cluster_name}": "owned"
                        }
                    ),
                    "StringLike": CfnJson(
                        self, "ResourceTagScopedDeletion",
                        value={
                            "aws:ResourceTag/karpenter.sh/nodepool": "*"
                        }
                    )
                }
            )
        )
        karpenter_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:DescribeAvailabilityZones",
                    "ec2:DescribeImages",
                    "ec2:DescribeInstances",
                    "ec2:DescribeInstanceTypeOfferings",
                    "ec2:DescribeInstanceTypes",
                    "ec2:DescribeLaunchTemplates",
                    "ec2:DescribeSecurityGroups",
                    "ec2:DescribeSpotPriceHistory",
                    "ec2:DescribeSubnets"
                ],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "aws:RequestedRegion": self._region
                    }
                }
            )
        )
        return karpenter_role

    def add_interruption_queue(self, cluster_name, role):
        interruption_queue = sqs.Queue(
            self,
            "KarpenterInterruptionQueue",
            queue_name=cluster_name,
            retention_period=Duration.minutes(5)
        )

        rules = [
            events.Rule(
                self,
                "ScheduledChangeRule",
                event_pattern={
                    "source": ["aws.health"],
                    "detail_type": ["AWS Health Event"]
                }
            ),
            events.Rule(
                self,
                "SpotInterruptionRule",
                event_pattern={
                    "source": ["aws.ec2"],
                    "detail_type": ["EC2 Spot Instance Interruption Warning"]
                }
            ),
            events.Rule(
                self,
                "RebalanceRule",
                event_pattern={
                    "source": ["aws.ec2"],
                    "detail_type": ["EC2 Instance Rebalance Recommendation"]
                }
            ),
            events.Rule(
                self,
                "InstanceStateChangeRule",
                event_pattern={
                    "source": ["aws.ec2"],
                    "detail_type": ["EC2 Instance State-change Notification"]
                }
            )
        ]

        for rule in rules:
            rule.add_target(targets.SqsQueue(interruption_queue))

        # Allow Karpenter to access the interruption queue
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:DeleteMessage",
                    "sqs:GetQueueAttributes",
                    "sqs:GetQueueUrl",
                    "sqs:ReceiveMessage"
                ],
                resources=[interruption_queue.queue_arn]
            )
        )

        return interruption_queue

    def add_ec2_node_class(
            self,
            id: str,
            cluster,
            subnet_id,
            security_group_id,
            name='default',
        ) -> None:
        return cluster.add_manifest(
            id,
            {
                "apiVersion": "karpenter.k8s.aws/v1",
                "kind": "EC2NodeClass",
                "metadata": {
                    "name": name,
                },
                "spec": {
                    "amiFamily": "AL2023",
                    "amiSelectorTerms": [
                        {
                            "alias": "al2023@latest"
                        }
                    ],
                    "role": self.role.role_name,
                    "subnetSelectorTerms": subnet_id,
                    "securityGroupSelectorTerms": security_group_id,
                }
            }
        )

    def add_node_pool(
        self,
        id: str,
        cluster: eks.Cluster,
        nodeclass_name: str,
        labels: dict,
        node_arch: list,
        capacity_type: list,
        instance_category: list,
        instance_family: list,
        cpu_limit: int,
        mem_limit: str,
    ) -> None:
        return cluster.add_manifest(
            id,
            {
                "apiVersion": "karpenter.sh/v1",
                "kind": "NodePool",
                "metadata": {
                    "name": id
                },
                "spec": {
                    "template": {
                        "metadata": {
                            "labels": labels
                        },
                        "spec": {
                            "requirements": [
                                {
                                  "key": "kubernetes.io/arch",
                                  "operator": "In",
                                  "values": node_arch
                                },
                                {
                                  "key": "kubernetes.io/os",
                                  "operator": "In",
                                  "values": ["linux"]
                                },
                                {
                                  "key": "karpenter.sh/capacity-type",
                                  "operator": "In",
                                  "values": capacity_type
                                },
                                {
                                  "key": "karpenter.k8s.aws/instance-category",
                                  "operator": "In",
                                  "values": instance_category
                                },
                                {
                                  "key": "karpenter.k8s.aws/instance-family",
                                  "operator": "In",
                                  "values": instance_family
                                }
                            ],
                            "nodeClassRef": {
                              "group": "karpenter.k8s.aws",
                              "kind": "EC2NodeClass",
                              "name": nodeclass_name
                            },
                            "expireAfter": "5m"
                        }
                    },
                    "limits": {
                        "cpu": cpu_limit,
                        "memory": mem_limit
                    },
                    "disruption": {
                        "consolidationPolicy": "WhenEmptyOrUnderutilized",
                        "consolidateAfter": "1m"
                    }
                }
            }
        )