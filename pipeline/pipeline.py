import aws_cdk as cdk
from aws_cdk.pipelines import (
    CodePipeline,
    CodePipelineSource,
    CodeBuildStep,
    ShellStep,
)
from aws_cdk import (
    Environment,
    Stack,
    aws_codebuild as codebuild,
    aws_codecommit as codecommit,
    aws_iam as iam,
)
from typing import Any
from constructs import Construct
from .stages import (
    EksClusterDeploymentStage,
    KeypairDeploymentStage,
)


class PipelineStack(Stack):
    """Defines the CI/CD pipeline stack for deploying AWS resources.

    Attributes:
        env (Environment): The AWS environment where the stack is deployed.
        region (str): The AWS region.
        account (str): The AWS account ID.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        config: dict,
        **kwargs: Any
    ) -> None:
        """Initializes the PipelineStack.

        Args:
            scope (Construct): The scope in which this construct is defined.
            id (str): The scoped construct ID.
            config (dict): Configuration parameters for the pipeline.
            **kwargs (Any): Additional keyword arguments.
        """
        super().__init__(scope, id, **kwargs)
        env = kwargs.get("env")
        region = env.region
        account = env.account

        # Define a policy statement for DescribeCluster
        describe_cluster_policy = iam.PolicyStatement(
            actions=["eks:DescribeCluster"],
            resources=[
                f"arn:aws:eks:{config['eks']['target_region']}:{account}:cluster/{config['eks']['cluster_name']}",
            ],
            effect=iam.Effect.ALLOW
        )

        # Define a policy statement for accessing EKS parameters in SSM
        access_eksparams_policy = iam.PolicyStatement(
            actions=[
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:GetParameterHistory",
                "ssm:DescribeParameters",
                "ssm:PutParameter",
                "ssm:DeleteParameter",
                "ssm:AddTagsToResource"
            ],
            resources=[
                f"arn:aws:ssm:{config['eks']['target_region']}:{account}:parameter/eks/*"
            ],
            effect=iam.Effect.ALLOW
        )

        # Import the CodeCommit repository
        source_repo = codecommit.Repository.from_repository_name(
            self,
            f"{config['pipeline']['repositoryname']}-repo",
            repository_name=config['pipeline']['repositoryname']
        )

        # Define the pipeline source
        pipeline_source = CodePipelineSource.code_commit(
            source_repo,
            config['pipeline']['branchname'],
            code_build_clone_output=True
        )

        # Create the CodePipeline
        pipeline = CodePipeline(
            self,
            f"{config['pipeline']['repositoryname']}",
            pipeline_name=f"{config['pipeline']['repositoryname']}",
            cross_account_keys=True,
            enable_key_rotation=True,
            synth=CodeBuildStep(
                f"{config['pipeline']['repositoryname']}-buildStep",
                input=pipeline_source,
                build_environment=codebuild.BuildEnvironment(
                    build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                    compute_type=codebuild.ComputeType.SMALL,
                ),
                install_commands=[
                    "npm install -g aws-cdk",
                    "pip install -r requirements.txt",
                ],
                commands=[
                    "cdk synth -q"
                ],
                role_policy_statements=[
                    describe_cluster_policy,
                    access_eksparams_policy
                ]
            )
        )

        # Scanning and Tests
        files_to_scan = [
            "./app.py",
            "./eks/*.py",
            "./eks/util/*.py",
            "./pipeline/*.py",
        ]
        bandit_command = "bandit " + " ".join(files_to_scan)
        scanning_wave = pipeline.add_wave("Scanning")
        scanning_wave.add_pre(
            ShellStep(
                "Code Scanning",
                commands=[
                    "pip install -r requirements.txt",
                    bandit_command,
                ],
            )
        )

        # Account ID for dev
        dev_account_id = config["accounts"]["dev"]["id"]
        # Add Keypair deployment stage to the pipeline
        dev_keypair_wave = pipeline.add_wave("Dev-Keypair")
        dev_keypair_wave.add_stage(
            KeypairDeploymentStage(
                self,
                f"Keypair-Dev-{config['eks']['target_region']}",
                config=config,
                phase="dev",
                env=Environment(
                    account=dev_account_id,
                    region=config['eks']['target_region'],
                ),
            )
        )
        # Add EKS cluster deployment stage to the pipeline
        pipeline.add_stage(
            EksClusterDeploymentStage(
                self,
                f"Dev-EksCluster-{config['eks']['target_region']}",
                config=config,
                phase="dev",
                env=Environment(
                    account=dev_account_id,
                    region=config['eks']['target_region'],
                ),
            )
        )

        # In case of a seperate prod account, add the following code
        # prod_account_id = config["accounts"]["prod"]["id"]
        # prod_keypair_wave = pipeline.add_wave("Prod-Keypair")
        # prod_keypair_wave.add_stage(
        #     KeypairDeploymentStage(
        #         self,
        #         f"Keypair-Prod-{config['eks']['target_region']}",
        #         config=config,
        #         phase="prod",
        #         env=Environment(
        #             account=prod_account_id,
        #             region=config['eks']['target_region'],
        #         ),
        #     )
        # )

        # pipeline.add_stage(
        #     EksClusterDeploymentStage(
        #         self,
        #         f"Prod-EksCluster-{config['eks']['target_region']}",
        #         config=config,
        #         phase="prod",
        #         env=Environment(
        #             account=prod_account_id,
        #             region=config['eks']['target_region'],
        #         ),
        #     )
        # )