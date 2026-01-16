# Phase 1 Setup Guide

This guide walks you through setting up the Legal-AI system with Phase 1 models (no Bedrock Claude approval required).

## Phase 1 Configuration

**Embeddings:** Amazon Titan Text Embeddings V2 (Bedrock) - ✅ No approval needed  
**Text Generation:** Azure OpenAI GPT-4o-mini - ✅ No approval needed, 93% cheaper than GPT-4o

## Prerequisites

1. **AWS Account** with Bedrock access (for embeddings)
2. **Azure Subscription** (OpenAI resource will be created by Pulumi)
3. **Supabase** database
4. **Azure OpenAI Access** - Apply at https://aka.ms/oai/access (typically 1-2 business days)

## Step 1: Deploy Infrastructure

### AWS Infrastructure (for embeddings)

```bash
cd infra/aws/
npm install

# Initialize stack
pulumi stack init dev
pulumi config set aws:region ap-southeast-1
pulumi config set environment dev

# Deploy
pulumi up
```

### Azure Infrastructure (for OpenAI + batch processing)

Pulumi will create:
- Azure OpenAI account with GPT-4o-mini deployment
- Storage Account for batch processing
- Service Principal with proper permissions

```bash
cd infra/azure/
npm install

# Login to Azure
az login
az account set --subscription "<your-subscription-id>"

# Initialize stack  
pulumi stack init dev
pulumi config set azure-native:location southeastasia  # Or: eastus, westeurope
pulumi config set environment dev

# Optional: Deploy GPT-4o instead of GPT-4o-mini
pulumi config set deployGpt4o true
pulumi config set deployGpt4oMini false

# Deploy (takes ~5-10 minutes)
pulumi up
```

**Note:** If you don't have Azure OpenAI access approval yet:
```bash
# Skip model deployment temporarily
pulumi config set deployGpt4oMini false
pulumi up  # Deploy storage only

# After approval, deploy model
pulumi config set deployGpt4oMini true
pulumi up
```

## Step 2: Sync Environment Variables

After deploying infrastructure, sync credentials to `.env`:

```bash
cd infra/
./sync-env.sh
```

This automatically extracts:
- AWS credentials and S3 bucket names
- Azure OpenAI endpoint, API key, and deployment names
- Azure Storage credentials
- Service Principal credentials

## Step 3: Configure Supabase

Add Supabase configuration to `.env`:

```bash
# Supabase - for local dev
SUPABASE_URL=http://127.0.0.1:34321
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key
SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:34322/postgres

# Or for production
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-production-key
SUPABASE_DB_URL=postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres
```

## Step 4: Verify Configuration

Your `.env` should now have:

```bash
# AWS Bedrock (embeddings)
AWS_REGION=ap-southeast-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
BEDROCK_BATCH_INPUT_BUCKET=legal-ai-bedrock-batch-input-dev
BEDROCK_BATCH_OUTPUT_BUCKET=legal-ai-bedrock-batch-output-dev
BEDROCK_BATCH_ROLE_ARN=arn:aws:iam::...

# Azure OpenAI (text generation) - auto-synced from Pulumi
AZURE_OPENAI_ENDPOINT=https://legalai-openai-dev.openai.azure.com/
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_API_VERSION=2024-10-01-preview
AZURE_OPENAI_GPT4O_MINI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_GPT4O_DEPLOYMENT=gpt-4o  # If you deployed GPT-4o

# Azure Storage (batch processing) - auto-synced from Pulumi
AZURE_STORAGE_ACCOUNT_NAME=...
AZURE_STORAGE_CONNECTION_STRING=...
AZURE_BATCH_INPUT_CONTAINER=batch-input
AZURE_BATCH_OUTPUT_CONTAINER=batch-output

# Supabase (database)
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
SUPABASE_DB_URL=postgresql://...
```

## Step 5: Test the Setup

### Test AWS Bedrock Access

```bash
cd batch/
python -c "
import boto3
import os
from dotenv import load_dotenv

load_dotenv('../.env')

client = boto3.client(
    'bedrock',
    region_name=os.getenv('AWS_REGION'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

# List available models
response = client.list_foundation_models()
print('✓ AWS Bedrock access working!')
print(f'Available models: {len(response[\"modelSummaries\"])}')
"
```

### Test Azure OpenAI Access

```bash
cd batch/
python -c "
from openai import AzureOpenAI
import os
from dotenv import load_dotenv

load_dotenv('../.env')

client = AzureOpenAI(
    api_key=os.getenv('AZURE_OPENAI_API_KEY'),
    api_version=os.getenv('AZURE_OPENAI_API_VERSION'),
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT')
)

response = client.chat.completions.create(
    model=os.getenv('AZURE_OPENAI_GPT4O_MINI_DEPLOYMENT'),
    messages=[{'role': 'user', 'content': 'Test'}],
    max_tokens=10
)

print('✓ Azure OpenAI access working!')
print(f'Response: {response.choices[0].message.content}')
"
```

### Test Embeddings

```bash
cd batch/
python -c "
import boto3
import json
import os
from dotenv import load_dotenv

load_dotenv('../.env')

client = boto3.client(
    'bedrock',
    region_name=os.getenv('AWS_REGION'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

body = json.dumps({
    'inputText': 'This is a test legal document about contract law.',
    'dimensions': 1024,
    'normalize': True
})

response = client.invoke_model(
    modelId='amazon.titan-embed-text-v2:0',
    body=body
)

result = json.loads(response['body'].read())
embedding = result.get('embedding', [])

print('✓ Titan embeddings working!')
print(f'Embedding dimensions: {len(embedding)}')
"
```

## Step 6: Run a Test Job

Generate embeddings for a test case:

```bash
cd batch/

# Make sure you have cases in the database first
# Then run embedding generation
python -m jobs.generate_embeddings_cases --limit 1
```

Generate a test headnote:

```bash
cd batch/
python -m jobs.generate_headnotes --limit 1
```

## Troubleshooting

### "Access Denied" on AWS Bedrock

Check your credentials:
```bash
aws sts get-caller-identity
```

List available models:
```bash
aws bedrock list-foundation-models --region ap-southeast-1
```

### Azure OpenAI 401 Unauthorized

Verify your endpoint and key:
```bash
az cognitiveservices account show \
  --name your-openai-resource \
  --resource-group your-resource-group
```

### "Deployment not found" error

Check your deployment name matches:
```bash
az cognitiveservices account deployment list \
  --name your-openai-resource \
  --resource-group your-resource-group
```

### Import errors

Make sure dependencies are installed:
```bash
cd batch/
pip install openai boto3 python-dotenv
```

## Next Steps

Once everything is working:

1. **Request Claude access** in AWS Bedrock Console → Model access
2. **Run scrapers** to populate your database with cases
3. **Generate embeddings** for semantic search
4. **Generate headnotes** using GPT-4o
5. **Compare quality** once Claude is approved

## Upgrading Models

### To GPT-4o (Higher Quality)

If you need better quality:

1. Deploy GPT-4o:
   ```bash
   cd infra/azure/
   pulumi config set deployGpt4o true
   pulumi up
   ```

2. Update `batch/config/settings.py`:
   ```python
   headnote_model: str = "azure-gpt-4o"
   ```

3. Re-sync credentials:
   ```bash
   cd infra/
   ./sync-env.sh --azure-only
   ```

### To Claude Opus 4.5 (Best Quality, After Approval)

When AWS Bedrock Claude access is approved:

1. Update `batch/config/settings.py`:
   ```python
   headnote_model: str = "anthropic.claude-opus-4-5:0"
   ```

2. Restart your services

The code automatically routes to the correct model based on the `headnote_model` value.

## Cost Estimates (Phase 1)

**Embeddings (Titan V2, Batch Mode):**
- $0.000055 per 1,000 input tokens (batch)
- For 120,000 cases × 5,000 tokens = 600M tokens
- Cost: **$33**

**Text Generation (GPT-4o-mini, Batch Mode):**
- Input: $0.075 per 1M tokens
- Output: $0.30 per 1M tokens  
- For 120,000 cases:
  - Input: 600M tokens × $0.075/1M = $45
  - Output: 60M tokens × $0.30/1M = $18
- Cost: **$63**

**Azure Storage:**
- ~$2-5 per month

**Total for 120,000 cases (one-time):**
- Embeddings: $33
- Headnotes: $63
- Storage: $5
- **Total: ~$101**

**Alternative models:**
- GPT-4o (batch): ~$1,050 (15x more expensive, higher quality)
- Claude Opus 4.5 (batch, after approval): ~$2,250 (35x more expensive, best quality)

## Questions?

- See [INTERIM_MODELS.md](INTERIM_MODELS.md) for detailed model comparison
- See [MODEL_RECOMMENDATIONS.md](MODEL_RECOMMENDATIONS.md) for long-term strategy
- Check [../infra/SYNC_ENV_GUIDE.md](../infra/SYNC_ENV_GUIDE.md) for environment sync details
