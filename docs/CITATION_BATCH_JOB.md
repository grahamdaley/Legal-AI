# Citation Extraction Batch Job

This document describes how to run the citation extraction batch job to populate the `cited_cases` and `law_report_citations` columns in the `court_cases` table.

## Overview

The batch job extracts legal citations from the `full_text` of each case and stores them in:

- **`cited_cases`** - JSONB array of all citations found (neutral citations + law report citations)
- **`law_report_citations`** - JSONB array of law report citations that identify THIS case (found in header)

### Supported Citation Formats

| Format | Example | Description |
|--------|---------|-------------|
| HK Neutral | `[2024] HKCFI 123` | Hong Kong neutral citations |
| HKLR | `[1996] 2 HKLR 401` | Hong Kong Law Reports |
| HKLRD | `[2010] 1 HKLRD 100` | Hong Kong Law Reports & Digest |
| HKCFAR | `[2000] 3 HKCFAR 125` | HK Court of Final Appeal Reports |
| HKC | `[1995] 1 HKC 200` | Hong Kong Cases |

## Prerequisites

1. Database must have the migration `20260122143158_add_law_report_citations.sql` applied
2. Python environment with dependencies installed

## Running the Batch Job

### 1. Navigate to the batch directory

```bash
cd batch
```

### 2. Activate the virtual environment

```bash
source .venv/bin/activate
```

### 3. Ensure database connection is configured

The job uses `SUPABASE_DB_URL` from the environment. Check `.env` file or set it:

```bash
export SUPABASE_DB_URL="postgresql://postgres:password@host:port/postgres"
```

### 4. Run the job

**Full run (all cases):**
```bash
python -m jobs.reextract_citations
```

**Dry run (preview without changes):**
```bash
python -m jobs.reextract_citations --dry-run --limit 100
```

**Limited run (for testing):**
```bash
python -m jobs.reextract_citations --limit 1000
```

## Monitoring Progress

The job processes cases in batches of 500 and logs progress to stdout.

To check database progress:

```bash
python -c "
import asyncio, asyncpg
from config.settings import get_settings

async def check():
    conn = await asyncpg.connect(get_settings().supabase_db_url)
    row = await conn.fetchrow('''
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE jsonb_array_length(cited_cases) > 0) as with_citations,
            COUNT(*) FILTER (WHERE cited_cases::text LIKE '%HKLR%' OR cited_cases::text LIKE '%HKCFAR%') as with_law_reports
        FROM court_cases
        WHERE full_text IS NOT NULL
    ''')
    print(f'Total cases with full_text: {row[\"total\"]}')
    print(f'Cases with citations extracted: {row[\"with_citations\"]}')
    print(f'Cases citing HKLR/HKCFAR: {row[\"with_law_reports\"]}')
    await conn.close()

asyncio.run(check())
"
```

## Expected Results

For a database with ~118,000 cases:
- ~47,800 cases will have citations extracted (many judgments don't cite other cases)
- ~23,800 cases will cite HKLR/HKCFAR law reports
- Processing time: approximately 15-20 minutes

## Related Files

- `batch/jobs/reextract_citations.py` - The batch job script
- `batch/scrapers/utils/citation_parser.py` - Citation parsing logic
- `supabase/migrations/20260122143158_add_law_report_citations.sql` - Database migration

## Troubleshooting

### Job times out or stops

The job processes in batches to avoid timeouts. If it stops, you can safely re-run it - it will update all records (idempotent operation).

### No citations being extracted

Check that:
1. Cases have `full_text` populated
2. The citation parser patterns match the citation formats in your data
3. Database connection is working

### Testing the parser

```python
from scrapers.utils.citation_parser import parse_hk_citations, parse_hk_law_reports

text = "As held in [2020] HKCFI 123 and [1996] 2 HKLR 401..."
print(parse_hk_citations(text))
print(parse_hk_law_reports(text))
```
