"""
Application settings loaded from environment variables.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings

# Find repo root (parent of batch directory)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings."""

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
    supabase_db_url: str = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    
    # Output directory for scraped data
    output_dir: str = "./output"

    # Azure OpenAI (used to call text-embedding-3-large)
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2023-12-01-preview"
    azure_openai_embed_deployment: str = ""

    # Anthropic / Bedrock-compatible keys (for Claude via Bedrock)
    anthropic_api_key: str = ""  # optional, kept for compatibility

    # AWS / Bedrock
    aws_region: str = "ap-southeast-1"

    # Scraper settings
    scraper_request_delay: float = 3.0
    scraper_max_concurrent: int = 2
    scraper_headless: bool = True

    # State and logging
    state_dir: str = "./state"
    log_dir: str = "./logs"
    log_level: str = "INFO"

    # AI Models
    # Logical model identifiers; concrete provider-specific IDs are configured
    # via environment variables where needed.
    embedding_model: str = "bedrock-cohere"
    headnote_model: str = "anthropic.claude-3-7-sonnet:0"

    # Apify (optional)
    apify_token: Optional[str] = None

    class Config:
        env_file = str(_ENV_FILE)
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
