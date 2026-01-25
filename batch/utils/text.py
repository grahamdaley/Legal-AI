"""Text processing utilities for batch operations."""


def truncate_to_token_limit(text: str, max_tokens: int = 4000) -> str:
    """Truncate text to fit within a conservative token limit.

    Uses a 1 char ≈ 1 token heuristic to stay well under model token limits.
    This is conservative but guarantees we stay below hard limits even in
    worst-case tokenization scenarios (e.g., legal text with dense terminology).

    Args:
        text: The text to truncate.
        max_tokens: Maximum number of "tokens" (characters) to allow.

    Returns:
        Truncated text, preferring word boundaries when possible.
    """
    max_chars = max_tokens
    if len(text) <= max_chars:
        return text

    # Truncate at character boundary, then at word boundary if possible
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.8:  # Only use space break if reasonably close
        truncated = truncated[:last_space]

    return truncated.rstrip()
