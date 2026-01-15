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

    # Azure OpenAI (embeddings and text generation)
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-10-01-preview"
    azure_openai_embed_deployment: str = ""
    azure_openai_gpt4o_deployment: str = "gpt-4o"
    
    # Azure Storage (for batch processing)
    azure_storage_account_name: str = ""
    azure_storage_account_key: str = ""
    azure_storage_connection_string: str = ""
    azure_batch_input_container: str = "batch-input"
    azure_batch_output_container: str = "batch-output"
    
    # Azure Service Principal (alternative authentication)
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""

    # Anthropic / Bedrock-compatible keys (for Claude via Bedrock)
    anthropic_api_key: str = ""  # optional, kept for compatibility

    # AWS / Bedrock
    aws_region: str = "ap-southeast-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    
    # Bedrock Batch Processing
    bedrock_batch_input_bucket: str = ""
    bedrock_batch_output_bucket: str = ""
    bedrock_batch_role_arn: str = ""

    # Scraper settings
    scraper_request_delay: float = 3.0
    scraper_max_concurrent: int = 2
    scraper_headless: bool = True

    # State and logging
    state_dir: str = "./state"
    log_dir: str = "./logs"
    log_level: str = "INFO"

    # AI Models - Phase 1 Configuration
    # Phase 1: Use models that don't require Bedrock approval
    # - Embeddings: Amazon Titan V2 (no approval needed)
    # - Text generation: Azure GPT-4o (already have access)
    embedding_model: str = "amazon.titan-embed-text-v2:0"
    headnote_model: str = "azure-gpt-4o"
    
    # Phase 2 (after Claude approval):
    # headnote_model: str = "anthropic.claude-opus-4-5:0"

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
