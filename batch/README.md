# Legal AI - Batch Scrapers

Web scrapers for collecting Hong Kong legal data from official sources.

## Data Sources

| Source          | URL                     | Content         |
|-----------------|-------------------------|-----------------|
| **Judiciary**   | legalref.judiciary.hk   | Court judgments |
| **eLegislation**| elegislation.gov.hk     | Legislation     |

## Setup

### Prerequisites

- Python 3.11+
- Playwright browsers

### Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### Configuration

Copy the example environment file to the repo root and configure:

```bash
cp ../.env.example ../.env
# Edit ../.env with your credentials
```

Note: The `.env` file is located in the repo root directory (parent of `batch/`) so it can be shared by all components.

## Usage

### Judiciary Scraper

Scrapes court judgments from the Hong Kong Judiciary Legal Reference System.

```bash
# Scrape CFA and CA judgments from 2020 onwards
python -m jobs.run_judiciary --courts CFA CA --year-from 2020

# Scrape with limit (for testing)
python -m jobs.run_judiciary --courts CFA --year-from 2024 --limit 10

# Resume from last state
python -m jobs.run_judiciary --resume

# Resume from specific date
python -m jobs.run_judiciary --resume-from-date 2024-06-01

# Dry run (discover URLs only)
python -m jobs.run_judiciary --dry-run

# Run with visible browser (for debugging)
python -m jobs.run_judiciary --no-headless --limit 5
```

**Options:**

- `--courts`: Courts to scrape (CFA, CA, CFI, DC, FC, LT, LAB, SCT)
- `--year-from`: Start year (default: 2000)
- `--year-to`: End year (default: current year)
- `--limit`: Maximum cases to scrape
- `--resume`: Resume from last saved state
- `--resume-from-date`: Resume from specific date (YYYY-MM-DD)
- `--output-dir`: Output directory (default: ./output/judiciary)
- `--state-file`: State file path (default: ./state/judiciary_state.json)
- `--delay`: Request delay in seconds (default: 3.0)
- `--no-headless`: Show browser window
- `--dry-run`: Only discover URLs

### eLegislation Scraper

Scrapes legislation from the Hong Kong eLegislation database.

```bash
# Scrape all legislation
python -m jobs.run_elegislation

# Scrape specific chapters
python -m jobs.run_elegislation --chapters 32 32A 571

# List all available chapters
python -m jobs.run_elegislation --list-chapters

# Exclude subsidiary legislation
python -m jobs.run_elegislation --no-subsidiary

# Dry run
python -m jobs.run_elegislation --dry-run --limit 100
```

**Options:**

- `--chapters`: Specific chapters to scrape
- `--limit`: Maximum items to scrape
- `--include-subsidiary`: Include subsidiary legislation (default: True)
- `--no-subsidiary`: Exclude subsidiary legislation
- `--list-chapters`: List all available chapters and exit
- `--output-dir`: Output directory (default: ./output/elegislation)
- `--state-file`: State file path
- `--delay`: Request delay in seconds (default: 3.0)
- `--no-headless`: Show browser window
- `--dry-run`: Only discover URLs

## Output Format

### Judiciary Cases (JSONL)

```json
{
  "neutral_citation": "[2024] HKCFA 15",
  "case_number": "FACV 1/2024",
  "case_name": "HKSAR v. Chan Tai Man",
  "court": "HKCFA",
  "decision_date": "2024-06-15",
  "judges": ["Chief Justice Cheung", "Mr Justice Ribeiro PJ"],
  "parties": {"applicant": ["HKSAR"], "respondent": ["Chan Tai Man"]},
  "headnote": null,
  "catchwords": [],
  "full_text": "...",
  "word_count": 15000,
  "language": "en",
  "cited_cases": ["[2020] HKCFA 10", "[2019] HKCA 500"],
  "source_url": "https://legalref.judiciary.hk/...",
  "pdf_url": "https://legalref.judiciary.hk/.../judgment.pdf",
  "scraped_at": "2024-01-15T10:30:00Z"
}
```

### Legislation (JSONL)

```json
{
  "chapter_number": "Cap. 32",
  "title_en": "Evidence Ordinance",
  "title_zh": "證據條例",
  "type": "ordinance",
  "enactment_date": "1886-01-01",
  "status": "active",
  "sections": [
    {
      "section_number": "1",
      "title": "Short title",
      "content": "This Ordinance may be cited as the Evidence Ordinance."
    }
  ],
  "source_url": "https://www.elegislation.gov.hk/hk/cap32",
  "scraped_at": "2024-01-15T10:30:00Z"
}
```

## Database Ingestion

After scraping, ingest JSONL files into the Supabase database:

```bash
# Ingest a specific judiciary file
python -m jobs.ingest_jsonl --source judiciary --file output/judiciary/cases_20260104.jsonl

# Ingest a specific legislation file
python -m jobs.ingest_jsonl --source elegislation --file output/elegislation/legislation_20260104.jsonl

# Ingest all files for a source
python -m jobs.ingest_jsonl --source judiciary --all
python -m jobs.ingest_jsonl --source elegislation --all
```

**Options:**

- `--source`: Data source type (`judiciary` or `elegislation`)
- `--file`: Path to specific JSONL file to ingest
- `--all`: Process all JSONL files in the source output directory

**Database Tables:**

  | Table | Description |
  | ------- | ------------- |
  | `courts` | Hong Kong court hierarchy lookup |
  | `court_cases` | Court judgments with full text |
  | `legislation` | Legislation chapters |
  | `legislation_sections` | Individual sections within legislation |
  | `legislation_schedules` | Schedules attached to legislation |
  | `ingestion_jobs` | Tracks file ingestion for idempotency |

The ingestion job:

- Uses upsert (INSERT ... ON CONFLICT UPDATE) for idempotent re-runs
- Tracks processed files to skip already-ingested data
- Records success/failure counts per file

## State Management

The scrapers maintain state files to support resuming interrupted scrapes:

- `./state/judiciary_state.json` - Judiciary scraper state
- `./state/elegislation_state.json` - eLegislation scraper state

State includes:

- Last successful URL
- Last successful date
- Set of processed URLs
- Failed URLs with error messages
- Statistics (total, successful, failed, skipped)

## Rate Limiting

**Important:** Both scrapers implement rate limiting to be respectful of the source websites:

- Default delay: 3 seconds between requests
- Maximum concurrent requests: 2
- Automatic retry with exponential backoff on failures

The Judiciary website's robots.txt disallows automated access. Ensure you have proper authorization before running the scraper.

## Project Structure

```text
batch/
├── config/
│   ├── __init__.py
│   └── settings.py          # Environment settings
├── scrapers/
│   ├── __init__.py
│   ├── base.py               # Base scraper class
│   ├── judiciary/
│   │   ├── __init__.py
│   │   ├── config.py         # Court mappings
│   │   ├── parsers.py        # HTML/PDF parsing
│   │   └── scraper.py        # Judiciary scraper
│   ├── elegislation/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── parsers.py
│   │   └── scraper.py        # eLegislation scraper
│   └── utils/
│       ├── __init__.py
│       ├── citation_parser.py # Citation extraction
│       └── rate_limiter.py    # Rate limiting utilities
├── jobs/
│   ├── __init__.py
│   ├── run_judiciary.py      # Judiciary job runner
│   ├── run_elegislation.py   # eLegislation job runner
│   └── ingest_jsonl.py       # Database ingestion job
├── requirements.txt
└── README.md
```

## Deployment

For production deployment on a VM:

1. Set up a VM (e.g., DigitalOcean, AWS EC2) with Ubuntu
2. Install Python 3.11+ and dependencies
3. Configure environment variables
4. Set up systemd service for reliability
5. Configure cron for scheduled runs

### Step-by-Step Setup

#### 1. Prepare the Server

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python 3.11+ and required system dependencies
sudo apt install -y python3.11 python3.11-venv python3-pip git

# Install Playwright system dependencies
sudo apt install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
    libcairo2 libatspi2.0-0

# Create a dedicated user for the scraper
sudo useradd -r -m -s /bin/bash scraper
```

#### 2. Deploy the Application

```bash
# Create application directory
sudo mkdir -p /opt/legal-ai
sudo chown scraper:scraper /opt/legal-ai

# Switch to scraper user
sudo -u scraper -i

# Clone the repository
cd /opt/legal-ai
git clone https://github.com/your-org/Legal-AI.git .

# Create and activate virtual environment
cd batch
python3.11 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

#### 3. Configure Environment

```bash
# Copy and edit the environment file (in repo root)
cp /opt/legal-ai/.env.example /opt/legal-ai/.env
nano /opt/legal-ai/.env

# Set appropriate permissions
chmod 600 /opt/legal-ai/.env
```

#### 4. Create Log Directory

```bash
sudo mkdir -p /var/log/legal-ai
sudo chown scraper:scraper /var/log/legal-ai
```

#### 5. Install systemd Services

```bash
# Create the Judiciary scraper service
sudo tee /etc/systemd/system/legal-ai-judiciary.service << 'EOF'
[Unit]
Description=Legal AI Judiciary Scraper
After=network.target

[Service]
Type=simple
User=scraper
WorkingDirectory=/opt/legal-ai/batch
ExecStart=/opt/legal-ai/batch/.venv/bin/python -m jobs.run_judiciary --year-from 1947 --resume
Restart=on-failure
RestartSec=60
StandardOutput=append:/var/log/legal-ai/judiciary.log
StandardError=append:/var/log/legal-ai/judiciary.log

[Install]
WantedBy=multi-user.target
EOF

# Create the eLegislation scraper service
sudo tee /etc/systemd/system/legal-ai-elegislation.service << 'EOF'
[Unit]
Description=Legal AI eLegislation Scraper
After=network.target

[Service]
Type=simple
User=scraper
WorkingDirectory=/opt/legal-ai/batch
ExecStart=/opt/legal-ai/batch/.venv/bin/python -m jobs.run_elegislation --resume
Restart=on-failure
RestartSec=60
StandardOutput=append:/var/log/legal-ai/elegislation.log
StandardError=append:/var/log/legal-ai/elegislation.log

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable services
sudo systemctl daemon-reload
sudo systemctl enable legal-ai-judiciary.service
sudo systemctl enable legal-ai-elegislation.service
```

#### 6. Manage the Services

```bash
# Start a scraper
sudo systemctl start legal-ai-judiciary

# Check status
sudo systemctl status legal-ai-judiciary

# View logs
sudo journalctl -u legal-ai-judiciary -f
# Or view the log file directly
tail -f /var/log/legal-ai/judiciary.log

# Stop a scraper
sudo systemctl stop legal-ai-judiciary

# Restart after code updates
sudo systemctl restart legal-ai-judiciary
```

### Example Cron for Daily Updates

```cron
# Run incremental scrape daily at 2 AM
0 2 * * * cd /opt/legal-ai/batch && .venv/bin/python -m jobs.run_judiciary --year-from $(date +\%Y) --resume >> /var/log/legal-ai/judiciary.log 2>&1
```

## License

Proprietary - All rights reserved.
