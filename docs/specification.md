# Legal Case Law Research Application - Technical Specification

**Version**: 1.0  
**Date**: January 2026  
**Status**: Draft

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [Data Sources](#3-data-sources)
4. [Database Design](#4-database-design)
5. [Web Scraper Architecture](#5-web-scraper-architecture)
6. [AI/ML Pipeline](#6-aiml-pipeline)
7. [API Specification](#7-api-specification)
8. [Frontend Application](#8-frontend-application)
9. [Workflow Integrations](#9-workflow-integrations)
10. [Security & Compliance](#10-security--compliance)
11. [Infrastructure & Deployment](#11-infrastructure--deployment)
12. [Implementation Roadmap](#12-implementation-roadmap)

---

## 1. Executive Summary

### 1.1 Purpose

This document specifies a legal research application enabling Hong Kong lawyers to discover relevant case law and legislation to support legal submissions. The system uses semantic search powered by AI to match natural language queries against a comprehensive database of Hong Kong legal materials.

### 1.2 Scope

**Phase 1 (MVP)**: Hong Kong jurisdiction
- Case law from the Judiciary (legalref.judiciary.hk)
- Legislation from eLegislation (elegislation.gov.hk)

**Future Phases**: Expansion to UK, USA, Australia, Canada, Singapore, New Zealand

### 1.3 Key Objectives

| Objective | Success Metric |
|-----------|----------------|
| Accurate case retrieval | >90% relevance in top 10 results |
| Fast search response | <2 seconds for standard queries |
| Comprehensive coverage | 100% of published HK judgments |
| Workflow integration | MS Word add-in adoption >50% of users |

---

## 2. System Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT APPLICATIONS                                 │
├──────────────┬──────────────┬──────────────┬──────────────┬─────────────────────┤
│   Web App    │  MS Word     │   Browser    │   Outlook    │   REST API          │
│   (React)    │  Add-in      │   Extension  │   Plugin     │   Clients           │
└──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┴──────────┬──────────┘
       └──────────────┴──────────────┴──────┬───────┴──────────────────┘
                                            │
                                            ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY (Supabase Edge Functions)                │
└───────────────────────────────────────────┬───────────────────────────────────────┘
                                            │
              ┌─────────────────────────────┼─────────────────────────────┐
              ▼                             ▼                             ▼
┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐
│      AI/ML SERVICES     │   │     CORE SERVICES       │   │    BACKGROUND JOBS      │
├─────────────────────────┤   ├─────────────────────────┤   ├─────────────────────────┤
│ • Query Understanding   │   │ • Search Orchestration  │   │ • Scraper Workers       │
│ • Embedding Generation  │   │ • Citation Resolution   │   │ • Embedding Pipeline    │
│ • Relevance Ranking     │   │ • User Management       │   │ • Index Maintenance     │
│ • Summarization         │   │ • Export Generation     │   │ • Data Sync             │
└───────────┬─────────────┘   └───────────┬─────────────┘   └───────────┬─────────────┘
            └─────────────────────────────┼─────────────────────────────┘
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER (Supabase/PostgreSQL)                     │
├─────────────────┬─────────────────┬─────────────────┬─────────────────────────────┤
│   Cases DB      │   Legislation   │   Vector Store  │   User Data & Analytics     │
│   (judgments)   │   DB            │   (pgvector)    │   (auth, searches, prefs)   │
└─────────────────┴─────────────────┴─────────────────┴─────────────────────────────┘
```

### 2.2 Technology Stack

| Component | Technology | Justification |
|-----------|------------|---------------|
| **Frontend** | Next.js 16 / React 19 / TypeScript / TailwindCSS / shadcn/ui | Modern, type-safe, SSR |
| **Backend API** | Supabase Edge Functions (Deno) | Serverless, integrated |
| **Database** | PostgreSQL 17 + pgvector | Vector search + relational |
| **Authentication** | Supabase Auth | Built-in OAuth, SSO |
| **File Storage** | Supabase Storage | PDF judgment storage |
| **AI/Embeddings** | OpenAI API (text-embedding-3-large) | Best embeddings |
| **LLM** | See Section 6.1 | Task-specific model selection |
| **Scraping** | Python + Playwright + Apify | JS rendering support |

---

## 3. Data Sources

### 3.1 Hong Kong Judiciary (legalref.judiciary.hk)

The Legal Reference System (LRS) is the official repository of Hong Kong court judgments.

| Data Type | Description | Volume (Est.) |
|-----------|-------------|---------------|
| **Judgments** | Full text of court decisions | ~150,000+ |
| **Neutral Citations** | Official case identifiers | All cases post-2000 |
| **Court Types** | CFA, CA, CFI, DC, FC, Tribunals | 15+ court types |
| **Date Range** | 1946 - Present | 80+ years |

#### Court Hierarchy

| Level | Court | Citation Code |
|-------|-------|---------------|
| 1 | Court of Final Appeal | HKCFA |
| 2 | Court of Appeal | HKCA |
| 3 | Court of First Instance | HKCFI |
| 4 | District Court | HKDC |
| 4 | Family Court | HKFC |
| 4 | Lands Tribunal | HKLT |
| 5 | Labour Tribunal | HKLBT |

#### Citation Formats

| Court | Format | Example |
|-------|--------|---------|
| CFA | [YYYY] HKCFA NNN | [2024] HKCFA 15 |
| CA | [YYYY] HKCA NNN | [2024] HKCA 234 |
| CFI | [YYYY] HKCFI NNN | [2024] HKCFI 1567 |

#### Access Considerations

> **Important**: The Judiciary website's robots.txt disallows automated access (`Disallow: /`).
> 
> **Recommended approaches**:
> 1. **Formal data access agreement** - Contact Judiciary IT for bulk data/API access
> 2. **Third-party licensed data** - Partner with existing legal data providers
> 3. **If authorized** - Implement strict rate limiting (3+ second delays)

### 3.2 Hong Kong e-Legislation (elegislation.gov.hk)

Official database of Hong Kong legislation maintained by the Department of Justice.

| Data Type | Description | Volume (Est.) |
|-----------|-------------|---------------|
| **Ordinances** | Primary legislation | ~600 chapters |
| **Subsidiary Legislation** | Regulations, rules | ~1,500+ items |
| **Historical Versions** | Point-in-time legislation | Multiple per cap |

#### Access Notes

- Sitemap available: `https://www.elegislation.gov.hk/sitemapindex.xml`
- Site uses heavy JavaScript rendering (requires Playwright)
- robots.txt allows specific search engine bots

---

## 4. Database Design

### 4.1 Core Tables

#### 4.1.1 Jurisdictions

```sql
CREATE TABLE jurisdictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(10) UNIQUE NOT NULL,           -- 'HK', 'UK', 'AU'
    name VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL,
    legal_system VARCHAR(50) NOT NULL,          -- 'common_law'
    default_citation_style VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 4.1.2 Courts

```sql
CREATE TABLE courts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction_id UUID NOT NULL REFERENCES jurisdictions(id),
    name VARCHAR(200) NOT NULL,
    abbreviation VARCHAR(20) NOT NULL,          -- 'CFA', 'CA'
    citation_code VARCHAR(20) NOT NULL,         -- 'HKCFA', 'HKCA'
    hierarchy_level INT NOT NULL,               -- 1 = highest
    parent_court_id UUID REFERENCES courts(id),
    UNIQUE(jurisdiction_id, abbreviation)
);
```

#### 4.1.3 Cases (Primary Table)

```sql
CREATE TABLE cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Identifiers
    neutral_citation VARCHAR(100) UNIQUE,       -- '[2024] HKCFA 15'
    case_number VARCHAR(100),                   -- 'FACV 1/2024'
    other_citations TEXT[],
    
    -- Relationships
    jurisdiction_id UUID NOT NULL REFERENCES jurisdictions(id),
    court_id UUID NOT NULL REFERENCES courts(id),
    
    -- Core metadata
    case_name TEXT NOT NULL,                    -- 'HKSAR v. Chan Tai Man'
    case_name_short VARCHAR(200),
    decision_date DATE,
    
    -- Parties & Judges
    parties JSONB,
    judges TEXT[],
    
    -- Content
    headnote TEXT,                              -- AI-generated summary
    catchwords TEXT[],
    full_text TEXT,
    word_count INT,
    
    -- Classification
    case_type VARCHAR(50),                      -- 'civil', 'criminal'
    subject_matter TEXT[],
    
    -- Original Source (for user verification and citation)
    source_url TEXT NOT NULL,                   -- Direct link to judgment on legalref.judiciary.hk
    source_pdf_url TEXT,                        -- Direct link to PDF if available
    pdf_storage_path TEXT,                      -- Local copy in Supabase Storage
    last_verified_at TIMESTAMPTZ,               -- When source URL was last confirmed valid
    language VARCHAR(10) DEFAULT 'en',
    
    -- Processing status
    status VARCHAR(20) DEFAULT 'pending',
    embedding_status VARCHAR(20) DEFAULT 'pending',
    
    -- Full-text search
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(case_name, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(headnote, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(full_text, '')), 'C')
    ) STORED,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cases_jurisdiction ON cases(jurisdiction_id);
CREATE INDEX idx_cases_court ON cases(court_id);
CREATE INDEX idx_cases_decision_date ON cases(decision_date DESC);
CREATE INDEX idx_cases_search ON cases USING GIN(search_vector);
```

#### 4.1.4 Case Embeddings (Vector Store)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE case_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_type VARCHAR(20) DEFAULT 'body',      -- 'headnote', 'body', 'ratio'
    embedding vector(3072),                     -- text-embedding-3-large
    token_count INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(case_id, chunk_index)
);

CREATE INDEX idx_case_embeddings_vector ON case_embeddings 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

#### 4.1.5 Case Citations

```sql
CREATE TABLE case_citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    citing_case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    cited_case_id UUID REFERENCES cases(id) ON DELETE SET NULL,
    cited_citation_text VARCHAR(200),           -- Raw text if unresolved
    citation_context TEXT,
    treatment VARCHAR(50),                      -- 'followed', 'distinguished'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(citing_case_id, cited_case_id)
);
```

#### 4.1.6 Legislation Tables

```sql
CREATE TABLE legislation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction_id UUID NOT NULL REFERENCES jurisdictions(id),
    chapter_number VARCHAR(20) NOT NULL,        -- 'Cap. 32'
    title_en TEXT NOT NULL,
    title_zh TEXT,
    type VARCHAR(50) NOT NULL,                  -- 'ordinance', 'regulation'
    enactment_date DATE,
    status VARCHAR(20) DEFAULT 'active',
    
    -- Original Source (for user verification and citation)
    source_url TEXT NOT NULL,                   -- Direct link on elegislation.gov.hk
    source_pdf_url TEXT,                        -- PDF version if available
    last_verified_at TIMESTAMPTZ,               -- When source URL was last confirmed valid
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(jurisdiction_id, chapter_number)
);

CREATE TABLE legislation_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legislation_id UUID NOT NULL REFERENCES legislation(id) ON DELETE CASCADE,
    section_number VARCHAR(50) NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    version_date DATE,
    
    -- Original Source (for user verification and citation)
    source_url TEXT,                            -- Direct link to section on elegislation.gov.hk
    
    embedding_status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE legislation_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id UUID NOT NULL REFERENCES legislation_sections(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(3072),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(section_id, chunk_index)
);
```

#### 4.1.7 User Tables

```sql
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name VARCHAR(200),
    firm_name VARCHAR(200),
    subscription_tier VARCHAR(20) DEFAULT 'free',
    preferences JSONB DEFAULT '{"default_jurisdiction": "HK"}'::jsonb,
    searches_this_month INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE user_searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    query_embedding vector(3072),
    filters JSONB,
    results_count INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE user_collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE collection_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES user_collections(id) ON DELETE CASCADE,
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE,
    legislation_id UUID REFERENCES legislation(id) ON DELETE CASCADE,
    notes TEXT,
    added_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.2 Database Functions

#### Semantic Search Function

```sql
CREATE OR REPLACE FUNCTION search_cases_semantic(
    query_embedding vector(3072),
    match_threshold DECIMAL DEFAULT 0.7,
    match_count INT DEFAULT 20,
    filter_jurisdiction UUID DEFAULT NULL,
    filter_courts UUID[] DEFAULT NULL,
    filter_date_from DATE DEFAULT NULL,
    filter_date_to DATE DEFAULT NULL
)
RETURNS TABLE (
    case_id UUID,
    neutral_citation VARCHAR,
    case_name TEXT,
    decision_date DATE,
    court_name VARCHAR,
    headnote TEXT,
    similarity DECIMAL,
    matching_chunk TEXT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT ON (c.id)
        c.id, c.neutral_citation, c.case_name, c.decision_date,
        ct.name, c.headnote,
        (1 - (ce.embedding <=> query_embedding))::DECIMAL,
        ce.chunk_text
    FROM case_embeddings ce
    JOIN cases c ON c.id = ce.case_id
    JOIN courts ct ON ct.id = c.court_id
    WHERE 
        (1 - (ce.embedding <=> query_embedding)) > match_threshold
        AND (filter_jurisdiction IS NULL OR c.jurisdiction_id = filter_jurisdiction)
        AND (filter_courts IS NULL OR c.court_id = ANY(filter_courts))
        AND (filter_date_from IS NULL OR c.decision_date >= filter_date_from)
        AND (filter_date_to IS NULL OR c.decision_date <= filter_date_to)
        AND c.status = 'processed'
    ORDER BY c.id, (1 - (ce.embedding <=> query_embedding)) DESC
    LIMIT match_count;
END;
$$;
```

#### Hybrid Search Function

```sql
CREATE OR REPLACE FUNCTION search_cases_hybrid(
    search_query TEXT,
    query_embedding vector(3072),
    semantic_weight DECIMAL DEFAULT 0.7,
    match_count INT DEFAULT 20
)
RETURNS TABLE (
    case_id UUID,
    neutral_citation VARCHAR,
    case_name TEXT,
    combined_score DECIMAL
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    WITH semantic AS (
        SELECT c.id, MAX(1 - (ce.embedding <=> query_embedding)) AS score
        FROM case_embeddings ce JOIN cases c ON c.id = ce.case_id
        GROUP BY c.id ORDER BY score DESC LIMIT match_count * 2
    ),
    fulltext AS (
        SELECT c.id, ts_rank(c.search_vector, websearch_to_tsquery('english', search_query)) AS score
        FROM cases c
        WHERE c.search_vector @@ websearch_to_tsquery('english', search_query)
        ORDER BY score DESC LIMIT match_count * 2
    )
    SELECT c.id, c.neutral_citation, c.case_name,
        (COALESCE(s.score,0) * semantic_weight + COALESCE(f.score,0) * (1-semantic_weight))::DECIMAL
    FROM semantic s FULL OUTER JOIN fulltext f ON s.id = f.id
    JOIN cases c ON c.id = COALESCE(s.id, f.id)
    ORDER BY 4 DESC LIMIT match_count;
END;
$$;
```

### 4.3 Row-Level Security

```sql
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_collections ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile" ON user_profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can view own searches" ON user_searches
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can view own/public collections" ON user_collections
    FOR SELECT USING (auth.uid() = user_id OR is_public = true);
```

---

## 5. Web Scraper Architecture

### 5.1 Overview

The scraping system is designed to:
- Handle JavaScript-rendered content (SPA sites)
- Respect rate limits (3+ seconds between requests)
- Run incrementally (daily updates)
- Be resilient to failures

### 5.2 Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Runtime** | Python 3.11+ | Primary language |
| **Browser** | Playwright | JS rendering |
| **HTTP Client** | httpx / aiohttp | Async requests |
| **HTML Parsing** | BeautifulSoup4 / lxml | DOM parsing |
| **PDF** | PyMuPDF / pdfplumber | PDF text extraction |
| **Task Queue** | Celery / Apify | Job distribution |
| **Cloud** | Apify (optional) | Managed infrastructure |

### 5.3 Project Structure

```
batch/
├── scrapers/
│   ├── __init__.py
│   ├── base.py                    # Base scraper class
│   ├── judiciary/
│   │   ├── scraper.py             # Judiciary scraper
│   │   ├── parsers.py             # HTML/PDF parsing
│   │   └── config.py              # Court mappings
│   ├── elegislation/
│   │   ├── scraper.py             # eLegislation scraper
│   │   └── parsers.py             # HTML parsing
│   └── utils/
│       ├── browser.py             # Playwright helpers
│       ├── rate_limiter.py        # Request throttling
│       └── citation_parser.py     # HK citation regex
├── pipeline/
│   ├── embeddings.py              # OpenAI embeddings
│   ├── summarizer.py              # AI headnote generation
│   └── db_writer.py               # Supabase insertion
├── jobs/
│   ├── full_scrape.py             # Full historical scrape
│   └── incremental_scrape.py      # Daily updates
├── requirements.txt
└── README.md
```

### 5.4 Base Scraper Class

```python
# batch/scrapers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator, Optional
import asyncio
from playwright.async_api import async_playwright, Browser, Page

@dataclass
class ScrapedItem:
    source_url: str
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    raw_html: Optional[str] = None

@dataclass
class ScraperConfig:
    base_url: str
    request_delay: float = 3.0
    max_concurrent: int = 2
    timeout: int = 60000
    max_retries: int = 3
    headless: bool = True

class BaseScraper(ABC):
    def __init__(self, config: ScraperConfig):
        self.config = config
        self._browser: Optional[Browser] = None
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self._last_request = 0.0
    
    async def __aenter__(self):
        pw = await async_playwright().start()
        self._browser = await pw.chromium.launch(headless=self.config.headless)
        return self
    
    async def __aexit__(self, *args):
        if self._browser:
            await self._browser.close()
    
    async def _rate_limit(self):
        now = asyncio.get_event_loop().time()
        wait = self.config.request_delay - (now - self._last_request)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request = asyncio.get_event_loop().time()
    
    async def fetch_page(self, url: str) -> Optional[str]:
        async with self._semaphore:
            await self._rate_limit()
            ctx = await self._browser.new_context()
            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until='networkidle', timeout=self.config.timeout)
                return await page.content()
            finally:
                await page.close()
                await ctx.close()
    
    @abstractmethod
    async def get_index_urls(self) -> AsyncIterator[str]:
        pass
    
    @abstractmethod
    async def scrape_item(self, url: str) -> Optional[ScrapedItem]:
        pass
```

### 5.5 Judiciary Scraper

```python
# batch/scrapers/judiciary/scraper.py
import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, AsyncIterator
from bs4 import BeautifulSoup
from ..base import BaseScraper, ScrapedItem, ScraperConfig

@dataclass
class JudiciaryCase(ScrapedItem):
    neutral_citation: Optional[str] = None
    case_number: Optional[str] = None
    case_name: Optional[str] = None
    court: Optional[str] = None
    decision_date: Optional[date] = None
    judges: List[str] = field(default_factory=list)
    headnote: Optional[str] = None
    full_text: Optional[str] = None

COURTS = ['HKCFA', 'HKCA', 'HKCFI', 'HKDC', 'HKFC', 'HKLT']

class JudiciaryScraper(BaseScraper):
    """Scraper for HK Judiciary Legal Reference System"""
    
    BASE_URL = "https://legalref.judiciary.hk"
    
    def __init__(self):
        super().__init__(ScraperConfig(
            base_url=self.BASE_URL,
            request_delay=3.0,
            max_concurrent=2,
        ))
    
    async def get_index_urls(self, courts: List[str] = None, 
                              year_from: int = 2000) -> AsyncIterator[str]:
        courts = courts or COURTS
        for court in courts:
            for year in range(year_from, 2027):
                # Navigate search, yield judgment URLs
                # Implementation depends on exact site structure
                pass
    
    async def scrape_item(self, url: str) -> Optional[JudiciaryCase]:
        html = await self.fetch_page(url)
        if not html:
            return None
        return self._parse_judgment(html, url)
    
    def _parse_judgment(self, html: str, url: str) -> JudiciaryCase:
        soup = BeautifulSoup(html, 'lxml')
        
        # Extract citation - pattern: [YYYY] HKXXX NNN
        citation_pattern = r'\[(\d{4})\]\s+(HK[A-Z]+)\s+(\d+)'
        citation_match = re.search(citation_pattern, html)
        
        case = JudiciaryCase(source_url=url, raw_html=html)
        
        if citation_match:
            case.neutral_citation = citation_match.group(0)
            case.court = citation_match.group(2)
        
        # Extract case name from title
        title = soup.find('title')
        if title:
            case.case_name = title.get_text(strip=True)
        
        # Extract full text
        body = soup.find('body')
        if body:
            case.full_text = body.get_text(separator='\n', strip=True)
        
        return case
```

### 5.6 eLegislation Scraper

```python
# batch/scrapers/elegislation/scraper.py
from dataclasses import dataclass, field
from typing import List, Optional, AsyncIterator
from bs4 import BeautifulSoup
from ..base import BaseScraper, ScrapedItem, ScraperConfig

@dataclass
class LegislationItem(ScrapedItem):
    chapter_number: Optional[str] = None
    title_en: Optional[str] = None
    title_zh: Optional[str] = None
    type: str = 'ordinance'
    sections: List[dict] = field(default_factory=list)

class ELegislationScraper(BaseScraper):
    """Scraper for HK eLegislation"""
    
    BASE_URL = "https://www.elegislation.gov.hk"
    SITEMAP_URL = f"{BASE_URL}/sitemapindex.xml"
    
    def __init__(self):
        super().__init__(ScraperConfig(
            base_url=self.BASE_URL,
            request_delay=3.0,
            max_concurrent=2,
        ))
    
    async def get_index_urls(self) -> AsyncIterator[str]:
        # Parse sitemap for chapter URLs
        sitemap = await self.fetch_page(self.SITEMAP_URL)
        if sitemap:
            soup = BeautifulSoup(sitemap, 'xml')
            for loc in soup.find_all('loc'):
                url = loc.get_text()
                if '/hk/cap' in url.lower():
                    yield url
    
    async def scrape_item(self, url: str) -> Optional[LegislationItem]:
        html = await self.fetch_page(url)
        if not html:
            return None
        return self._parse_legislation(html, url)
    
    def _parse_legislation(self, html: str, url: str) -> LegislationItem:
        soup = BeautifulSoup(html, 'lxml')
        item = LegislationItem(source_url=url, raw_html=html)
        
        # Extract chapter number from URL or content
        # e.g., /hk/cap32 -> Cap. 32
        if '/cap' in url.lower():
            cap_match = re.search(r'/cap(\d+)', url.lower())
            if cap_match:
                item.chapter_number = f"Cap. {cap_match.group(1)}"
        
        # Extract title
        title_el = soup.find('h1', class_='title')
        if title_el:
            item.title_en = title_el.get_text(strip=True)
        
        return item
```

### 5.7 Using Apify (Optional)

Apify provides managed scraping infrastructure with built-in proxy rotation, scheduling, and monitoring.

```python
# batch/apify/judiciary-actor/src/main.py
from apify import Actor
from playwright.async_api import async_playwright

async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}
        courts = input_data.get('courts', ['HKCFA', 'HKCA'])
        year_from = input_data.get('year_from', 2020)
        
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            
            # Scraping logic here
            # Use Actor.push_data() to store results
            # Use Actor.set_value() for state persistence
            
            await browser.close()
```

**Apify actor.json:**
```json
{
    "actorSpecification": 1,
    "name": "hk-judiciary-scraper",
    "title": "HK Judiciary Judgment Scraper",
    "version": "1.0",
    "input": {
        "courts": { "type": "array", "default": ["HKCFA", "HKCA"] },
        "year_from": { "type": "integer", "default": 2020 }
    }
}
```

### 5.8 Citation Parser

```python
# batch/scrapers/utils/citation_parser.py
import re
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ParsedCitation:
    full_citation: str
    year: int
    court: str
    number: int
    jurisdiction: str = 'HK'

HK_CITATION_PATTERN = re.compile(
    r'\[(\d{4})\]\s*(HK(?:CFA|CA|CFI|DC|FC|LT|LAB|SCT))\s*(\d+)',
    re.IGNORECASE
)

UK_CITATION_PATTERN = re.compile(
    r'\[(\d{4})\]\s*(\d+)?\s*(AC|QB|WLR|All ER|UKSC|UKHL|EWCA)',
    re.IGNORECASE
)

def parse_hk_citations(text: str) -> List[ParsedCitation]:
    """Extract all HK citations from text"""
    citations = []
    for match in HK_CITATION_PATTERN.finditer(text):
        citations.append(ParsedCitation(
            full_citation=match.group(0),
            year=int(match.group(1)),
            court=match.group(2).upper(),
            number=int(match.group(3)),
            jurisdiction='HK'
        ))
    return citations

def normalize_citation(citation: str) -> str:
    """Normalize citation format"""
    match = HK_CITATION_PATTERN.match(citation.strip())
    if match:
        return f"[{match.group(1)}] {match.group(2).upper()} {match.group(3)}"
    return citation.strip()
```

### 5.9 Pipeline Jobs

```python
# batch/jobs/incremental_scrape.py
import asyncio
from datetime import datetime, timedelta
from supabase import create_client
from scrapers.judiciary import JudiciaryScraper
from pipeline.embeddings import generate_embeddings
from pipeline.db_writer import upsert_case

async def run_incremental():
    """Daily incremental scrape for new judgments"""
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Get last scrape date
    result = supabase.table('cases').select('decision_date').order('decision_date', desc=True).limit(1).execute()
    last_date = result.data[0]['decision_date'] if result.data else '2020-01-01'
    
    async with JudiciaryScraper() as scraper:
        async for url in scraper.get_index_urls(year_from=int(last_date[:4])):
            case = await scraper.scrape_item(url)
            if case and case.decision_date and case.decision_date > last_date:
                # Generate embeddings
                embeddings = await generate_embeddings(case.full_text)
                
                # Save to database
                await upsert_case(supabase, case, embeddings)

if __name__ == '__main__':
    asyncio.run(run_incremental())
```

---

## 6. AI/ML Pipeline

### 6.1 LLM Selection

Rather than hardcoding specific model versions, select models based on these criteria and evaluate the **latest available versions** at implementation time.

#### Selection Criteria

| Criterion | Requirement |
|-----------|-------------|
| **Context window** | 50K+ tokens for long judgments |
| **Accuracy** | Low hallucination rate for legal summarization |
| **Latency** | <3s response for query understanding |
| **Cost** | Balance quality vs. volume requirements |
| **Multilingual** | English + Traditional Chinese support |

#### Current Recommendations (January 2026)

| Use Case | Recommended Model | Rationale |
|----------|-------------------|----------|
| **Query Understanding** | GPT-4o-mini (or latest equivalent) | Fast, cost-effective, sufficient accuracy |
| **Headnote Generation** | Claude 3.5 Sonnet (or latest equivalent) | Better legal reasoning, lower hallucination |
| **Citation Extraction** | GPT-4o-mini | Structured output, fast |
| **Complex Legal Analysis** | Claude Opus / GPT-4 class | When accuracy is critical |

#### Evaluation Process

At implementation, benchmark latest models from OpenAI, Anthropic, and Google on a sample of 100 HK judgments measuring:
- Headnote accuracy vs. official headnotes (where available)
- Citation extraction precision/recall
- Query understanding relevance scoring

### 6.2 Embedding Generation

```python
# batch/pipeline/embeddings.py
from openai import OpenAI
from typing import List
import tiktoken

client = OpenAI()
EMBEDDING_MODEL = "text-embedding-3-large"
MAX_TOKENS = 8000
CHUNK_OVERLAP = 200

def chunk_text(text: str, max_tokens: int = MAX_TOKENS) -> List[str]:
    """Split text into chunks that fit within token limit"""
    enc = tiktoken.encoding_for_model("gpt-4")
    tokens = enc.encode(text)
    
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(enc.decode(chunk_tokens))
        start = end - CHUNK_OVERLAP if end < len(tokens) else end
    
    return chunks

async def generate_embeddings(text: str) -> List[dict]:
    """Generate embeddings for text chunks"""
    chunks = chunk_text(text)
    results = []
    
    for i, chunk in enumerate(chunks):
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=chunk
        )
        results.append({
            'chunk_index': i,
            'chunk_text': chunk,
            'embedding': response.data[0].embedding,
            'token_count': response.usage.total_tokens
        })
    
    return results
```

### 6.3 AI Summarization

```python
# batch/pipeline/summarizer.py
import anthropic
from config.settings import HEADNOTE_MODEL

client = anthropic.Anthropic()

HEADNOTE_PROMPT = """Generate a concise legal headnote (max 300 words) for the following judgment.
Include: (1) Key legal issues, (2) Holdings, (3) Significant legal principles established.
Format as a single paragraph suitable for legal research.

Judgment:
{text}
"""

async def generate_headnote(judgment_text: str, model: str = HEADNOTE_MODEL) -> str:
    """Generate AI headnote for a judgment.
    
    Args:
        judgment_text: Full judgment text
        model: Model identifier (default from config, recommend Claude 3.5 Sonnet class)
    """
    # Use first 50000 chars to leverage larger context windows
    truncated = judgment_text[:50000]
    
    response = client.messages.create(
        model=model,  # e.g., "claude-3-5-sonnet-20241022" or latest
        max_tokens=500,
        messages=[
            {
                "role": "user", 
                "content": f"You are a legal research assistant specializing in Hong Kong law.\n\n{HEADNOTE_PROMPT.format(text=truncated)}"
            }
        ]
    )
    
    return response.content[0].text
```

---

## 7. API Specification

### 7.1 Search Endpoints

#### POST /api/search

```typescript
// Request
{
  query: string;
  filters?: {
    jurisdiction?: string;
    courts?: string[];
    dateFrom?: string;  // ISO date
    dateTo?: string;
    caseType?: string;
    topics?: string[];
  };
  options?: {
    limit?: number;      // default 20
    offset?: number;
    includeSnippets?: boolean;
    searchType?: 'semantic' | 'keyword' | 'hybrid';
  };
}

// Response
{
  results: Array<{
    id: string;
    neutralCitation: string;
    caseName: string;
    court: string;
    decisionDate: string;
    headnote: string;
    relevanceScore: number;
    matchingSnippet?: string;
  }>;
  total: number;
  query: {
    interpreted: string;  // AI-enhanced query understanding
    suggestions?: string[];
  };
}
```

#### GET /api/cases/:id

```typescript
// Response
{
  id: string;
  neutralCitation: string;
  caseNumber: string;
  caseName: string;
  court: { id: string; name: string; abbreviation: string };
  jurisdiction: { code: string; name: string };
  decisionDate: string;
  judges: string[];
  parties: { applicant: string[]; respondent: string[] };
  headnote: string;
  catchwords: string[];
  fullText: string;
  pdfUrl?: string;
  citedCases: Array<{ citation: string; treatment: string }>;
  citingCases: Array<{ citation: string; caseName: string }>;
}
```

### 7.2 Authentication

All API requests require a valid JWT token in the Authorization header:

```
Authorization: Bearer <supabase_jwt_token>
```

---

## 8. Frontend Application

### 8.1 Key Screens

1. **Search Interface** - Natural language query input with filters
2. **Results List** - Paginated results with relevance scores
3. **Case Detail View** - Full judgment with citation network
4. **Collections** - Saved cases organized in folders
5. **Export** - Generate formatted citation lists

### 8.2 Tech Stack

- Next.js 16 (latest)
- React 19 (latest) + TypeScript
- TailwindCSS + shadcn/ui
- React Query for data fetching
- Supabase client SDK

---

## 9. Workflow Integrations

### 9.1 Microsoft Word Add-in

**Purpose**: Search and cite directly within Word

**Features**:
- Highlight text → search for relevant cases
- One-click citation insertion (OSCOLA format)
- Side panel with search results

**Tech**: Office.js + React + Supabase SDK

### 9.2 Browser Extension

**Purpose**: Research while browsing

**Features**:
- Right-click context search
- Page annotation
- Quick citation lookup

---

## 10. Security & Compliance

- **Authentication**: Supabase Auth with MFA option
- **Row-Level Security**: Users only access own data
- **Encryption**: TLS 1.3 in transit, AES-256 at rest
- **Audit Logging**: Track all searches for compliance
- **Rate Limiting**: Prevent abuse

---

## 11. Infrastructure & Deployment

### 11.1 Production Architecture

```
Cloudflare (CDN/WAF)
    ↓
Netlify (Frontend)  ←→  Supabase Cloud (HK Region)
                           ├── Edge Functions
                           ├── PostgreSQL + pgvector
                           └── Storage (PDFs)
```

### 11.2 Scraper Infrastructure

**Recommended: Self-hosted VM**

| Phase | Infrastructure | Est. Cost |
|-------|---------------|-----------|
| **Initial bulk scrape** | DigitalOcean/AWS VM (4GB RAM) | ~$50-100 one-time |
| **Daily updates** | Same VM or scheduled cron job | ~$20-50/month |

**Setup**:
- Ubuntu VM with Python 3.11+, Playwright, PostgreSQL client
- Cron job for daily incremental scrapes
- Systemd service for reliability
- Logs shipped to Supabase or external monitoring

**When to consider Apify**:
- Expanding to multiple jurisdictions simultaneously
- Facing IP blocking requiring proxy rotation
- Need managed infrastructure with built-in retries

---

## 12. Implementation Roadmap

| Phase | Timeline | Deliverables |
|-------|----------|--------------|
| **1** | Months 1-2 | Database schema, scrapers, embedding pipeline |
| **2** | Months 3-4 | Search API, basic web app |
| **3** | Months 5-6 | Word add-in, citation network |
| **4** | Months 7+ | Additional jurisdictions |

---

## Appendix A: Dependencies

### Python (batch/)
```
playwright>=1.40.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
httpx>=0.25.0
openai>=1.6.0
tiktoken>=0.5.0
supabase>=2.0.0
pydantic>=2.5.0
apify-client>=1.5.0  # optional
```

### Node.js (www/)
```
react: ^18.2.0
typescript: ^5.3.0
@supabase/supabase-js: ^2.39.0
@tanstack/react-query: ^5.17.0
tailwindcss: ^3.4.0
```

---

## Appendix B: Environment Variables

```env
# Supabase
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=

# OpenAI
OPENAI_API_KEY=

# Scraper
SCRAPER_REQUEST_DELAY=3.0
SCRAPER_MAX_CONCURRENT=2

# Apify (optional)
APIFY_TOKEN=
```
