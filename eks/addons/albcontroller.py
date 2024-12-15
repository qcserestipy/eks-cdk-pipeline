from aws_cdk import (
    aws_iam as iam,
    aws_eks as eks,
    aws_ec2 as ec2
)
from constructs import Construct
from ..helm import EksHelmDeployWithPodIdentity
from typing import Any

class EksAwsAlbControllerAddOn(Construct):
    """Deploys the AWS ALB Ingress Controller to an EKS cluster.

    This construct installs the AWS ALB Ingress Controller using Helm with Pod Identity,
    allowing the EKS cluster to manage Application Load Balancers.

    Attributes:
        cluster (eks.Cluster): The EKS cluster where the ALB controller is deployed.
        vpc (ec2.Vpc): The VPC associated with the EKS cluster.
        account (str): AWS account ID.
        region (str): AWS region.
        helm_deploy (EksHelmDeployWithPodIdentity): Helm deployment construct for the ALB controller.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        cluster: eks.Cluster,
        vpc: ec2.Vpc,
        account: str,
        region: str,
        **kwargs: Any
    ) -> None:
        """Initializes the EksAwsAlbControllerAddOn.

        Args:
            scope (Construct): The scope in which this construct is defined.
            id (str): The scoped construct ID.
            cluster (eks.Cluster): The EKS cluster to deploy the ALB controller to.
            vpc (ec2.Vpc): The VPC in which the cluster is deployed.
            account (str): AWS account ID.
            region (str): AWS region.
            **kwargs (Any): Additional keyword arguments.
        """
        super().__init__(scope, id, **kwargs)

        self.serviceaccountname = "application-loadbalancer"
        self.release = "aws-load-balancer-controller-1.8.2"
        self.namespace = "kube-system"
        self.version = "1.8.2"
        self.repository = "https://aws.github.io/eks-charts"

        self.helm_deploy = EksHelmDeployWithPodIdentity(
            self,
            "EksAwsAlbControllerAddOn",
            cluster=cluster,
            chart="aws-load-balancer-controller",
            release=self.release,
            repository=self.repository,
            namespace=self.namespace,
            version=self.version,
            serviceaccountname=self.serviceaccountname,
            role_policy_statements=self.alb_policy_list(),
            values={
                "clusterName": cluster.cluster_name,
                "region": region,
                "vpcId": vpc.vpc_id,
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
        )

    def alb_policy_list(self) -> list:
        """Generates a list of IAM policy statements required by the ALB controller.

        Returns:
            list: A list of `iam.PolicyStatement` objects.
        """
        return [
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:CreateServiceLinkedRole"],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "iam:AWSServiceName": "elasticloadbalancing.amazonaws.com"
                    }
                }
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ec2:DescribeAccountAttributes",
                    "ec2:DescribeAddresses",
                    "ec2:DescribeAvailabilityZones",
                    "ec2:DescribeInternetGateways",
                    "ec2:DescribeVpcs",
                    "ec2:DescribeVpcPeeringConnections",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeSecurityGroups",
                    "ec2:DescribeInstances",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DescribeTags",
                    "ec2:GetCoipPoolUsage",
                    "ec2:DescribeCoipPools",
                    "elasticloadbalancing:DescribeLoadBalancers",
                    "elasticloadbalancing:DescribeLoadBalancerAttributes",
                    "elasticloadbalancing:DescribeListeners",
                    "elasticloadbalancing:DescribeListenerCertificates",
                    "elasticloadbalancing:DescribeSSLPolicies",
                    "elasticloadbalancing:DescribeRules",
                    "elasticloadbalancing:DescribeTargetGroups",
                    "elasticloadbalancing:DescribeTargetGroupAttributes",
                    "elasticloadbalancing:DescribeTargetHealth",
                    "elasticloadbalancing:DescribeTags",
                    "elasticloadbalancing:DescribeTrustStores"
                ],
                resources=["*"]
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:DescribeUserPoolClient",
                    "acm:ListCertificates",
                    "acm:DescribeCertificate",
                    "iam:ListServerCertificates",
                    "iam:GetServerCertificate",
                    "waf-regional:GetWebACL",
                    "waf-regional:GetWebACLForResource",
                    "waf-regional:AssociateWebACL",
                    "waf-regional:DisassociateWebACL",
                    "wafv2:GetWebACL",
                    "wafv2:GetWebACLForResource",
                    "wafv2:AssociateWebACL",
                    "wafv2:DisassociateWebACL",
                    "shield:GetSubscriptionState",
                    "shield:DescribeProtection",
                    "shield:CreateProtection",
                    "shield:DeleteProtection"
                ],
                resources=["*"]
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ec2:AuthorizeSecurityGroupIngress",
                    "ec2:RevokeSecurityGroupIngress"
                ],
                resources=["*"]
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ec2:CreateSecurityGroup"
                ],
                resources=["*"]
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ec2:CreateTags"],
                resources=["arn:aws:ec2:*:*:security-group/*"],
                conditions={
                    "StringEquals": {
                        "ec2:CreateAction": "CreateSecurityGroup"
                    },
                    "Null": {
                        "aws:RequestTag/elbv2.k8s.aws/cluster": "false"
                    }
                }
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ec2:CreateTags", "ec2:DeleteTags"],
                resources=["arn:aws:ec2:*:*:security-group/*"],
                conditions={
                    "Null": {
                        "aws:RequestTag/elbv2.k8s.aws/cluster": "true",
                        "aws:ResourceTag/elbv2.k8s.aws/cluster": "false"
                    }
                }
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ec2:AuthorizeSecurityGroupIngress", "ec2:RevokeSecurityGroupIngress", "ec2:DeleteSecurityGroup"],
                resources=["*"],
                conditions={
                    "Null": {
                        "aws:ResourceTag/elbv2.k8s.aws/cluster": "false"
                    }
                }
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["elasticloadbalancing:CreateLoadBalancer", "elasticloadbalancing:CreateTargetGroup"],
                resources=["*"],
                conditions={
                    "Null": {
                        "aws:RequestTag/elbv2.k8s.aws/cluster": "false"
                    }
                }
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "elasticloadbalancing:CreateListener",
                    "elasticloadbalancing:DeleteListener",
                    "elasticloadbalancing:CreateRule",
                    "elasticloadbalancing:DeleteRule"
                ],
                resources=["*"]
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["elasticloadbalancing:AddTags", "elasticloadbalancing:RemoveTags"],
                resources=[
                    "arn:aws:elasticloadbalancing:*:*:targetgroup/*/*",
                    "arn:aws:elasticloadbalancing:*:*:loadbalancer/net/*/*",
                    "arn:aws:elasticloadbalancing:*:*:loadbalancer/app/*/*"
                ],
                conditions={
                    "Null": {
                        "aws:RequestTag/elbv2.k8s.aws/cluster": "true",
                        "aws:ResourceTag/elbv2.k8s.aws/cluster": "false"
                    }
                }
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["elasticloadbalancing:AddTags", "elasticloadbalancing:RemoveTags"],
                resources=[
                    "arn:aws:elasticloadbalancing:*:*:listener/net/*/*/*",
                    "arn:aws:elasticloadbalancing:*:*:listener/app/*/*/*",
                    "arn:aws:elasticloadbalancing:*:*:listener-rule/net/*/*/*",
                    "arn:aws:elasticloadbalancing:*:*:listener-rule/app/*/*/*"
                ]
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "elasticloadbalancing:ModifyLoadBalancerAttributes",
                    "elasticloadbalancing:SetIpAddressType",
                    "elasticloadbalancing:SetSecurityGroups",
                    "elasticloadbalancing:SetSubnets",
                    "elasticloadbalancing:DeleteLoadBalancer",
                    "elasticloadbalancing:ModifyTargetGroup",
                    "elasticloadbalancing:ModifyTargetGroupAttributes",
                    "elasticloadbalancing:DeleteTargetGroup"
                ],
                resources=["*"],
                conditions={
                    "Null": {
                        "aws:ResourceTag/elbv2.k8s.aws/cluster": "false"
                    }
                }
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["elasticloadbalancing:AddTags"],
                resources=[
                    "arn:aws:elasticloadbalancing:*:*:targetgroup/*/*",
                    "arn:aws:elasticloadbalancing:*:*:loadbalancer/net/*/*",
                    "arn:aws:elasticloadbalancing:*:*:loadbalancer/app/*/*"
                ],
                conditions={
                    "StringEquals": {
                        "elasticloadbalancing:CreateAction": ["CreateTargetGroup", "CreateLoadBalancer"]
                    },
                    "Null": {
                        "aws:RequestTag/elbv2.k8s.aws/cluster": "false"
                    }
                }
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["elasticloadbalancing:RegisterTargets", "elasticloadbalancing:DeregisterTargets"],
                resources=["arn:aws:elasticloadbalancing:*:*:targetgroup/*/*"]
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "elasticloadbalancing:SetWebAcl",
                    "elasticloadbalancing:ModifyListener",
                    "elasticloadbalancing:AddListenerCertificates",
                    "elasticloadbalancing:RemoveListenerCertificates",
                    "elasticloadbalancing:ModifyRule"
                ],
                resources=["*"]
            )
        ]