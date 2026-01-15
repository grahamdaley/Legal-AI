# AWS Infrastructure for Legal-AI

This directory contains Pulumi Infrastructure as Code (IaC) for provisioning AWS resources needed for Amazon Bedrock batch processing.

## What Gets Created

The Pulumi script provisions:

1. **S3 Buckets**:
   - `legal-ai-bedrock-batch-input-{environment}`: Stores JSONL input files for batch jobs
   - `legal-ai-bedrock-batch-output-{environment}`: Stores results from Bedrock batch jobs
   - Both buckets have versioning enabled and 90-day lifecycle policies

2. **IAM Role for Bedrock**:
   - `legal-ai-bedrock-batch-role-{environment}`: Service role that Bedrock assumes when running batch jobs
   - Policies allow Bedrock to read from input bucket, write to output bucket, and invoke models

3. **IAM User for Application**:
   - `legal-ai-bedrock-app-user-{environment}`: User for the Legal-AI application
   - Policies allow creating/managing batch jobs, uploading inputs, and downloading outputs
   - Access keys are generated for programmatic access

4. **Supported Bedrock Models**:
   - **Text Generation:**
     - Claude Opus 4.5 (`anthropic.claude-opus-4-5:0`) - Latest, best for complex reasoning
     - Claude 3.7 Sonnet (`anthropic.claude-3-7-sonnet:0`) - Balanced performance/cost
     - Claude 3.5 Sonnet v2 (`anthropic.claude-3-5-sonnet-20241022-v2:0`) - Fast, efficient
   - **Embeddings:**
     - Amazon Titan Text Embeddings V2 (`amazon.titan-embed-text-v2:0`) - 1024 dimensions
     - Cohere Embed English V3 (`cohere.embed-english-v3`) - English optimized
     - Cohere Embed Multilingual V3 (`cohere.embed-multilingual-v3`) - Multilingual support

## Prerequisites

1. **AWS CLI configured** with credentials that have admin access:
   ```bash
   aws configure
   ```

2. **Pulumi CLI installed**:
   ```bash
   brew install pulumi  # macOS
   ```

3. **Node.js 18+** installed:
   ```bash
   brew install node  # macOS
   ```

## Setup

### 1. Install Dependencies

```bash
cd infra/aws/
npm install
```

### 2. Login to Pulumi

```bash
# Option A: Pulumi Cloud (recommended)
pulumi login

# Option B: Local file-based state
pulumi login --local
```

### 3. Initialize a New Stack

Create a stack for your environment (dev, staging, prod):

```bash
pulumi stack init dev
```

### 4. Configure the Stack

Set configuration values:

```bash
# Set AWS region (default is ap-southeast-1)
pulumi config set aws:region ap-southeast-1

# Set environment name (optional, defaults to "dev")
pulumi config set environment dev
```

### 5. Preview Changes

```bash
pulumi preview
# or
npm run preview
```

### 6. Deploy Infrastructure

```bash
pulumi up
# or
npm run up
```

Review the changes and confirm with `yes`.

## Post-Deployment

After deployment, Pulumi exports important values:

```bash
# View all outputs
pulumi stack output
# or
npm run output

# Get specific values
pulumi stack output inputBucketName
pulumi stack output outputBucketName
pulumi stack output bedrockRoleArn
pulumi stack output appUserAccessKeyId
pulumi stack output appUserSecretAccessKey --show-secrets
```

### Update Environment Variables

**Automatic (Recommended)**: Use the sync script from the infra root:

```bash
cd ..
./sync-env.sh --aws-only
# or for a specific stack:
./sync-env.sh --aws-only --aws-stack dev
```

**Manual**: Add these to your `.env` file in the repository root:

```bash
# AWS credentials for the application user
AWS_ACCESS_KEY_ID=$(pulumi stack output appUserAccessKeyId)
AWS_SECRET_ACCESS_KEY=$(pulumi stack output appUserSecretAccessKey --show-secrets)
AWS_REGION=ap-southeast-1

# S3 bucket names
BEDROCK_BATCH_INPUT_BUCKET=$(pulumi stack output inputBucketName)
BEDROCK_BATCH_OUTPUT_BUCKET=$(pulumi stack output outputBucketName)

# IAM role ARN (used when creating batch jobs)
BEDROCK_BATCH_ROLE_ARN=$(pulumi stack output bedrockRoleArn)
```

## Managing Multiple Environments

Create separate stacks for different environments:

```bash
# Development
pulumi stack init dev
pulumi config set environment dev
pulumi up

# Staging
pulumi stack init staging
pulumi config set environment staging
pulumi up

# Production
pulumi stack init production
pulumi config set environment production
pulumi up
```

Switch between stacks:

```bash
pulumi stack select dev
pulumi stack select staging
pulumi stack select production
```

## Destroying Resources

To tear down all resources (be careful!):

```bash
pulumi destroy
# or
npm run destroy
```

## Development

Build TypeScript:

```bash
npm run build
```

The compiled JavaScript files are excluded from Git via `.gitignore`.

## Security Notes

1. **Access Keys**: The IAM user access keys are marked as secrets in Pulumi. Store them securely in your `.env` file (which should be in `.gitignore`).

2. **S3 Buckets**: Both buckets block all public access by default.

3. **IAM Permissions**: The application user has minimal permissions - only what's needed for batch processing.

4. **Model Access**: Bedrock access is restricted to specific model ARNs. Update `index.ts` if you need different models.

## Cost Considerations

- **S3 Storage**: Minimal costs; lifecycle policies delete files after 90 days
- **S3 Requests**: Pay per API call (PUT, GET, LIST)
- **Bedrock**: Pay-per-use based on input/output tokens
- **IAM**: No cost for users/roles/policies

Estimated monthly cost for low-moderate usage: $5-50 depending on batch job volume.

## Troubleshooting

### TypeScript compilation errors

```bash
npm run build
```

### Pulumi state conflicts

If you see state conflicts, ensure you're on the correct stack:

```bash
pulumi stack ls
pulumi stack select <your-stack>
```

### AWS permission errors

Ensure your AWS CLI credentials have sufficient permissions:

```bash
aws sts get-caller-identity
```

### Bedrock model access

If you get "model not available" errors, check that the models are enabled in your AWS account:

```bash
aws bedrock list-foundation-models --region ap-southeast-1
```

Some models require requesting access through the AWS Bedrock console.

## Next Steps

After infrastructure is deployed:

1. Update `batch/config/settings.py` to use the new environment variables
2. Create batch processing jobs in `batch/jobs/` that use the S3 buckets
3. Test with a small batch job before scaling up
