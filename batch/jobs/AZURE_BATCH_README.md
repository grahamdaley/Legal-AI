# Azure OpenAI Batch API for Headnote Generation

This document describes how to use Azure OpenAI's Global Batch API to generate headnotes for Hong Kong court cases at scale, with **50% cost savings** compared to standard real-time API calls.

## Overview

**Problem**: 118,498 court cases need AI-generated headnotes. Sequential processing would take 5-7 days and cost ~$178.

**Solution**: Azure OpenAI Global Batch API processes requests asynchronously in batches with:
- **50% lower cost** (~$89 vs ~$178)
- **24-hour target turnaround** (vs 5-7 days sequential)
- **Separate quota** (doesn't impact online workloads)
- **Same quality** as real-time API

## Prerequisites

### 1. Azure OpenAI GlobalBatch Deployment

You **must** have a `GlobalBatch` deployment type to use the batch API. Standard deployments won't work.

The Pulumi infrastructure already includes this:
- **Deployment name**: `gpt-4o-mini-batch`
- **Model**: `gpt-4o-mini` version `2024-07-18`
- **SKU**: `GlobalBatch` with 250K TPM capacity

To deploy/update the infrastructure:

```bash
cd /opt/legal-ai/infra/azure
pulumi up
```

### 2. Environment Configuration

Add to your `.env` file in the repository root:

```bash
# Azure OpenAI (required)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_API_VERSION=2024-10-01-preview

# Batch deployment name (matches Pulumi deployment)
AZURE_OPENAI_GPT4O_MINI_BATCH_DEPLOYMENT=gpt-4o-mini-batch

# Database connection
SUPABASE_DB_URL=postgresql://postgres:password@host:port/postgres
```

### 3. Python Dependencies

Ensure you have the OpenAI Python SDK:

```bash
cd /opt/legal-ai/batch
source .venv/bin/activate
pip install openai
```

## Usage

### Quick Start: Full Pipeline

Process all cases in one command (export, submit, wait, ingest):

```bash
cd /opt/legal-ai/batch
source .venv/bin/activate
python -m jobs.generate_headnotes_batch run --wait
```

This will:
1. Export cases without headnotes to JSONL
2. Upload to Azure OpenAI
3. Submit batch job
4. Wait for completion (polls every 60s)
5. Download results
6. Update `court_cases.headnote` column

### Step-by-Step Workflow

For more control, run each step separately:

#### Step 1: Export Cases to JSONL

```bash
python -m jobs.generate_headnotes_batch export --limit 100
```

This creates `output/headnotes/headnotes-batch-YYYYMMDD_HHMMSS.jsonl` with:
- One request per case
- Few-shot examples embedded in prompts
- Truncated judgment text (150K chars max)
- Automatic file splitting for >50,000 cases

#### Step 2: Submit Batch Job

```bash
python -m jobs.generate_headnotes_batch submit \
  --file output/headnotes/headnotes-batch-20260118_214500.jsonl \
  --name "Headnotes Jan 2026"
```

Output:
```
Batch ID: batch_abc123def456
Status: validating
```

Save the `batch_id` - you'll need it for the next steps.

#### Step 3: Monitor Status

```bash
python -m jobs.generate_headnotes_batch status --batch-id batch_abc123def456
```

Possible statuses:
- `validating`: Azure is validating the input file
- `in_progress`: Batch is being processed
- `finalizing`: Results are being prepared
- `completed`: Ready to download
- `failed`: Something went wrong (check error file)
- `cancelled`: Job was cancelled

Typical timeline: **4-12 hours** for 118,498 cases.

#### Step 4: Download and Ingest Results

Once status is `completed`:

```bash
python -m jobs.generate_headnotes_batch ingest --batch-id batch_abc123def456
```

This will:
1. Download the output JSONL file
2. Parse each headnote from the response
3. Update `court_cases.headnote` column
4. Log progress every 1000 records

## File Format

### Input JSONL Format

Each line is a JSON object following Azure OpenAI batch format:

```json
{
  "custom_id": "case-a1b2c3d4-e5f6-4789-g0h1-i2j3k4l5m6n7",
  "method": "POST",
  "url": "/chat/completions",
  "body": {
    "model": "gpt-4o-mini-batch",
    "messages": [
      {"role": "user", "content": "You are a senior law reporter...[prompt with few-shot examples and judgment text]"}
    ],
    "max_tokens": 600,
    "temperature": 0.1
  }
}
```

**Important**: 
- `custom_id` format: `case-<uuid>` (used to map results back to cases)
- `model` must be the GlobalBatch deployment name
- Maximum 50,000 requests per file
- Maximum 200 MB file size

### Output JSONL Format

Each line contains the result:

```json
{
  "id": "batch_req_xyz789",
  "custom_id": "case-a1b2c3d4-e5f6-4789-g0h1-i2j3k4l5m6n7",
  "response": {
    "status_code": 200,
    "request_id": "req_abc123",
    "body": {
      "id": "chatcmpl-xyz",
      "choices": [
        {
          "index": 0,
          "message": {
            "role": "assistant",
            "content": "Citation: [2024] HKCFA 15\nCourt: Court of Final Appeal...[generated headnote]"
          },
          "finish_reason": "stop"
        }
      ],
      "usage": {"prompt_tokens": 4521, "completion_tokens": 387, "total_tokens": 4908}
    }
  },
  "error": null
}
```

## Cost Estimation

Based on GPT-4o-mini pricing (50% batch discount):

| Metric | Value |
|--------|-------|
| Cases to process | 118,498 |
| Avg prompt size | ~4,500 tokens (few-shot + judgment) |
| Avg completion size | ~400 tokens |
| Total input tokens | ~533M |
| Total output tokens | ~47M |
| Standard cost | $0.150/1M input + $0.600/1M output = ~$108 |
| **Batch cost (50% off)** | ~**$54** |

**Note**: Actual costs depend on:
- Judgment length (150K char truncation)
- Few-shot example count (currently 3)
- Generated headnote verbosity

## Architecture Details

### Database Schema

Updates the `court_cases` table:

```sql
CREATE TABLE court_cases (
    id UUID PRIMARY KEY,
    neutral_citation TEXT,
    case_name TEXT,
    full_text TEXT,
    headnote TEXT,  -- Updated by batch ingestion
    updated_at TIMESTAMPTZ,
    ...
);
```

Query to find cases needing headnotes:

```sql
SELECT COUNT(*) 
FROM court_cases 
WHERE full_text IS NOT NULL 
  AND (headnote IS NULL OR headnote = '');
```

### Few-Shot Learning

The script fetches 3 example headnotes from `headnote_corpus` table and embeds them in every prompt. This ensures consistent formatting across all generated headnotes.

```sql
SELECT headnote_text 
FROM headnote_corpus 
ORDER BY created_at DESC 
LIMIT 3;
```

### Prompt Structure

Each prompt includes:
1. System instructions (headnote format, guidelines)
2. Few-shot examples (3 real headnotes from corpus)
3. Judgment text (truncated to 150K chars)

Total prompt size: ~4,500 tokens on average.

### Error Handling

The ingestion step handles:
- **Missing responses**: Skipped, logged
- **API errors**: Extracted from `error` field
- **Malformed JSON**: Caught and logged
- **Missing case IDs**: Validated before database update

Failed cases can be re-processed by re-exporting with the same query (only cases without headnotes).

## Comparison: Batch vs Sequential

| Aspect | Sequential (current) | Batch API |
|--------|---------------------|-----------|
| **Processing time** | 5-7 days | 4-12 hours |
| **Cost** | ~$108 | ~$54 (50% off) |
| **Quota impact** | Uses real-time quota | Separate batch quota |
| **Monitoring** | Per-case logging | Single batch status |
| **Error recovery** | Retry per case | Re-submit entire batch |
| **Concurrency** | Limited by TPM quota | Azure-managed parallelism |

## Limitations

1. **24-hour SLA**: Azure targets 24-hour turnaround but doesn't guarantee it
2. **No streaming**: Batch jobs return complete results, no incremental updates
3. **GlobalBatch deployment required**: Standard deployments won't work
4. **Maximum 100K requests per batch**: Need multiple batches for >100K cases
5. **No progress visibility**: Status is binary (in_progress/completed), no percentage
6. **24-hour expiration**: Unclaimed output files expire after 24 hours

## Troubleshooting

### Error: "OperationNotSupported"

```
The chatCompletion operation does not work with the specified model, gpt-4o-mini
```

**Cause**: Using a Standard deployment instead of GlobalBatch.

**Solution**: Ensure `AZURE_OPENAI_GPT4O_MINI_BATCH_DEPLOYMENT` points to a GlobalBatch deployment. Verify in Azure Portal or run `pulumi up` to create it.

### Error: "Invalid custom_id format"

**Cause**: `custom_id` doesn't match `case-<uuid>` pattern.

**Solution**: The script automatically formats custom IDs correctly. If you're manually creating JSONL, ensure format is `case-` followed by UUID (no extra hyphens).

### Error: "Exceeded maximum allowed records (50000)"

**Cause**: JSONL file has >50,000 requests.

**Solution**: The script automatically splits into multiple files. Submit each file as a separate batch job.

### Batch stuck in "validating" for >10 minutes

**Cause**: Malformed JSONL (invalid JSON, wrong format).

**Solution**: 
1. Check the error file ID from batch status
2. Download error file: `client.files.content(error_file_id)`
3. Fix issues and re-submit

### Zero headnotes ingested after completion

**Cause**: Output file has errors in all requests.

**Solution**:
1. Download output file manually and inspect
2. Check for common issues:
   - Deployment name mismatch
   - Token limit exceeded
   - Prompt formatting errors
3. Review error file ID from batch status

## Advanced Usage

### Testing with a Small Subset

```bash
python -m jobs.generate_headnotes_batch export --limit 150
python -m jobs.generate_headnotes_batch submit --file output/headnotes/headnotes-batch-*.jsonl
# Wait 10-15 minutes for small batch
python -m jobs.generate_headnotes_batch ingest --batch-id <batch_id>
```

### Multiple Batches in Parallel

Azure allows multiple concurrent batch jobs. To process 118K cases:

```bash
# Batch 1: First 50K
python -m jobs.generate_headnotes_batch export --limit 50000
# Submit and note batch_id_1

# Batch 2: Next 50K (modify export query to skip first 50K)
# ... similar process
```

### Monitoring Multiple Jobs

```bash
for batch_id in batch_abc123 batch_def456 batch_ghi789; do
    python -m jobs.generate_headnotes_batch status --batch-id $batch_id
done
```

## References

- [Azure OpenAI Batch API Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/batch)
- [OpenAI Batch API Reference](https://platform.openai.com/docs/guides/batch)
- [Azure OpenAI Deployment Types](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/concepts/deployment-types)
- [Pulumi Azure Cognitive Services](https://www.pulumi.com/registry/packages/azure-native/api-docs/cognitiveservices/)

## Next Steps

After completing headnote generation:

1. **Verify quality**: Sample random headnotes and review for accuracy
2. **Update embeddings**: Re-generate embeddings for cases with new headnotes
3. **Monitor costs**: Check Azure OpenAI usage dashboard
4. **Production deployment**: Add to systemd service or cron job for new cases
