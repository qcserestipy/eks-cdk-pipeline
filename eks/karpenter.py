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
    """Deploys Karpenter for EKS cluster auto-scaling.

    This construct installs Karpenter, providing efficient and flexible
    auto-scaling capabilities for Kubernetes clusters.

    Attributes:
        cluster (eks.Cluster): The EKS cluster where Karpenter is deployed.
        account (str): AWS account ID.
        region (str): AWS region.
        role (iam.Role): IAM role used by Karpenter.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        cluster: eks.Cluster,
        account: str,
        region: str,
        **kwargs: Any
    ) -> None:
        """Initializes the EksKarpenter construct.

        Args:
            scope (Construct): The scope in which this construct is defined.
            id (str): The scoped construct ID.
            cluster (eks.Cluster): The EKS cluster to deploy Karpenter to.
            account (str): AWS account ID.
            region (str): AWS region.
            **kwargs (Any): Additional keyword arguments.
        """
        super().__init__(scope, id, **kwargs)

        self._region = region
        self._account = account
        self._serviceaccountname = "karpenter"
        self._namespace = "karpenter"
        self._releasename = "karpenter"
        self.role = self.create_role(cluster)
        self.add_interruption_queue(cluster.cluster_name, self.role)

        cluster.aws_auth.add_role_mapping(self.role, username='system:node:{{EC2PrivateDNSName}}' ,groups=["system:bootstrappers", "system:nodes"])

        karpenter_helm_chart = cluster.add_helm_chart("EksKarpenterHelmChart",
            chart="karpenter",
            repository="oci://public.ecr.aws/karpenter/karpenter",
            version="1.0.0",
            release=self._releasename,
            create_namespace=True,
            namespace=self._namespace,
            values={
                "replicas": 1,
                "serviceAccount": {
                    "name": self._serviceaccountname,
                    "create": True,
                    "annotations": {
                        "eks.amazonaws.com/role-arn": self.role.role_arn
                    }
                },
                "controller": {
                    "resources": {
                        "limits": {
                            "cpu": "200m",
                            "memory": "256Mi"
                        },
                        "requests": {
                            "cpu": "50m",
                            "memory": "64Mi"
                        }    
                    } 
                },
                "settings":{
                    "clusterName": cluster.cluster_name,
                    "clusterEndpoint": cluster.cluster_endpoint,
                },
                "postInstallHook": {
                    "image": {
                        "repository": "docker.io/bitnami/kubectl",
                        "tag": "1.30",
                        "digest": "sha256:4f74249f971f8ca158a03eaa0c8e7741a2a750fe53525dc69497cf23584df04a"
                    }
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
                "serviceMonitor": {
                    "enabled": True
                }
            }
        )

        cfn_sa_association = eks.CfnPodIdentityAssociation(self, "EksKarpenterPodIdentityAssociation",
            cluster_name=cluster.cluster_name,
            namespace=self._namespace,
            role_arn=self.role.role_arn,
            service_account=self._serviceaccountname,
        )

        cfn_sa_association.node.add_dependency(karpenter_helm_chart)

    def create_role(self, cluster) -> iam.Role:
        """Creates an IAM role for Karpenter with necessary permissions.

        Args:
            cluster (eks.Cluster): The EKS cluster where Karpenter is deployed.

        Returns:
            iam.Role: The IAM role used by Karpenter.
        """
        # Define the Karpenter IAM role
        karpenter_role = iam.Role(
            self, "EksKarpenterRole",
            assumed_by=iam.ServicePrincipal("pods.eks.amazonaws.com"),
            role_name=f"KarpenterNodeRole-{cluster.cluster_name}",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSWorkerNodePolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKS_CNI_Policy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryReadOnly"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
            ]
        )
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

    def add_interruption_queue(self, cluster_name, role) -> sqs.Queue:
        """Creates an SQS queue for handling EC2 instance interruptions and adds necessary permissions.

        Args:
            cluster_name (str): Name of the EKS cluster.
            role (iam.Role): IAM role to which permissions will be added.

        Returns:
            sqs.Queue: The SQS queue for interruption events.
        """
        # Create the SQS queue to handle interruptions
        interruption_queue = sqs.Queue(
            self, 
            "KarpenterInterruptionQueue",
            queue_name=cluster_name,
            retention_period=Duration.minutes(5)
        )
        # Define the event rules
        rules = [
            # ScheduledChangeRule
            events.Rule(
                self, 
                "ScheduledChangeRule",
                event_pattern={
                    "source": ["aws.health"],
                    "detail_type": ["AWS Health Event"]
                }
            ),
            # SpotInterruptionRule
            events.Rule(
                self, 
                "SpotInterruptionRule",
                event_pattern={
                    "source": ["aws.ec2"],
                    "detail_type": ["EC2 Spot Instance Interruption Warning"]
                }
            ),
            # RebalanceRule
            events.Rule(
                self, 
                "RebalanceRule",
                event_pattern={
                    "source": ["aws.ec2"],
                    "detail_type": ["EC2 Instance Rebalance Recommendation"]
                }
            ),
            # InstanceStateChangeRule
            events.Rule(
                self, 
                "InstanceStateChangeRule",
                event_pattern={
                    "source": ["aws.ec2"],
                    "detail_type": ["EC2 Instance State-change Notification"]
                }
            )
        ]
        # Add the SQS queue as a target for each rule
        for rule in rules:
            rule.add_target(targets.SqsQueue(interruption_queue))

        # Add the necessary IAM policy statements for SQS access
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

    def add_ec2_node_class(self, id: str, spec: dict) -> eks.KubernetesManifest:
        """Adds an EC2NodeClass to the cluster.

        Args:
            id (str): Identifier for the EC2NodeClass resource.
            spec (dict): Specification of the EC2NodeClass.

        Returns:
            eks.KubernetesManifest: The Kubernetes manifest for the EC2NodeClass.
        """
        return self.cluster_stack.cluster.add_manifest(id, {
            "apiVersion": "karpenter.k8s.aws/v1beta1",
            "kind": "EC2NodeClass",
            "metadata": {
                "name": id,
                "namespace": self._namespace,
            },
            "spec": spec,
        })

    def add_node_pool(self, id: str, spec: dict) -> eks.KubernetesManifest:
        """Adds a NodePool to the cluster.

        Args:
            id (str): Identifier for the NodePool resource.
            spec (dict): Specification of the NodePool.

        Returns:
            eks.KubernetesManifest: The Kubernetes manifest for the NodePool.
        """
        return self.cluster_stack.cluster.add_manifest(id, {
            "apiVersion": "karpenter.sh/v1beta1",
            "kind": "NodePool",
            "metadata": {
                "name": id,
                "namespace": self._namespace,
            },
            "spec": spec,
        })