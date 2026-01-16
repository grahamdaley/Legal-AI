# Environment Sync Guide

This guide explains how to automatically sync Pulumi stack outputs to your `.env` file.

## Quick Start

After deploying your infrastructure:

```bash
cd infra/
./sync-env.sh
```

This will:
1. Read outputs from both AWS and Azure Pulumi stacks
2. Update or create `.env` file in the repository root
3. Set all infrastructure-related environment variables

## Usage Examples

### Sync Both Providers

```bash
# Use current stacks
./sync-env.sh

# Use specific stacks
./sync-env.sh --aws-stack dev --azure-stack prod
```

### Sync Only AWS

```bash
# Use current stack
./sync-env.sh --aws-only

# Use specific stack
./sync-env.sh --aws-only --aws-stack staging
```

### Sync Only Azure

```bash
# Use current stack
./sync-env.sh --azure-only

# Use specific stack
./sync-env.sh --azure-only --azure-stack prod
```

### Custom Output File

```bash
# Output to a different file
./sync-env.sh --output /path/to/custom.env
```

## What Gets Synced

### AWS Variables

- `AWS_ACCESS_KEY_ID` - IAM user access key
- `AWS_SECRET_ACCESS_KEY` - IAM user secret key
- `AWS_REGION` - AWS region (default: ap-southeast-1)
- `BEDROCK_BATCH_INPUT_BUCKET` - S3 bucket for batch inputs
- `BEDROCK_BATCH_OUTPUT_BUCKET` - S3 bucket for batch outputs
- `BEDROCK_BATCH_ROLE_ARN` - IAM role ARN for Bedrock

### Azure Variables

**Azure OpenAI:**
- `AZURE_OPENAI_ENDPOINT` - Azure OpenAI endpoint URL
- `AZURE_OPENAI_API_KEY` - Azure OpenAI API key
- `AZURE_OPENAI_GPT4O_MINI_DEPLOYMENT` - GPT-4o-mini deployment name
- `AZURE_OPENAI_GPT4O_DEPLOYMENT` - GPT-4o deployment name
- `AZURE_OPENAI_API_VERSION` - API version (default: 2024-10-01-preview)

**Azure Storage:**
- `AZURE_STORAGE_ACCOUNT_NAME` - Storage account name
- `AZURE_STORAGE_ACCOUNT_KEY` - Storage account key
- `AZURE_STORAGE_CONNECTION_STRING` - Full connection string
- `AZURE_BATCH_INPUT_CONTAINER` - Blob container for inputs
- `AZURE_BATCH_OUTPUT_CONTAINER` - Blob container for outputs

**Service Principal:**
- `AZURE_TENANT_ID` - Azure AD tenant ID
- `AZURE_CLIENT_ID` - Service principal client ID
- `AZURE_CLIENT_SECRET` - Service principal secret

## What Does NOT Get Synced

The following must be set manually in your `.env` file:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_DB_URL`
- Other application-specific settings

## Workflow

### Initial Setup

1. Deploy infrastructure:
   ```bash
   cd infra/aws/
   npm install
   pulumi up
   ```

2. Sync to `.env`:
   ```bash
   cd ..
   ./sync-env.sh --aws-only
   ```

3. Manually add other variables:
   ```bash
   # Edit ../.env and add SUPABASE_*, AZURE_OPENAI_*, etc.
   ```

### Switching Environments

```bash
# Switch to staging stack and update .env
cd infra/aws/
pulumi stack select staging

cd ..
./sync-env.sh --aws-only --aws-stack staging
```

### Multiple Environments

Use separate `.env` files for different environments:

```bash
# Development
./sync-env.sh --aws-stack dev --output ../.env.dev

# Staging  
./sync-env.sh --aws-stack staging --output ../.env.staging

# Production
./sync-env.sh --aws-stack prod --output ../.env.prod
```

## Script Behavior

- **Updates existing values**: If a variable already exists in `.env`, it will be updated
- **Adds new values**: If a variable doesn't exist, it will be appended
- **Skips null values**: If Pulumi returns no value, the variable is skipped
- **Preserves other variables**: Variables not managed by the script remain unchanged
- **Handles secrets**: Automatically retrieves secret values using `--show-secrets`

## Troubleshooting

### "Stack not found" error

Make sure the stack exists:

```bash
cd infra/aws/  # or azure/
pulumi stack ls
```

If it doesn't exist, create it:

```bash
pulumi stack init dev
pulumi config set environment dev
pulumi up
```

### "No such file or directory" error

Run the script from the `infra/` directory:

```bash
cd infra/
./sync-env.sh
```

### Values not updating

Check that you're selecting the correct stack:

```bash
cd infra/aws/
pulumi stack select dev
pulumi stack output  # Verify outputs exist

cd ..
./sync-env.sh --aws-stack dev
```

### Permission denied

Make sure the script is executable:

```bash
chmod +x infra/sync-env.sh
```

## Advanced Usage

### CI/CD Integration

```bash
# In your CI/CD pipeline
cd infra/
./sync-env.sh --aws-stack $ENVIRONMENT --output ../.env
```

### Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
cd infra/
./sync-env.sh --aws-stack dev
git add ../.env
```

### Verify Changes

```bash
# Sync and show differences
./sync-env.sh --aws-only
git diff ../.env
```

## Help

```bash
./sync-env.sh --help
```

For more details, see:
- [Main Infrastructure README](README.md)
- [AWS Infrastructure README](aws/README.md)
- [Azure Infrastructure README](azure/README.md)
