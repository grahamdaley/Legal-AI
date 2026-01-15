# Phase 1 Setup Guide

This guide walks you through setting up the Legal-AI system with Phase 1 models (no Bedrock Claude approval required).

## Phase 1 Configuration

**Embeddings:** Amazon Titan Text Embeddings V2 (Bedrock) - ✅ No approval needed  
**Text Generation:** Azure OpenAI GPT-4o - ✅ Already have access

## Prerequisites

1. **AWS Account** with Bedrock access (for embeddings)
2. **Azure OpenAI** resource with GPT-4o deployment
3. **Supabase** database

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

### Azure Infrastructure (optional, for batch processing)

```bash
cd infra/azure/
npm install

# Initialize stack  
pulumi stack init dev
pulumi config set azure-native:location eastasia  # Hong Kong
pulumi config set environment dev

# If you have existing Azure OpenAI resource
pulumi config set openaiResourceName your-openai-resource
pulumi config set openaiResourceGroup your-resource-group

# Deploy
pulumi up
```

## Step 2: Sync Environment Variables

After deploying infrastructure, sync credentials to `.env`:

```bash
cd infra/
./sync-env.sh --aws-only
# or for both:
./sync-env.sh
```

## Step 3: Configure Azure OpenAI

Add these to your `.env` file (manually):

```bash
# Azure OpenAI - eastasia (Hong Kong) or southeastasia (Singapore)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_API_VERSION=2024-10-01-preview
AZURE_OPENAI_GPT4O_DEPLOYMENT=gpt-4o

# Optional: If you also want embeddings from Azure
AZURE_OPENAI_EMBED_DEPLOYMENT=text-embedding-3-large
```

**How to get these values:**

```bash
# List your Azure OpenAI resources
az cognitiveservices account list \
  --query "[?kind=='OpenAI'].[name,location,properties.endpoint]" \
  --output table

# Get API key
az cognitiveservices account keys list \
  --name your-openai-resource \
  --resource-group your-resource-group \
  --query key1 \
  --output tsv

# List deployments
az cognitiveservices account deployment list \
  --name your-openai-resource \
  --resource-group your-resource-group \
  --query "[].{name:name,model:properties.model.name}" \
  --output table
```

## Step 4: Configure Supabase

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

## Step 5: Verify Configuration

Your `.env` should now have:

```bash
# AWS Bedrock (embeddings)
AWS_REGION=ap-southeast-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
BEDROCK_BATCH_INPUT_BUCKET=legal-ai-bedrock-batch-input-dev
BEDROCK_BATCH_OUTPUT_BUCKET=legal-ai-bedrock-batch-output-dev
BEDROCK_BATCH_ROLE_ARN=arn:aws:iam::...

# Azure OpenAI (text generation)
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_API_VERSION=2024-10-01-preview
AZURE_OPENAI_GPT4O_DEPLOYMENT=gpt-4o

# Supabase (database)
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
SUPABASE_DB_URL=postgresql://...

# AI Models (Phase 1)
EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
HEADNOTE_MODEL=azure-gpt-4o
```

## Step 6: Test the Setup

### Test AWS Bedrock Access

```bash
cd batch/
python -c "
import boto3
import os
from dotenv import load_dotenv

load_dotenv('../.env')

client = boto3.client(
    'bedrock-runtime',
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
    model=os.getenv('AZURE_OPENAI_GPT4O_DEPLOYMENT'),
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
    'bedrock-runtime',
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

## Step 7: Run a Test Job

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

## Migration to Phase 2 (After Claude Approval)

When Claude access is approved:

1. Update `.env`:
   ```bash
   HEADNOTE_MODEL=anthropic.claude-opus-4-5:0
   ```

2. Restart your services - that's it!

The code automatically routes to the correct model based on the `HEADNOTE_MODEL` value.

## Cost Estimates (Phase 1)

**Embeddings (Titan V2):**
- $0.10 per 1M input tokens
- ~100 tokens per document = $0.01 per 1000 documents

**Text Generation (GPT-4o):**
- Input: $2.50 per 1M tokens
- Output: $10 per 1M tokens  
- ~2000 tokens per headnote = $0.05 per headnote

**Total for 10,000 cases:**
- Embeddings: $10
- Headnotes: $500
- **Total: ~$510**

Compare to Phase 2 (Claude Opus 4.5): ~$1,500 (3x more expensive but better quality)

## Questions?

- See [INTERIM_MODELS.md](INTERIM_MODELS.md) for detailed model comparison
- See [MODEL_RECOMMENDATIONS.md](MODEL_RECOMMENDATIONS.md) for long-term strategy
- Check [../infra/SYNC_ENV_GUIDE.md](../infra/SYNC_ENV_GUIDE.md) for environment sync details
