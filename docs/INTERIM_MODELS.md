# Interim Model Recommendations (While Waiting for Claude Access)

If you don't yet have access to Claude models in Bedrock, here are the best alternatives available immediately.

## Quick Answer

**For immediate use without approval:**

1. **Text Generation**: Use **Azure OpenAI GPT-4o** (you already have access)
2. **Embeddings**: Use **Amazon Titan Text Embeddings V2** (no approval needed)

## Text Generation Options (Ranked)

### Option 1: Azure OpenAI GPT-4o ✅ RECOMMENDED

**Why this is best:**
- You already have Azure OpenAI set up
- No Bedrock approval needed
- Excellent quality for legal text
- Supports structured outputs
- 128K context window (good for long judgments)

**Setup:**
```python
# In batch/config/settings.py, use Azure OpenAI endpoint
HEADNOTE_MODEL = "gpt-4o"  # Your Azure deployment name

# Or use the direct Azure OpenAI API
from openai import AzureOpenAI

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-10-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
```

**Cost:** ~$2.50 per 1M input tokens, $10 per 1M output tokens

### Option 2: Amazon Titan Text Premier (Bedrock - No Approval)

**Model ID:** `amazon.titan-text-premier-v1:0`

**Why:**
- Available immediately in Bedrock (no approval needed)
- Good for general text generation
- Decent quality for structured outputs
- Cost-effective

**Limitations:**
- Not as good as Claude for complex reasoning
- 32K context window (smaller than needed for very long judgments)
- Quality may be lower for legal analysis

**Setup:**
```python
import boto3
import json

client = boto3.client('bedrock-runtime', region_name='ap-southeast-1')

response = client.invoke_model(
    modelId='amazon.titan-text-premier-v1:0',
    body=json.dumps({
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": 2000,
            "temperature": 0.1,
            "topP": 0.9
        }
    })
)
```

**Cost:** ~$0.50 per 1M input tokens, $1.50 per 1M output tokens (very cheap)

### Option 3: Meta Llama 3.3 70B (Bedrock - No Approval)

**Model ID:** `meta.llama3-3-70b-instruct-v1:0`

**Why:**
- Open source, no approval required
- Good quality for general tasks
- 128K context window
- Cost-effective

**Limitations:**
- Not specialized for legal text
- May require more prompt engineering
- Less reliable for structured outputs

**Cost:** ~$0.99 per 1M input tokens, $0.99 per 1M output tokens

### Option 4: Mistral Large 2 (Bedrock - May Need Approval)

**Model ID:** `mistral.mistral-large-2407-v1:0`

**Why:**
- Very capable model
- 128K context window
- Good for European languages (less relevant for HK)

**Check if you have access:**
```bash
aws bedrock list-foundation-models \
  --region ap-southeast-1 \
  --query 'modelSummaries[?contains(modelId, `mistral`)]'
```

## Embeddings (No Change Needed)

### Amazon Titan Text Embeddings V2 ✅

**Model ID:** `amazon.titan-embed-text-v2:0`

**Why:**
- **No approval required** - Available immediately
- 1024 dimensions
- Good quality for semantic search
- Cost-effective
- Already in your infrastructure code

**You can use this right away!**

## Recommended Interim Architecture

### Setup A: Azure OpenAI + Bedrock Embeddings (Best)

```
Embeddings: Amazon Titan V2 (Bedrock) - No approval needed
Text Generation: GPT-4o (Azure OpenAI) - You have access
```

**Advantages:**
- Start immediately
- High quality for both tasks
- Proven technology
- Easy to migrate to Claude later

**Configuration:**
```bash
# .env
EMBEDDING_MODEL=bedrock-titan
HEADNOTE_MODEL=azure-gpt-4o

# For embeddings via Bedrock
AWS_REGION=ap-southeast-1
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret

# For text generation via Azure
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

### Setup B: All Bedrock (If you want to avoid Azure costs)

```
Embeddings: Amazon Titan V2 (Bedrock) - No approval needed
Text Generation: Amazon Titan Text Premier (Bedrock) - No approval needed
```

**Advantages:**
- Single provider (simpler)
- Lower costs
- All within AWS

**Disadvantages:**
- Lower quality for complex legal analysis
- May need more prompt engineering

## Migration Path

### Phase 1: Start Now (Today)
```
Embeddings: Amazon Titan V2 ✅
Text Generation: Azure GPT-4o ✅
```

### Phase 2: After Claude Approval (1-2 days)
```
Embeddings: Amazon Titan V2 ✅
Text Generation: Claude Opus 4.5 (Bedrock) 🔄 Migrate
```

**Migration is easy:**
Just change the model ID in your config - the infrastructure already supports Claude!

## How to Request Claude Access

While you're getting started with the interim setup:

1. **Go to AWS Console** → Bedrock → Model access
2. **Select region:** ap-southeast-1
3. **Request access for:**
   - Anthropic Claude Opus 4.5
   - Anthropic Claude 3.7 Sonnet
   - Anthropic Claude 3.5 Sonnet v2
4. **Approval time:** Usually instant to a few hours (sometimes up to 24 hours)

**Check your current access:**
```bash
aws bedrock list-foundation-models \
  --region ap-southeast-1 \
  --query 'modelSummaries[?contains(modelId, `anthropic`)]'
```

## Checking What's Available Now

**List all models you can use immediately:**
```bash
aws bedrock list-foundation-models \
  --region ap-southeast-1 \
  --query 'modelSummaries[?modelLifecycle.status==`ACTIVE`].[modelId,modelName]' \
  --output table
```

**Filter by provider:**
```bash
# Amazon models (usually no approval)
aws bedrock list-foundation-models \
  --region ap-southeast-1 \
  --query 'modelSummaries[?contains(modelId, `amazon`)].[modelId,modelName]' \
  --output table

# Meta models (usually no approval)
aws bedrock list-foundation-models \
  --region ap-southeast-1 \
  --query 'modelSummaries[?contains(modelId, `meta`)].[modelId,modelName]' \
  --output table
```

## Code Changes Needed

### For Azure OpenAI (Recommended Interim)

Update `batch/pipeline/summarizer.py`:

```python
from openai import AzureOpenAI
from config.settings import get_settings

def _get_azure_client():
    settings = get_settings()
    return AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version="2024-10-01-preview",
        azure_endpoint=settings.azure_openai_endpoint
    )

async def generate_headnote(case_id: str, *, max_chars: int = 150000) -> Optional[str]:
    # ... existing code to load case ...
    
    client = _get_azure_client()
    
    response = client.chat.completions.create(
        model=settings.azure_openai_deployment_name,  # e.g., "gpt-4o"
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=600,
        temperature=0.1
    )
    
    return response.choices[0].message.content
```

### For Titan Text Premier (All-Bedrock)

Update `batch/pipeline/summarizer.py`:

```python
import boto3
import json
from config.settings import get_settings

def _bedrock_client():
    settings = get_settings()
    return boto3.client("bedrock-runtime", region_name=settings.aws_region)

async def generate_headnote_titan(case_id: str) -> Optional[str]:
    # ... existing code to load case ...
    
    client = _bedrock_client()
    
    body = json.dumps({
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": 2000,
            "temperature": 0.1,
            "topP": 0.9,
            "stopSequences": []
        }
    })
    
    response = client.invoke_model(
        modelId="amazon.titan-text-premier-v1:0",
        body=body
    )
    
    result = json.loads(response['body'].read())
    return result['results'][0]['outputText']
```

## Performance Comparison

| Model | Quality | Speed | Cost | Context | Availability |
|-------|---------|-------|------|---------|--------------|
| **Azure GPT-4o** | ⭐⭐⭐⭐ | Fast | $$$ | 128K | ✅ Now |
| **Titan Premier** | ⭐⭐⭐ | Fast | $ | 32K | ✅ Now |
| **Llama 3.3 70B** | ⭐⭐⭐ | Medium | $$ | 128K | ✅ Now |
| **Claude Opus 4.5** | ⭐⭐⭐⭐⭐ | Medium | $$$$ | 200K | 🔄 Pending |

## Recommendation

**Start with Azure OpenAI GPT-4o** while you wait for Claude access:

1. **Today:** Deploy with Azure GPT-4o + Titan embeddings
2. **Request Claude access** in AWS Console
3. **Tomorrow:** Switch to Claude when approved (just change model ID)
4. **Compare:** Run both for a while to verify Claude is worth the cost

This gives you the best quality now and an easy migration path later!

## Questions?

- **"How long until Claude approval?"** Usually a few hours, max 24-48 hours
- **"Will I need to rewrite code?"** No, just change the model configuration
- **"Is GPT-4o good enough?"** Yes! It's excellent for legal text and structured outputs
- **"Should I use Titan to save money?"** Try GPT-4o first for quality, switch to Titan if budget-constrained

See [MODEL_RECOMMENDATIONS.md](MODEL_RECOMMENDATIONS.md) for the long-term strategy once Claude is available.
