# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Legal-AI is a legal research application for Hong Kong lawyers to discover relevant case law and legislation using semantic search powered by AI. The system scrapes legal materials from official Hong Kong sources, stores them in a Supabase/PostgreSQL database with vector embeddings, and provides search capabilities.

**Tech Stack**: Python 3.11+, Playwright, Supabase, PostgreSQL with pgvector, OpenAI/Anthropic APIs

## Repository Structure

This is a **monorepo** with the following major components:

```
Legal-AI/                  # Root repository
├── batch/                 # Web scrapers (Python)
│   ├── scrapers/         # Scraper implementations
│   │   ├── judiciary/    # Hong Kong Judiciary scraper
│   │   ├── elegislation/ # eLegislation scraper
│   │   └── utils/        # Citation parser, rate limiter
│   ├── jobs/             # Runnable jobs (scraping, ingestion)
│   ├── config/           # Settings (loads from root .env)
│   └── tests/            # pytest tests
├── supabase/             # Database schema and migrations
│   └── migrations/       # SQL migration files
├── www/                  # Future web frontend (not yet implemented)
└── .env                  # Environment config (in repo root, shared by all components)
```

**Important**: The `.env` file is located in the **repository root** (parent of `batch/`), not inside `batch/`. All components load configuration from the root `.env` file via `batch/config/settings.py`.

## Data Sources

1. **Hong Kong Judiciary** (legalref.judiciary.hk): Court judgments from 1947 onwards
   - **Note**: `robots.txt` disallows automated access - scrapers should only be used with proper authorization
   - Rate limiting: 3+ second delays between requests

2. **Hong Kong eLegislation** (elegislation.gov.hk): Legislation chapters and subsidiary legislation

## Common Commands

### Setup

```bash
# From batch/ directory
cd batch
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# Configure environment (edit .env in repo root)
cp ../.env.example ../.env
# Edit ../.env with your credentials
```

### Running Tests

```bash
# From batch/ directory
cd batch
source .venv/bin/activate
pytest                           # Run all tests
pytest tests/test_scrapers.py    # Run specific test file
pytest -v                        # Verbose output
pytest -k citation               # Run tests matching pattern
```

### Scraping

All scraper commands are run from the `batch/` directory using Python's `-m` flag:

```bash
cd batch
source .venv/bin/activate

# Judiciary scraper
python -m jobs.run_judiciary --courts CFA CA --year-from 2020
python -m jobs.run_judiciary --courts CFA --year-from 2024 --limit 10  # Testing
python -m jobs.run_judiciary --resume                                   # Resume from last state
python -m jobs.run_judiciary --no-headless --limit 5                    # Debug with visible browser

# eLegislation scraper
python -m jobs.run_elegislation
python -m jobs.run_elegislation --chapters 32 571
python -m jobs.run_elegislation --list-chapters
python -m jobs.run_elegislation --dry-run --limit 100

# Database ingestion
python -m jobs.ingest_jsonl --source judiciary --file output/judiciary/cases_20260104.jsonl
python -m jobs.ingest_jsonl --source elegislation --all
```

### Database

```bash
# From repo root
cd supabase

# Start local Supabase (Docker required)
supabase start

# Apply migrations
supabase db reset

# Stop local instance
supabase stop
```

The local Supabase instance uses these ports:
- API: 34321
- DB: 34322
- Studio: 34323

Connection string for local dev: `postgresql://postgres:postgres@127.0.0.1:34322/postgres`

## Architecture

### Scraper Architecture

All scrapers inherit from `BaseScraper` (in `batch/scrapers/base.py`) which provides:
- Rate limiting with configurable delays (default 3s)
- Concurrent request management via semaphore (max 2 concurrent)
- Persistent state for resume capability (stored in `./state/`)
- Automatic retries with exponential backoff
- Structured logging via structlog

**Key Design Pattern**: Scrapers are async context managers that:
1. Initialize Playwright browser on `__aenter__`
2. Load state from JSON file
3. Yield URLs via `get_index_urls()` iterator
4. Parse HTML via specialized parsers in `scrapers/{source}/parsers.py`
5. Save state on `__aexit__`

### Database Schema

Located in `supabase/migrations/`:
- `courts`: Hong Kong court hierarchy lookup
- `court_cases`: Court judgments with full text, embeddings (vector(3072) using text-embedding-3-large)
- `legislation`: Legislation chapters
- `legislation_sections`: Individual sections within legislation
- `legislation_schedules`: Schedules attached to legislation
- `ingestion_jobs`: Tracks file ingestion for idempotency

**Vector Search**: Uses pgvector extension with 3072-dimensional embeddings from OpenAI's `text-embedding-3-large` model.

### Citation Parser

The `scrapers/utils/citation_parser.py` module handles legal citation extraction and normalization:
- Hong Kong neutral citations: `[2024] HKCFA 15`
- Case numbers: `FACV 1/2024`
- UK and Australian citations also supported

### Rate Limiting

The `scrapers/utils/rate_limiter.py` implements token bucket algorithm for respectful scraping.

## Environment Variables

All components read from `.env` in the **repository root**:

```bash
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
OPENAI_API_KEY=sk-your-key

# Scraper settings (optional, have defaults)
SCRAPER_REQUEST_DELAY=3.0
SCRAPER_MAX_CONCURRENT=2
SCRAPER_HEADLESS=true

# AI Models (optional, have defaults)
EMBEDDING_MODEL=text-embedding-3-large
HEADNOTE_MODEL=claude-3-5-sonnet-20241022
```

## Output Files

Scrapers output to `batch/output/`:
- `batch/output/judiciary/cases_YYYYMMDD.jsonl` - Court cases
- `batch/output/elegislation/legislation_YYYYMMDD.jsonl` - Legislation

State files in `batch/state/`:
- `batch/state/judiciary_state.json` - Judiciary scraper resume state
- `batch/state/elegislation_state.json` - eLegislation scraper resume state

## Known Issues & Considerations

1. **Robots.txt**: The Judiciary website disallows automated access. Ensure proper authorization before running scrapers.

2. **Environment File Location**: The `.env` file is in the repository root, NOT in the `batch/` directory. The settings module explicitly looks for `../.env` (parent directory).

3. **Database Connection**: The ingestion job uses `asyncpg` to connect directly to PostgreSQL using `SUPABASE_DB_URL`, not the REST API.

4. **Heavy JavaScript Sites**: Both data sources require Playwright (headless browser) because they use client-side JavaScript rendering. Simple HTTP requests won't work.

## Coding Standards

This project follows coding standards documented in `.windsurf/rules/`. Key guidelines:

### Python Best Practices
- Follow PEP 8 style guidelines
- Use modular, reusable functions for scraping tasks
- Implement robust error handling with exponential backoff for retries
- Respect rate limiting (minimum 3 seconds between requests)
- Use asyncio for concurrent scraping operations
- Document all assumptions and methodologies

### Branching Strategy
- **Feature branches**: Create feature branches for new work (`feature/scraper-improvements`, `fix/citation-parser`)
- **`local` branch**: Integration branch for local development, merges from feature branches, deploys to E2E testing environment
- **`staging` branch**: Pre-production branch for manual testing, deploys to Staging environment
- **`main` branch**: Production-ready code, automatically deploys to Production environment

**Workflow**: `feature/* → local → staging → main`

See `.windsurf/rules/branching-strategy.md` for full Git/deployment workflow

## Development Workflow

1. **Adding New Scraper**: Create new directory under `batch/scrapers/`, inherit from `BaseScraper`, implement `get_index_urls()` and parsing logic
2. **Database Changes**: Add migrations to `supabase/migrations/` with timestamp prefix
3. **Testing**: Add tests to `batch/tests/`, use pytest-asyncio for async tests
4. **Configuration**: Add new settings to `batch/config/settings.py` and `.env.example`

## Production Deployment

The system is designed for deployment as systemd services on a VM (see `batch/README.md` for detailed steps):
- Two long-running scraper services (judiciary, elegislation)
- Automatic restart on failure
- Logs to `/var/log/legal-ai/`
- Uses dedicated `scraper` system user
