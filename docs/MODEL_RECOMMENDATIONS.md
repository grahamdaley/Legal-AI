# Model and Region Recommendations

This document provides recommendations for AI models and cloud regions for the Legal-AI project (as of January 2026).

## Cloud Regions

### AWS Region: `ap-southeast-1` (Singapore) ✅ Recommended

**Reasons:**
- **Proximity**: Closest major AWS region to Hong Kong (~2,500 km)
- **Latency**: ~10-20ms to Hong Kong
- **Bedrock Availability**: Full access to all Bedrock models including Claude Opus 4.5
- **Data Residency**: Complies with APAC data regulations
- **Reliability**: Mature region with excellent uptime

**Alternative:** `us-east-1` (Virginia)
- New models available first
- Higher latency (~200-250ms to Hong Kong)
- Better for testing latest features

### Azure Region: `eastasia` (Hong Kong) ✅ Recommended

**Reasons:**
- **Proximity**: Data center in Hong Kong
- **Latency**: <5ms locally
- **Data Residency**: Data stays in Hong Kong jurisdiction
- **Compliance**: Best for Hong Kong legal data

**Check availability:**
```bash
az cognitiveservices account list-skus \
  --kind OpenAI \
  --location eastasia
```

**Fallback:** `southeastasia` (Singapore)
- If `eastasia` doesn't have OpenAI services
- Similar latency to Hong Kong (~10-20ms)
- Broader service availability

## AWS Bedrock Models

### Text Generation (Headnotes, Summarization)

#### 1. Claude Opus 4.5 (Recommended) ✅

**Model ID:** `anthropic.claude-opus-4-5:0`

**Why:**
- Latest and most capable Claude model
- 200K token context window (ideal for long judgments)
- Superior reasoning and analysis
- Excellent for structured outputs (headnotes)
- Industry leader for legal/professional text

**Use For:**
- Generating structured headnotes
- Complex legal analysis
- Long document processing
- High-accuracy requirements

**Cost:** Higher per token, but better quality means fewer retries

#### 2. Claude 3.7 Sonnet (Balanced)

**Model ID:** `anthropic.claude-3-7-sonnet:0`

**Why:**
- Excellent balance of performance and cost
- Fast response times
- Good for batch processing
- Reliable and well-tested

**Use For:**
- High-volume batch processing
- Cost-sensitive workloads
- Production pipelines

#### 3. Claude 3.5 Sonnet v2 (Fast)

**Model ID:** `anthropic.claude-3-5-sonnet-20241022-v2:0`

**Why:**
- Fastest responses
- Lowest cost
- Good for simple tasks

**Use For:**
- Quick summaries
- Testing/development
- Simple text processing

### Embeddings (Semantic Search)

#### 1. Amazon Titan Text Embeddings V2 (Current) ✅

**Model ID:** `amazon.titan-embed-text-v2:0`

**Dimensions:** 1024

**Why:**
- Fully managed by AWS
- Good balance of quality and performance
- Cost-effective
- Well-integrated with Bedrock

**Use For:**
- General semantic search
- Document retrieval
- Current implementation

#### 2. Cohere Embed Multilingual V3 (Alternative for Bilingual)

**Model ID:** `cohere.embed-multilingual-v3`

**Dimensions:** 1024

**Why:**
- Excellent multilingual support
- Better for English + Chinese content
- Good for mixed-language legal texts

**Use For:**
- If dealing with bilingual judgments (English/Chinese)
- Cross-language search
- Hong Kong's bilingual legal system

**Consider If:**
- Your corpus includes significant Chinese language content
- Need to search across English and Chinese documents

## Azure OpenAI Models

### Embeddings

#### text-embedding-3-large (Current) ✅

**Deployment Name:** Your deployment name in Azure

**Dimensions:** 3072 (can be reduced to 1536 for pgvector)

**Why:**
- Highest quality OpenAI embeddings
- Excellent semantic understanding
- Well-suited for legal text
- Currently configured

**Use For:**
- High-precision semantic search
- Legal document retrieval
- Current implementation

**Note:** Reduce to 1536 dimensions in deployment config to match pgvector's efficient size

### Text Generation (if needed)

#### GPT-5.2 (Latest)

**Why:**
- Latest OpenAI model
- Structured, auditable outputs
- Enterprise-grade reliability
- Good tool use

**Use For:**
- Enterprise applications
- Structured data extraction
- Agent workflows

#### GPT-4o (Cost-Effective)

**Why:**
- Mature and reliable
- Lower cost than GPT-5.2
- Good performance

**Use For:**
- Production workloads
- Cost-sensitive applications

## Implementation Strategy

### Current Setup (Recommended)

```
Embeddings:
  - Primary: Amazon Titan V2 (Bedrock) → 1024 dims
  - Alternative: Azure OpenAI text-embedding-3-large → 1536 dims

Text Generation:
  - Primary: Claude Opus 4.5 (Bedrock) → Headnotes
  - Fallback: Claude 3.7 Sonnet (Bedrock) → Batch processing
```

### Database Configuration

**PostgreSQL pgvector:**
- Use 1024 dimensions for Bedrock embeddings
- Use 1536 dimensions for Azure OpenAI embeddings
- Store both if comparing quality

**Migration Path:**
```sql
-- Current: 3072 dimensions (Azure OpenAI default)
-- Recommended: 1536 dimensions (efficient, good quality)

ALTER TABLE court_cases 
  ALTER COLUMN embedding TYPE vector(1536);
```

## Cost Optimization

### Model Selection Strategy

1. **Development:** Use Claude 3.7 Sonnet (cheaper)
2. **Testing:** Small batch with Claude Opus 4.5
3. **Production:** Claude Opus 4.5 for final headnotes

### Batch Processing

- Use AWS Bedrock batch mode (50% cheaper)
- Use Azure OpenAI batch API (50% cheaper)
- Schedule during off-peak hours

### Embedding Strategy

- Generate embeddings once, reuse
- Cache common queries
- Use lower dimensions if acceptable quality

## Model Access

### Requesting Bedrock Model Access

Some models require explicit approval:

1. Go to AWS Bedrock Console
2. Navigate to "Model access"
3. Request access for:
   - Claude Opus 4.5
   - Claude 3.7 Sonnet
   - Amazon Titan Text Embeddings V2

**Processing Time:** Usually instant to a few hours

### Checking Available Models

```bash
# AWS Bedrock
aws bedrock list-foundation-models \
  --region ap-southeast-1 \
  --query 'modelSummaries[?contains(modelId, `anthropic`)]'

# Azure OpenAI
az cognitiveservices account list-models \
  --name your-openai-resource \
  --resource-group your-rg
```

## Performance Considerations

### Latency

**AWS Bedrock (ap-southeast-1):**
- To Hong Kong: ~10-20ms base latency
- Model inference: 50-500ms depending on length
- Total: 60-520ms per request

**Azure OpenAI (eastasia):**
- To Hong Kong: <5ms base latency
- Model inference: 100-1000ms depending on model
- Total: 105-1005ms per request

### Throughput

**Batch Processing:**
- AWS Bedrock: 1000s of requests/minute
- Azure OpenAI: Rate limits vary by deployment tier

**Real-time:**
- Use for interactive queries
- Cache results when possible

## Recommendations Summary

| Use Case | Provider | Model | Region |
|----------|----------|-------|--------|
| **Embeddings** | AWS Bedrock | Titan V2 | ap-southeast-1 |
| **Embeddings (Alt)** | Azure OpenAI | text-embedding-3-large | eastasia |
| **Headnotes (Best)** | AWS Bedrock | Claude Opus 4.5 | ap-southeast-1 |
| **Headnotes (Fast)** | AWS Bedrock | Claude 3.7 Sonnet | ap-southeast-1 |
| **Batch Processing** | AWS Bedrock | Any Claude | ap-southeast-1 |

## Next Steps

1. Update model IDs in `batch/config/settings.py`
2. Request model access in AWS Bedrock console
3. Test with small batch before full deployment
4. Monitor costs and adjust strategy
5. Consider A/B testing different models for quality comparison

## References

- [AWS Bedrock Models](https://aws.amazon.com/bedrock/model-choice/)
- [Azure AI Model Catalog](https://ai.azure.com/catalog/models)
- [Claude Opus 4.5 Documentation](https://www.anthropic.com/claude)
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
