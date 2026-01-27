"""Utility functions for storing and loading PDF files.

PDF files are stored organized by source type and case/item ID, mirroring the
layout used for raw HTML (see ``html_storage.py``), but without compression.
"""

from pathlib import Path
from typing import Optional


def get_pdf_dir(source_type: str, base_dir: Path = Path("output")) -> Path:
    """Get the PDF storage directory for a source type.

    Args:
        source_type: Type of source (e.g., "judiciary", "elegislation")
        base_dir: Base output directory

    Returns:
        Path to PDF storage directory
    """

    return base_dir / source_type / "pdf"


def get_pdf_file_path(
    item_id: str,
    source_type: str,
    base_dir: Path = Path("output"),
) -> Path:
    """Get the file path for an item's PDF file.

    Files are organized in subdirectories by first 2 chars of ID to avoid
    having too many files in a single directory.

    Args:
        item_id: Item UUID or identifier
        source_type: Type of source (e.g., "judiciary", "elegislation")
        base_dir: Base output directory

    Returns:
        Path to PDF file
    """

    pdf_dir = get_pdf_dir(source_type, base_dir)
    subdir = item_id[:2] if len(item_id) >= 2 else "00"
    return pdf_dir / subdir / f"{item_id}.pdf"


def save_pdf(
    item_id: str,
    pdf_bytes: bytes,
    source_type: str,
    base_dir: Path = Path("output"),
) -> Path:
    """Save a PDF to disk.

    Args:
        item_id: Item UUID or identifier
        pdf_bytes: Raw PDF bytes
        source_type: Type of source (e.g., "judiciary", "elegislation")
        base_dir: Base output directory

    Returns:
        Path to saved file
    """

    file_path = get_pdf_file_path(item_id, source_type, base_dir)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    return file_path


def load_pdf(
    item_id: str,
    source_type: str,
    base_dir: Path = Path("output"),
) -> Optional[bytes]:
    """Load a stored PDF file.

    Args:
        item_id: Item UUID or identifier
        source_type: Type of source (e.g., "judiciary", "elegislation")
        base_dir: Base output directory

    Returns:
        PDF bytes or None if the file doesn't exist
    """

    file_path = get_pdf_file_path(item_id, source_type, base_dir)
    if not file_path.exists():
        return None

    return file_path.read_bytes()


def pdf_file_exists(
    item_id: str,
    source_type: str,
    base_dir: Path = Path("output"),
) -> bool:
    """Check if a PDF file exists for an item.

    Args:
        item_id: Item UUID or identifier
        source_type: Type of source (e.g., "judiciary", "elegislation")
        base_dir: Base output directory

    Returns:
        True if file exists, False otherwise
    """

    file_path = get_pdf_file_path(item_id, source_type, base_dir)
    return file_path.exists()