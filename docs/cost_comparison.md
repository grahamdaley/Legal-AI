# Azure OpenAI Cost Comparison for Legal-AI

## Overview

This document compares the costs of different Azure OpenAI models for generating headnotes for 120,000 Hong Kong court judgements.

## Pricing (USD per 1M tokens)

| Model | Input (On-Demand) | Output (On-Demand) | Input (Batch) | Output (Batch) |
|-------|------------------|-------------------|---------------|----------------|
| **GPT-4o** | $2.50 | $10.00 | $1.25 | $5.00 |
| **GPT-4o-mini** | $0.15 | $0.60 | $0.075 | $0.30 |

**Batch API discount**: 50% off on-demand rates

## Cost Estimates for 120,000 Judgements

**Assumptions:**
- Average judgement length: 5,000 tokens (input)
- Average headnote length: 500 tokens (output)
- Total input: 600 million tokens
- Total output: 60 million tokens

### GPT-4o-mini (Batch Mode) ⭐ **RECOMMENDED**

```
Input:  600M tokens × $0.075/1M  = $45
Output:  60M tokens × $0.30/1M   = $18
----------------------------------------------
TOTAL:                             $63 USD
```

**Pros:**
- 93% cheaper than GPT-4o
- Very fast processing
- Good quality for summaries
- Already available (no approval needed)

**Cons:**
- Slightly less nuanced than GPT-4o for complex legal reasoning
- May miss subtle distinctions in very complex cases

### GPT-4o (Batch Mode)

```
Input:  600M tokens × $1.25/1M   = $750
Output:  60M tokens × $5.00/1M   = $300
----------------------------------------------
TOTAL:                            $1,050 USD
```

**Pros:**
- Higher quality reasoning
- Better at complex legal analysis
- More nuanced understanding

**Cons:**
- 15x more expensive than GPT-4o-mini
- Slower processing
- Not justified for most headnote tasks

### GPT-4o-mini (On-Demand)

```
Input:  600M tokens × $0.15/1M   = $90
Output:  60M tokens × $0.60/1M   = $36
----------------------------------------------
TOTAL:                            $126 USD
```

**Use case:** Real-time headnote generation for new judgements

### GPT-4o (On-Demand)

```
Input:  600M tokens × $2.50/1M   = $1,500
Output:  60M tokens × $10.00/1M  = $600
----------------------------------------------
TOTAL:                            $2,100 USD
```

**Use case:** Real-time generation where highest quality is critical

## Additional Costs

### Amazon Titan Text Embeddings V2 (for search)

```
600M tokens × $0.00011/1K (on-demand) = $66 USD
or
600M tokens × $0.000055/1K (batch, estimated) = $33 USD
```

### Azure Storage

- **Blob Storage**: ~$0.018 per GB/month
- **Operations**: Minimal (upload/download JSONL files)
- **Lifecycle policy**: Auto-deletes after 90 days

**Estimated**: $2-5/month

## Total Project Costs (One-Time Processing)

| Component | GPT-4o-mini | GPT-4o |
|-----------|------------|---------|
| Embeddings (Titan V2, batch) | $33 | $33 |
| Headnotes (Batch API) | $63 | $1,050 |
| Storage (first month) | $5 | $5 |
| **TOTAL** | **$101** | **$1,088** |

## Ongoing Costs

After initial processing, ongoing costs for incremental updates:

**Monthly additions** (assuming ~500 new judgements/month):

| Task | GPT-4o-mini | GPT-4o |
|------|------------|---------|
| New embeddings | $0.14 | $0.14 |
| New headnotes | $0.26 | $4.38 |
| Storage | $2 | $2 |
| **Monthly total** | **$2.40** | **$6.52** |

## Recommendation

### Use GPT-4o-mini for:
✅ Initial bulk processing (120K judgements)
✅ Automated daily/weekly updates
✅ Cost-sensitive deployments
✅ When "good enough" quality is acceptable

### Use GPT-4o for:
✅ High-stakes legal research
✅ Complex, precedent-setting cases
✅ When quality is more important than cost
✅ Manual/on-demand processing for specific cases

### Hybrid Approach:
1. **Bulk process with GPT-4o-mini** ($63) - saves $987
2. **Manually review** headnotes for precedent-setting cases
3. **Regenerate** critical cases with GPT-4o (~100 cases × $0.09 = $9)
4. **Total**: $72 vs $1,050 GPT-4o only (93% savings)

## Quality Considerations

### GPT-4o-mini is sufficient for:
- Extracting parties, dates, judges
- Summarizing holdings and outcomes
- Identifying legal issues and statutes
- Standard headnote generation

### GPT-4o is better for:
- Nuanced legal reasoning
- Complex multi-issue cases
- Identifying subtle precedential value
- Academic or research-grade analysis

## Testing Recommendation

Before committing to 120K judgements:

1. **Test sample** (100 cases) with GPT-4o-mini: $0.05
2. **Compare quality** with manual review
3. **If acceptable**, proceed with full batch
4. **If not**, try GPT-4o on same sample: $0.88
5. **Compare quality vs 17x cost increase**

## Conclusion

**For Legal-AI, GPT-4o-mini is the recommended choice:**

- ✅ 93% cost savings ($63 vs $1,050)
- ✅ Sufficient quality for headnote generation
- ✅ Faster processing (higher capacity available)
- ✅ Can always upgrade specific cases to GPT-4o later
- ✅ Total project cost: ~$100 USD (vs $1,100 with GPT-4o)

The quality difference doesn't justify the 15-17x cost increase for bulk headnote generation. Save GPT-4o for cases where it truly matters.
