#!/usr/bin/env python3
import aws_cdk as cdk
from eks.util.config import Config
from eks.util.account import Account
from pipeline.pipeline import PipelineStack

DEFAULT_CONFIG = "config"
import os
app_config = os.getenv("CDK_APP_CONFIG", DEFAULT_CONFIG)
app_dir = os.path.dirname(os.path.realpath(__file__))
config_file_path = os.path.join(app_dir, "config", app_config + ".json")
configuration = Config(config_file_path, vpc_present=True)
config = configuration.config

app = cdk.App()

pipeline_account = Account(
    account_label=config["pipeline"]["account"],
    account_region=config["pipeline"]["region"],
    config=config,
)

pipeline_env = cdk.Environment(
    account=pipeline_account.id,
    region=pipeline_account.region,
)


eks_pipeline = PipelineStack(
    app,
    "EKS-PipelineStack",
    description="CDK Pipeline to deploy resources for the EKS project",
    config=config,
    env=pipeline_env,
)

app.synth()