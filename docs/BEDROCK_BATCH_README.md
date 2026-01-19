# Bedrock Batch API for Embeddings Generation

This document explains how to use the Bedrock Batch API to generate embeddings much faster than the sequential approach.

## Why Use Batch API?

**Sequential approach** (current):
- Processes ~5-7 seconds per case
- For 44,672 cases: **~3-5 days**

**Batch API approach**:
- Processes all cases in parallel
- For 160,000 embeddings: **~few hours**
- Up to **10-50x faster**

## Prerequisites

All infrastructure is already set up:
- ✅ S3 buckets created (`legal-ai-bedrock-batch-input-dev-us-east-1`, `legal-ai-bedrock-batch-output-dev-us-east-1`)
- ✅ IAM role with permissions (`legal-ai-bedrock-batch-role-dev`)
- ✅ AWS credentials configured in `.env`

## Quick Start

### Option 1: All-in-One (Recommended for Testing)

```bash
cd /opt/legal-ai/batch
source .venv/bin/activate

# Test with 100 cases
python -m jobs.generate_embeddings_batch run --limit 100

# Process all remaining cases (will submit job and exit)
python -m jobs.generate_embeddings_batch run

# Process all and wait for completion (may take hours)
python -m jobs.generate_embeddings_batch run --wait
```

### Option 2: Step-by-Step (Recommended for Production)

This gives you more control over each step:

#### Step 1: Export & Upload

```bash
# Export all cases without embeddings to JSONL and upload to S3
python -m jobs.generate_embeddings_batch export

# Or limit for testing:
python -m jobs.generate_embeddings_batch export --limit 1000
```

Output:
```
Local file: ./batch_output/embeddings-batch-20260118-123456.jsonl
S3 URI: s3://legal-ai-bedrock-batch-input-dev-us-east-1/embeddings/20260118-123456/input.jsonl
```

#### Step 2: Submit Batch Job

```bash
# Use the S3 URI from step 1
python -m jobs.generate_embeddings_batch submit --input-uri "s3://legal-ai-bedrock-batch-input-dev-us-east-1/embeddings/20260118-123456/input.jsonl"
```

Output:
```
Job submitted!
Job ARN: arn:aws:bedrock:us-east-1:898813627132:model-invocation-job/abc123...
Status: Submitted
```

#### Step 3: Monitor Status

```bash
# Check job status (replace with your actual ARN)
python -m jobs.generate_embeddings_batch status --job-arn "arn:aws:bedrock:us-east-1:898813627132:model-invocation-job/abc123..."
```

Output:
```
Job Status: InProgress  # or Completed, Failed, Stopped
Job Name: legal-ai-embeddings-20260118-123456
Input: s3://legal-ai-bedrock-batch-input-dev-us-east-1/embeddings/20260118-123456/input.jsonl
Output: s3://legal-ai-bedrock-batch-output-dev-us-east-1/embeddings/20260118-123456/output/
Created: 2026-01-18T12:34:56Z
```

**Note**: Batch jobs can take several hours. Keep checking until status is `Completed`.

#### Step 4: Download & Ingest Results

Once the job status is `Completed`:

```bash
python -m jobs.generate_embeddings_batch ingest --job-arn "arn:aws:bedrock:us-east-1:898813627132:model-invocation-job/abc123..."
```

Output:
```
Ingested 160000 embeddings
```

## Understanding the Workflow

### 1. Export Process
- Queries `court_cases` table for cases without embeddings in `case_embeddings_cohere`
- For each case, generates semantic chunks using existing `chunking.py` module
- Writes JSONL file with Bedrock-compatible format:
  ```json
  {"recordId": "case-{uuid}-chunk-0", "modelInput": {"inputText": "...", "dimensions": 1024, "normalize": true}}
  ```
- Uploads to S3 input bucket

### 2. Submit Process
- Creates a Bedrock batch inference job via `create_model_invocation_job` API
- Specifies:
  - Model: `amazon.titan-embed-text-v2:0`
  - Input: S3 URI of JSONL file
  - Output: S3 prefix for results
  - IAM role: Bedrock service role with S3 access

### 3. Bedrock Processing (Async)
- AWS Bedrock processes all records in parallel
- Generates 1024-dimensional embeddings for each chunk
- Writes output to S3 as JSONL files (`.jsonl.out`)
- No cost while waiting (only charged for embeddings generated)

### 4. Ingest Process
- Downloads output JSONL files from S3
- Parses each record to extract:
  - `recordId` → parse to get `case_id` and `chunk_index`
  - `modelOutput.embedding` → 1024-dimensional vector
- Inserts into `case_embeddings_cohere` table
- Uses `ON CONFLICT` to handle duplicates

## Important Notes

### Chunk Text and Chunk Type
The batch output does **not** include the original input text. The ingestion process inserts:
- `chunk_text`: `NULL`
- `chunk_type`: `"unknown"`

This is a trade-off for speed. If you need these fields populated:
1. Run a follow-up script to re-chunk cases and update the database
2. Or modify the export script to encode metadata in `recordId`

### Cost Considerations
- **Amazon Titan Text Embeddings V2**: ~$0.0001 per 1,000 tokens
- For 160,000 chunks × ~500 tokens average = 80M tokens
- **Estimated cost**: ~$8-10 for all remaining embeddings

### Limitations
- Maximum 20 concurrent batch jobs per region for Titan Text Embeddings V2
- No guaranteed SLA for batch jobs (typically hours, not days)
- Batch jobs require at least 1 record (no empty files)

## Troubleshooting

### "ValidationException: Your account is not authorized to perform this action"
This may indicate batch inference is not enabled for your account. Contact AWS Support to request access to Bedrock batch inference.

### "No output files found"
- Check that job status is `Completed` (not `InProgress`, `Failed`, or `Stopped`)
- Verify output S3 URI in job details
- Check S3 bucket permissions

### "Invalid recordId format"
The ingestion script expects recordIds in format: `case-{uuid}-chunk-{index}`. If you modified the export script, update the parsing logic in `ingest_embeddings()`.

## Migration from Sequential to Batch

If you're currently running the sequential script (`generate_embeddings_cases.py`):

1. **Stop the sequential job**
2. **Run batch export** to process all remaining cases
3. **Submit batch job** and wait for completion
4. **Ingest results**
5. **Verify** counts match: `SELECT COUNT(DISTINCT case_id) FROM case_embeddings_cohere`

Both scripts query the same way (cases without embeddings), so they're safe to run in sequence without duplicates.

## Performance Comparison

| Approach | Processing Time | Cost | Complexity |
|----------|----------------|------|------------|
| Sequential | 3-5 days | Same | Low |
| Batch API | Few hours | Same | Medium |

**Recommendation**: Use batch API for initial corpus indexing, use sequential for incremental updates.
