# Legal-AI Infrastructure

This directory contains Pulumi Infrastructure as Code (IaC) for provisioning cloud resources needed for AI batch processing.

## Structure

The infrastructure is organized into separate directories for each cloud provider:

```
infra/
├── aws/          # AWS Bedrock infrastructure (TypeScript)
│   ├── index.ts
│   ├── package.json
│   └── README.md
└── azure/        # Azure OpenAI infrastructure (TypeScript)
    ├── index.ts
    ├── package.json
    └── README.md
```

## Overview

### AWS (Amazon Bedrock)

Location: `./aws/`

**Purpose**: For Claude models and Amazon Titan embeddings via Amazon Bedrock batch processing

**Creates**:
- S3 buckets for batch input/output
- IAM role for Bedrock batch jobs
- IAM user with programmatic access
- Proper security policies and lifecycle management

**See**: [aws/README.md](aws/README.md) for detailed setup instructions

### Azure (Azure OpenAI)

Location: `./azure/`

**Purpose**: For OpenAI embeddings via Azure OpenAI batch processing

**Creates**:
- Resource Group
- Storage Account with blob containers
- Service Principal with RBAC
- Role assignments for OpenAI and Storage access

**See**: [azure/README.md](azure/README.md) for detailed setup instructions

## Prerequisites

Both infrastructures require:

1. **Pulumi CLI**:
   ```bash
   brew install pulumi
   pulumi login
   ```

2. **Node.js 18+**:
   ```bash
   brew install node
   ```

3. **Cloud-specific CLIs**:
   ```bash
   # For AWS
   brew install awscli
   aws configure

   # For Azure
   brew install azure-cli
   az login
   ```

## Quick Start

### Deploy AWS Infrastructure

```bash
cd aws/
npm install
pulumi stack init dev
pulumi config set aws:region ap-southeast-1
pulumi config set environment dev
pulumi up
```

### Deploy Azure Infrastructure

```bash
cd azure/
npm install
pulumi stack init dev
pulumi config set azure-native:location southeastasia
pulumi config set environment dev
pulumi config set openaiResourceName your-openai-resource
pulumi config set openaiResourceGroup your-resource-group
pulumi up
```

## Post-Deployment

After deploying either infrastructure, you can automatically sync the stack outputs to your `.env` file.

### Automatic Sync (Recommended)

Use the `sync-env.sh` script to automatically read Pulumi outputs and update your `.env` file:

```bash
# Sync both AWS and Azure using current stacks
./sync-env.sh

# Sync specific stacks
./sync-env.sh --aws-stack dev --azure-stack prod

# Sync only AWS
./sync-env.sh --aws-only --aws-stack dev

# Sync only Azure
./sync-env.sh --azure-only --azure-stack staging
```

**What gets synced:**
- AWS: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `BEDROCK_BATCH_*`, `AWS_REGION`
- Azure: `AZURE_STORAGE_*`, `AZURE_BATCH_*`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`

**Note**: Other environment variables (like `SUPABASE_*`, `AZURE_OPENAI_*`) must still be set manually.

### Manual Sync (Alternative)

If you prefer to manually export outputs:

<details>
<summary>AWS Outputs</summary>

```bash
cd aws/
pulumi stack output appUserAccessKeyId
pulumi stack output appUserSecretAccessKey --show-secrets
pulumi stack output inputBucketName
pulumi stack output outputBucketName
pulumi stack output bedrockRoleArn
```

Add to `.env`:
```bash
AWS_ACCESS_KEY_ID=<appUserAccessKeyId>
AWS_SECRET_ACCESS_KEY=<appUserSecretAccessKey>
AWS_REGION=ap-southeast-1
BEDROCK_BATCH_INPUT_BUCKET=<inputBucketName>
BEDROCK_BATCH_OUTPUT_BUCKET=<outputBucketName>
BEDROCK_BATCH_ROLE_ARN=<bedrockRoleArn>
```
</details>

<details>
<summary>Azure Outputs</summary>

```bash
cd azure/
pulumi stack output storageAccountName
pulumi stack output storageAccountKey --show-secrets
pulumi stack output storageConnectionString --show-secrets
pulumi stack output inputContainerName
pulumi stack output outputContainerName
pulumi stack output servicePrincipalClientId
pulumi stack output servicePrincipalTenantId
pulumi stack output servicePrincipalClientSecret --show-secrets
```

Add to `.env`:
```bash
AZURE_STORAGE_ACCOUNT_NAME=<storageAccountName>
AZURE_STORAGE_ACCOUNT_KEY=<storageAccountKey>
AZURE_STORAGE_CONNECTION_STRING=<storageConnectionString>
AZURE_BATCH_INPUT_CONTAINER=<inputContainerName>
AZURE_BATCH_OUTPUT_CONTAINER=<outputContainerName>
AZURE_TENANT_ID=<servicePrincipalTenantId>
AZURE_CLIENT_ID=<servicePrincipalClientId>
AZURE_CLIENT_SECRET=<servicePrincipalClientSecret>
```
</details>

## Managing Multiple Environments

Both AWS and Azure support multiple environments (dev, staging, production) via Pulumi stacks:

```bash
# In either aws/ or azure/ directory

# Create and deploy dev stack
pulumi stack init dev
pulumi config set environment dev
pulumi up

# Create and deploy staging stack
pulumi stack init staging
pulumi config set environment staging
pulumi up

# Switch between stacks
pulumi stack select dev
pulumi stack select staging
```

## Independent Deployment

AWS and Azure infrastructures are completely independent:

- You can deploy both, either one, or neither
- Each has its own Pulumi state
- Each can have separate stacks (dev, staging, prod)
- The application code (`batch/`) will use whichever credentials are in `.env`

## Technology Stack

- **Language**: TypeScript
- **IaC Tool**: Pulumi
- **AWS Provider**: `@pulumi/aws`
- **Azure Providers**: `@pulumi/azure-native`, `@pulumi/azuread`

## Development

Each subdirectory is a standalone Node.js/TypeScript project:

```bash
# Build TypeScript
cd aws/  # or azure/
npm run build

# Preview changes
npm run preview

# Deploy
npm run up

# View outputs
npm run output

# Destroy
npm run destroy
```

## Security Best Practices

1. **Secrets Management**: All sensitive outputs (API keys, passwords) are marked as Pulumi secrets
2. **Least Privilege**: IAM/RBAC policies grant only necessary permissions
3. **No Public Access**: All storage has public access blocked
4. **TLS Enforcement**: Minimum TLS 1.2 enforced on all services
5. **Lifecycle Policies**: Automatic deletion of old files (90 days)

## Cost Optimization

- **S3/Blob Storage**: Lifecycle policies automatically delete old data
- **IAM/RBAC**: No cost for identity and access management
- **Pay-per-use**: Both AWS Bedrock and Azure OpenAI batch APIs charge per token
- **Estimated Cost**: $5-50/month for moderate usage

## Troubleshooting

### Common Issues

1. **Pulumi state conflicts**: Ensure you're on the correct stack with `pulumi stack select`
2. **TypeScript errors**: Run `npm run build` to check for compilation issues
3. **Cloud authentication**: Verify with `aws sts get-caller-identity` or `az account show`
4. **Permission errors**: Ensure your cloud credentials have admin access for initial setup

### Getting Help

- Check provider-specific READMEs: [aws/README.md](aws/README.md), [azure/README.md](azure/README.md)
- Pulumi documentation: https://www.pulumi.com/docs/
- AWS Bedrock: https://docs.aws.amazon.com/bedrock/
- Azure OpenAI: https://learn.microsoft.com/azure/ai-services/openai/

## Next Steps

1. Deploy infrastructure for your chosen cloud provider(s)
2. Update `.env` with the exported credentials
3. Implement batch processing logic in `batch/jobs/`
4. Test with small batch jobs before scaling
5. Set up monitoring (CloudWatch for AWS, Azure Monitor for Azure)
