from aws_cdk import (
    aws_iam as iam,
    aws_eks as eks,
)
from constructs import Construct
import json
class EksEbsCSIDriverAddOn(Construct):
    def __init__(
        self,
        scope: Construct, 
        id: str,
        cluster: eks.Cluster,
        **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        self.role = self.create_role()
        # Define the configuration values for the EBS CSI Driver add-on
        ebs_csi_driver_config = {
            "controller": {
                "replicaCount": 1,
                "resources": {
                    "requests": {
                        "cpu": "100m",
                        "memory": "128Mi"
                    },
                    "limits": {
                        "cpu": "400m",
                        "memory": "512Mi"
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
                        "operator": "Exists",
                        "effect": "NoSchedule"
                    }
                ]
            },
            "node": {
                "resources": {
                    "requests": {
                        "cpu": "100m",
                        "memory": "128Mi"
                    },
                    "limits": {
                        "cpu": "400m",
                        "memory": "512Mi"
                    }
                }
            }
        }
        # Create EBS CSI Driver add-on
        _ = eks.CfnAddon(
            self, "EbsCsiDriverAddon",
            cluster_name=cluster.cluster_name,
            addon_name="aws-ebs-csi-driver",
            addon_version="v1.32.0-eksbuild.1",
            resolve_conflicts="OVERWRITE",
            preserve_on_delete=False,
            configuration_values=json.dumps(ebs_csi_driver_config),
        )
        self.cfn_pod_identity_association = eks.CfnPodIdentityAssociation(self, "EbsCsiDriverAddonRoleAssociation",
            cluster_name=cluster.cluster_name,
            namespace="kube-system",
            role_arn=self.role.role_arn,
            service_account="ebs-csi-controller-sa",
        )

    def create_role(self):
        # IAM Role for Elastic Loadbalancer
        ebscsi_role = iam.Role(
            self, "EbsCsiDriverAddonRole",
            assumed_by=iam.ServicePrincipal("pods.eks.amazonaws.com"),
            role_name="EbsCsiDriverAddonRole",
        )
        # Override the trust policy
        ebscsi_role.assume_role_policy.add_statements(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("pods.eks.amazonaws.com")],
                actions=["sts:AssumeRole", "sts:TagSession"]
            )
        )
        # Inline policy document
        policy_document = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "ec2:CreateSnapshot",
                        "ec2:AttachVolume",
                        "ec2:DetachVolume",
                        "ec2:ModifyVolume",
                        "ec2:DescribeAvailabilityZones",
                        "ec2:DescribeInstances",
                        "ec2:DescribeSnapshots",
                        "ec2:DescribeTags",
                        "ec2:DescribeVolumes",
                        "ec2:DescribeVolumesModifications"
                    ],
                    resources=["*"]
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ec2:CreateTags"],
                    resources=[
                        "arn:aws:ec2:*:*:volume/*",
                        "arn:aws:ec2:*:*:snapshot/*"
                    ],
                    conditions={
                        "StringEquals": {
                            "ec2:CreateAction": ["CreateVolume", "CreateSnapshot"]
                        }
                    }
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ec2:DeleteTags"],
                    resources=[
                        "arn:aws:ec2:*:*:volume/*",
                        "arn:aws:ec2:*:*:snapshot/*"
                    ]
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ec2:CreateVolume"],
                    resources=["*"],
                    conditions={
                        "StringLike": {
                            "aws:RequestTag/ebs.csi.aws.com/cluster": "true"
                        }
                    }
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ec2:CreateVolume"],
                    resources=["*"],
                    conditions={
                        "StringLike": {
                            "aws:RequestTag/CSIVolumeName": "*"
                        }
                    }
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ec2:DeleteVolume"],
                    resources=["*"],
                    conditions={
                        "StringLike": {
                            "ec2:ResourceTag/ebs.csi.aws.com/cluster": "true"
                        }
                    }
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ec2:DeleteVolume"],
                    resources=["*"],
                    conditions={
                        "StringLike": {
                            "ec2:ResourceTag/CSIVolumeName": "*"
                        }
                    }
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ec2:DeleteVolume"],
                    resources=["*"],
                    conditions={
                        "StringLike": {
                            "ec2:ResourceTag/kubernetes.io/created-for/pvc/name": "*"
                        }
                    }
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ec2:DeleteSnapshot"],
                    resources=["*"],
                    conditions={
                        "StringLike": {
                            "ec2:ResourceTag/CSIVolumeSnapshotName": "*"
                        }
                    }
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ec2:DeleteSnapshot"],
                    resources=["*"],
                    conditions={
                        "StringLike": {
                            "ec2:ResourceTag/ebs.csi.aws.com/cluster": "true"
                        }
                    }
                ),
            ]
        )
        # Attach the inline policy to the role
        ebscsi_role.attach_inline_policy(
            iam.Policy(
                self, "EbsCsiDriverPolicy",
                document=policy_document
            )
        )
        return ebscsi_role