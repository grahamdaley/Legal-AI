# Legal-AI

Legal-AI is a legal research system for Hong Kong practitioners that helps you **find relevant case law and legislation by meaning**, not only keywords.

The platform:

- Ingests judgments from official sources (HK Judiciary LRS) and legislation from eLegislation
- Splits documents into semantically meaningful chunks
- Generates embeddings for semantic search (Amazon Bedrock)
- Produces AI headnotes (configurable; Bedrock or alternative providers)
- Exposes a search API backed by Supabase/Postgres + pgvector
- Provides a Next.js web app for search and case detail views

## Documentation

- **Technical specification**: [`docs/specification.md`](docs/specification.md)
- **How it works (chunking/embeddings/headnotes)**: [`docs/how_it_works.md`](docs/how_it_works.md)
- **Phase 1 setup guide**: [`docs/phase_1_setup.md`](docs/phase_1_setup.md)

## Repo structure

- `www/`: Next.js (React) frontend
- `supabase/`: local dev + migrations + edge functions
- `batch/`: scrapers + ingestion + embedding/headnote pipelines
- `infra/`: Pulumi IaC for AWS (Bedrock) and Azure (optional)

## Quick start (local dev, Amazon Bedrock)

### Prerequisites

- **Docker** (for local Supabase)
- **Supabase CLI** (`supabase`)
- **Node.js** (for `www/`)
- **Python 3.11+** (for `batch/`)
- **AWS account with Bedrock enabled** and credentials configured

### 1) Configure environment

Create a local env file:

```bash
cp .env.example .env
```

At minimum, set:

- `AWS_REGION`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

Optional (recommended for local Supabase dev):

- `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY`

### 2) Start Supabase locally

From the repo root:

```bash
cd supabase
supabase start
supabase db reset
```

This repo’s local Supabase ports are configured in `supabase/config.toml` (API defaults to `http://127.0.0.1:34321`).

### 3) Run the batch pipeline (scrapers + embeddings)

```bash
cd batch
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Note: Scraping must respect the target sites’ access rules. See `docs/specification.md` for guidance.

### 3a) Initial batch processing (embeddings + headnotes)

These are the recommended **first-time backfill** jobs to populate:

- `case_embeddings_cohere` (semantic search embeddings) via **AWS Bedrock Batch API**
- `court_cases.headnote` via **Azure OpenAI Batch API**

They are designed to be run from the `batch/` directory with your virtualenv active.

#### Embeddings (AWS Bedrock Batch API)

Required `.env` values:

- `AWS_REGION`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `BEDROCK_BATCH_INPUT_BUCKET`
- `BEDROCK_BATCH_OUTPUT_BUCKET`
- `BEDROCK_BATCH_ROLE_ARN`

All-in-one (export, submit, wait, ingest):

```bash
cd batch
python -m jobs.generate_embeddings_batch run --wait
```

Step-by-step (useful if you want to submit in one session and ingest later):

```bash
cd batch
python -m jobs.generate_embeddings_batch export
python -m jobs.generate_embeddings_batch status --job-arn <job_arn>
python -m jobs.generate_embeddings_batch ingest --job-arn <job_arn>
```

#### Headnotes (Azure OpenAI Batch API)

Required `.env` values:

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_API_VERSION` (defaults to `2024-10-01-preview`)
- `AZURE_OPENAI_GPT4O_MINI_BATCH_DEPLOYMENT` (defaults to `gpt-4o-mini-batch`)

All-in-one (export, submit, wait, ingest):

```bash
cd batch
python -m jobs.generate_headnotes_batch run --wait
```

Step-by-step:

```bash
cd batch
python -m jobs.generate_headnotes_batch export
python -m jobs.generate_headnotes_batch status --batch-id <batch_id>
python -m jobs.generate_headnotes_batch ingest --batch-id <batch_id>
```

### 4) Run the web app

```bash
cd www
npm install
npm run dev
```

By default, the frontend reads Supabase connection settings from `.env` (see `.env.example` keys with the `NEXT_PUBLIC_` prefix).

## Model configuration (Bedrock)

The batch code loads model IDs from `batch/config/settings.py` and environment variables in `.env`.

- **Embeddings (Bedrock)**: default is `amazon.titan-embed-text-v2:0`
- **Headnotes (text generation)**:
  - Phase 1 can use non-Bedrock providers (see `docs/phase_1_setup.md`)
  - If you have Bedrock model approvals, set `headnote_model` to a Bedrock model ID (e.g. an `anthropic.*` model) in `batch/config/settings.py`

## Deployment

- **Frontend**: Netlify
- **Backend**: Supabase (Postgres + pgvector, Edge Functions, Auth, Storage)
- **Batch jobs**: self-hosted VM (recommended) or managed runner

## License

This project is licensed under the GNU General Public License v3.0. See [`LICENSE.md`](LICENSE.md).
