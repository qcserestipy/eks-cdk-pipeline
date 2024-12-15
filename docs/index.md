# Welcome to the EKS CDK Project Documentation 

This documentation provides an overview and API reference for the AWS CDK (Cloud Development Kit) project designed to deploy an Amazon EKS (Elastic Kubernetes Service) cluster along with its associated resources and applications.

---

## Overview

This project automates the deployment of an EKS cluster using AWS CDK in Python. It includes constructs for setting up the network infrastructure, IAM roles and policies, EKS cluster and node groups, and various add-ons and applications deployed to the cluster.

### **Key Features**

- **Infrastructure as Code**: Use AWS CDK to define and provision cloud infrastructure using familiar programming languages.
- **Modular Constructs**: Reusable and customizable constructs for different components like networking, IAM, EKS cluster, and add-ons.
- **Secure and Scalable**: Implements best practices for security and scalability, including the use of IAM Roles for Service Accounts (IRSA) and auto-scaling with Karpenter.
- **Helm Integration**: Simplifies application deployment using Helm charts with support for Pod Identity.

---

## Architecture

The project's architecture comprises several AWS resources and CDK constructs that work together to create a fully functional EKS environment.

### **Networking**
  - **`EksNetworkStack`**: Creates a VPC with public and private subnets across multiple availability zones, tagged appropriately for Kubernetes integration.

### **IAM Roles and Policies**
  - **`EksIamStack`**: Defines IAM managed policies required for cross-account KMS key usage and other IAM roles needed by the cluster.

### **EKS Cluster**
  - **`EksClusterStack`**: Sets up the EKS cluster, including the control plane and worker nodes, and integrates various add-ons and applications.

### **Add-ons and Controllers**
  - **`EksCoreDnsAddOn`**: Deploys the CoreDNS add-on for internal DNS resolution within the cluster.
  - **`EksPodIdentityAddOn`**: Enables IAM Roles for Service Accounts (IRSA) for secure pod-level authentication.
  - **`EksAwsAlbControllerAddOn`**: Installs the AWS Application Load Balancer (ALB) Ingress Controller for Kubernetes.
  - **`EksKarpenter`**: Deploys Karpenter for efficient cluster auto-scaling.
  - **`EksHelmDeployWithPodIdentity`**: Helper construct for deploying Helm charts with Pod Identity.

### **Node Groups**
  - **`EksNodeGroups`**: Creates managed node groups with specific configurations for instance types, capacity types, labels, and taints.

### **Bastion Host**
  - **`EksBastionHost`**: Sets up an EC2 instance for securely managing and accessing the EKS cluster.

### **SSM Parameters**
  - **`EksSSMParametersStack`**: Stores essential EKS cluster information in AWS Systems Manager Parameter Store for use by other services or scripts.

---

## Getting Started

### **Prerequisites**

- **AWS Account**: An AWS account with permissions to create resources like VPCs, IAM roles, EKS clusters, etc.
- **AWS CLI**: Installed and configured with your AWS credentials.
- **AWS CDK**: Install AWS CDK globally.

```bash
  npm install -g aws-cdk
```

- Python: Version 3.7 or higher.
- Node.js: For CDK and npm packages.
- kubectl: Kubernetes command-line tool.
- Helm: Kubernetes package manager.
### Installation
1. Clone the Repository
```bash
  git clone https://github.com/yourusername/your-repo-name.git
  cd your-repo-name
```
2. Set Up a Python Virtual Environment (Use any package manager such as micromamba, mamba or conda) and install depencies
```bash
  micromamba env create -f conda_env.yaml
```
3. Bootstrap the CDK Environment
Replace YOUR_ACCOUNT_ID and YOUR_REGION with your AWS account ID and desired AWS region.
```bash
  cdk bootstrap aws://YOUR_ACCOUNT_ID/YOUR_REGION
```
4. Deploying the Stacks
```bash
  cdk deploy --all
```

---

## Project Structure
- app.py: Entry point of the CDK application.
- eks/: Contains constructs related to the EKS cluster and its components.
    - keypairs.py: Defines the KeypairStack.
    - iam.py: Defines the EksIamStack.
    - network.py: Defines the EksNetworkStack.
    - cluster.py: Defines the EksClusterStack.
    - clusterparams.py: Defines the EksSSMParametersStack.
    - karpenter.py: EksKarpenter construct.
    - bastion.py: EksBastionHost construct.
    - compute.py: EksNodeGroups construct.
- addons/: Contains constructs for EKS add-ons.
    - coredns.py: EksCoreDnsAddOn.
    - albcontroller.py: EksAwsAlbControllerAddOn.
    - podidentity.py: EksPodIdentityAddOn.
- pipeline/: Contains constructs for the CI/CD pipeline.
    - pipeline.py: Defines the PipelineStack.
    - stages.py: Defines deployment stages.

---

## Documentation
API Reference: Detailed documentation of all constructs and stacks in the project.
Deployment Stages: Information about the deployment stages in the CI/CD pipeline.
Constructs and Stacks: Documentation for individual constructs and stacks.

---

## Contributing
Contributions are welcome! If you'd like to contribute, please follow these steps:

1. Fork the Repository
Click the "Fork" button at the top right corner of the repository page.

2. Clone Your Fork

```bash
  git clone https://github.com/yourusername/your-repo-name.git
  cd your-repo-name
```

3. Create a Feature Branch

```bash
  git checkout -b feature/your-feature-name
```

4. Make Your Changes

Implement your feature or fix the bug.

5. Commit and Push

```bash
  git add .
  git commit -m "Description of your changes"
  git push origin feature/your-feature-name
```

6. Create a Pull Request

Open a pull request from your forked repository's feature branch to the main repository's main branch.

---

## License
This project is licensed under the Apache 2.0 License. See the LICENSE file for details.

---

## Acknowledgments
- AWS CDK: Thanks to the AWS CDK team for providing an excellent framework for cloud infrastructure as code.
- Community Contributors: Thanks to all contributors who have helped improve this project.

---

## Frequently Asked Questions (FAQ)
### Q: What is AWS CDK?
A: AWS Cloud Development Kit (CDK) is an open-source software development framework to define your cloud application resources using familiar programming languages.

### Q: Can I use this project in my own AWS account?
A: Yes, you can deploy this project in your own AWS account. Ensure you have the necessary permissions and have configured your AWS credentials.

### Q: How do I customize the EKS cluster configuration?
A: You can modify the config dictionary or relevant construct parameters in the code to customize aspects like cluster name, node group configurations, and add-on settings.

---

## Happy deploying!
Feel free to explore the documentation and reach out if you have any questions.