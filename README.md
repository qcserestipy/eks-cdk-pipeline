# EKS Cluster CDK Deployment

This project contains AWS Cloud Development Kit (CDK) code to deploy an Amazon Elastic Kubernetes Service (EKS) cluster along with its necessary IAM roles, network infrastructure, and associated configurations.

## Project Structure

- `eks/`
  - `__init__.py`: Package initializer.
  - `cluster.py`: Contains the `EksClusterStack` class, defining the EKS cluster and its associated resources.
  - `iam.py`: Contains the `EksIamStack` class, defining the IAM roles and policies for the EKS cluster.
  - `network.py`: Contains the `EksNetworkStack` class, defining the network infrastructure for the EKS cluster.
  - `util/config.py`: Contains the `Config` class for reading and parsing the configuration file.

- `app.py`: Main entry point of the CDK application. It defines and synthesizes the stacks.

## Prerequisites

- AWS CDK installed
- AWS CLI configured with appropriate permissions
- Python 3.8 or later
- Node.js (for AWS CDK)
- AWS CodeCommit connected to git repository in Deployment Account

## Configuration

Configuration is managed through a JSON file. By default, the project uses a configuration file named `config.json` located in the `config` directory. You can specify a different configuration file by setting the `CDK_APP_CONFIG` environment variable.

** Change the respective entries in the `config.json` **

# Deployment
Install dependencies:

```
micromamba env create -f conda_env.yaml
npm install -g aws-cdk
```

Bootstrap the CDK environment:
```
export AWS_REGION=eu-central-1
export AWS_PROFILE=hpc-dev
cdk bootstrap
```

Deploy the stacks:
```
export AWS_REGION=eu-central-1
export AWS_PROFILE=hpc-dev
cdk synth
cdk deploy
```

To add additional dependencies, for example other CDK libraries, just add
them to your `requirements.txt` file and rerun the `pip install -r requirements.txt`
command.

## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation

Enjoy!


# Known Issues
## KMS Key Grant Required for autoscaling group
In each target account when using encrypted AMIs for autoscaling groups an additional key grant needs to be created for the linked service role:
```
aws kms create-grant \
  --region eu-central-1 \
  --key-id arn:<arn-of-kms-key> \
  --grantee-principal arn:aws:iam::<target-account-id>:role/aws-service-role/autoscaling.amazonaws.com/ AWSServiceRoleForAutoScaling \
  --operations "Encrypt" "Decrypt" "ReEncryptFrom" "ReEncryptTo" "GenerateDataKey" "GenerateDataKeyWithoutPlaintext" "DescribeKey" "CreateGrant"
 ```
