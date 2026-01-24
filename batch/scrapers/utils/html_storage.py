"""
Utility functions for storing and loading raw HTML files.

HTML files are stored as gzipped files organized by source type and case/item ID.
"""

import gzip
import hashlib
from pathlib import Path
from typing import Optional


def get_html_dir(source_type: str, base_dir: Path = Path("output")) -> Path:
    """Get the HTML storage directory for a source type.
    
    Args:
        source_type: Type of source (e.g., "judiciary", "elegislation")
        base_dir: Base output directory
        
    Returns:
        Path to HTML storage directory
    """
    return base_dir / source_type / "html"


def get_html_file_path(
    item_id: str,
    source_type: str,
    base_dir: Path = Path("output"),
) -> Path:
    """Get the file path for an item's HTML file.
    
    Files are organized in subdirectories by first 2 chars of ID to avoid
    having too many files in a single directory.
    
    Args:
        item_id: Item UUID or identifier
        source_type: Type of source (e.g., "judiciary", "elegislation")
        base_dir: Base output directory
        
    Returns:
        Path to HTML file
    """
    html_dir = get_html_dir(source_type, base_dir)
    subdir = item_id[:2] if len(item_id) >= 2 else "00"
    return html_dir / subdir / f"{item_id}.html.gz"


def save_html(
    item_id: str,
    html: str,
    source_type: str,
    base_dir: Path = Path("output"),
) -> Path:
    """Save HTML to a gzipped file.
    
    Args:
        item_id: Item UUID or identifier
        html: HTML content
        source_type: Type of source (e.g., "judiciary", "elegislation")
        base_dir: Base output directory
        
    Returns:
        Path to saved file
    """
    file_path = get_html_file_path(item_id, source_type, base_dir)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with gzip.open(file_path, "wt", encoding="utf-8") as f:
        f.write(html)
    
    return file_path


def load_html(
    item_id: str,
    source_type: str,
    base_dir: Path = Path("output"),
) -> Optional[str]:
    """Load HTML from a gzipped file.
    
    Args:
        item_id: Item UUID or identifier
        source_type: Type of source (e.g., "judiciary", "elegislation")
        base_dir: Base output directory
        
    Returns:
        HTML content or None if file doesn't exist
    """
    file_path = get_html_file_path(item_id, source_type, base_dir)
    if not file_path.exists():
        return None
    
    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        return f.read()


def html_file_exists(
    item_id: str,
    source_type: str,
    base_dir: Path = Path("output"),
) -> bool:
    """Check if HTML file exists for an item.
    
    Args:
        item_id: Item UUID or identifier
        source_type: Type of source (e.g., "judiciary", "elegislation")
        base_dir: Base output directory
        
    Returns:
        True if file exists
    """
    file_path = get_html_file_path(item_id, source_type, base_dir)
    return file_path.exists()


def generate_item_id_from_url(url: str) -> str:
    """Generate a stable ID from a URL for cases where we don't have a UUID yet.
    
    Args:
        url: Source URL
        
    Returns:
        A hash-based ID
    """
    return hashlib.sha256(url.encode()).hexdigest()[:32]
