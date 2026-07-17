# Context budget and token estimation utilities
import re

def estimate_tokens(text: str) -> int:
    """A rough token estimation helper (approx 4 chars per token)."""
    return len(text) // 4
