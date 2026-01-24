# Re-scrape Judiciary Cases and Update Judges

This document describes the steps to re-fetch raw HTML for all court cases and re-parse the judges field using the improved parsing logic.

## Background

The original judge name parsing logic incorrectly fragmented judge names due to aggressive splitting on periods in judicial titles (e.g., "V.-P.", "J.A."). The parsing has been fixed in `batch/scrapers/judiciary/parsers.py`.

This process:

1. Re-fetches raw HTML from source URLs for all cases in the database
2. Saves HTML files locally for future re-parsing needs
3. Re-parses judges from the saved HTML using the improved logic
4. Updates **only** the `judges` field in the database (preserves embeddings, headnotes, etc.)

## Prerequisites

- Python 3.11+
- Access to the Supabase database (via `SUPABASE_DB_URL` environment variable)
- Network access to the Hong Kong Judiciary website

## Environment Setup

```bash
cd /path/to/Legal-AI/batch

# Create and activate virtual environment (if not already done)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Ensure environment variables are set
export SUPABASE_DB_URL="postgresql://..."
```

## Step 1: Re-fetch HTML for All Cases

This job queries the database for all court cases with source URLs, fetches the raw HTML, and saves it as gzipped files.

```bash
cd /path/to/Legal-AI/batch

# Preview what would be fetched (dry run)
python -m jobs.refetch_html --dry-run --limit 10

# Run the full re-fetch (this will take time due to rate limiting)
python -m jobs.refetch_html --delay 3.0

# Or resume if interrupted (skip cases with existing HTML files)
python -m jobs.refetch_html --delay 3.0 --skip-existing
```

### Options

| Option | Description |
|--------|-------------|
| `--limit N` | Process only N cases |
| `--dry-run`      | Show what would be fetched without actually fetching |
| `--skip-existing`| Skip cases that already have HTML files saved      |
| `--delay N`      | Delay between requests in seconds (default: 3.0)   |

### Output

HTML files are saved to:

```text
batch/output/judiciary/html/{first-2-chars-of-uuid}/{case_id}.html.gz
```

## Step 2: Re-parse Judges and Update Database

This job reads the saved HTML files, re-parses judges using the improved logic, and updates only the `judges` field in the database.

```bash
cd /path/to/Legal-AI/batch

# Preview sample changes (shows before/after for a few cases)
python -m jobs.reparse_judges --sample 10

# Dry run to see what would be updated
python -m jobs.reparse_judges --dry-run

# Run the actual update
python -m jobs.reparse_judges
```

### Command Options

| Option           | Description                                        |
| ---------------- | -------------------------------------------------- |
| `--limit N`      | Process only N cases                               |
| `--dry-run`      | Show what would be updated without making changes  |
| `--sample N`     | Show sample changes for N cases and exit           |

### What Gets Updated

- **Updated**: Only the `judges` JSONB field in `court_cases` table
- **Not touched**: `headnote`, `full_text`, embeddings, chunks, or any other fields

## Estimated Time

- **Re-fetch HTML**: ~3 seconds per case (due to rate limiting)
  - For 1000 cases: ~50 minutes
  - For 10000 cases: ~8 hours
- **Re-parse judges**: Fast, ~100 cases per second

## Troubleshooting

### Connection errors during re-fetch

The job will log failed URLs. You can re-run with `--skip-existing` to retry only failed cases.

### No HTML files found

Ensure Step 1 completed successfully. Check that files exist in `batch/output/judiciary/html/`.

### Database connection issues

Verify `SUPABASE_DB_URL` is set correctly and the database is accessible.

## File Locations

| File                                       | Purpose                                            |
| ------------------------------------------ | -------------------------------------------------- |
| `batch/jobs/refetch_html.py` | Job to re-fetch HTML from source URLs |
| `batch/jobs/reparse_judges.py` | Job to re-parse judges and update database |
| `batch/scrapers/judiciary/parsers.py` | Contains the fixed `_extract_judges_from_coram` function |
| `batch/scrapers/utils/html_storage.py` | Shared utility for HTML file storage |
| `batch/output/judiciary/html/` | Directory where HTML files are stored |
