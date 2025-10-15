"""Utility functions for I/O, token estimation, and cost calculation."""

import json
from pathlib import Path
from typing import Any, List, Dict
from loguru import logger
from .config import get_model_pricing


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, create if needed."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> Any:
    """Read JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any, indent: int = 2) -> None:
    """Write data to JSON file."""
    ensure_dir(path.parent)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    logger.info(f"Written JSON to {path}")


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using simple heuristic.
    Real tokenization varies, but ~4 chars per token is a reasonable approximation.
    """
    return len(text) // 4


def estimate_tokens_batch(texts: List[str]) -> int:
    """Estimate total tokens for a batch of texts."""
    return sum(estimate_tokens(text) for text in texts)


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str
) -> float:
    """
    Calculate cost in USD for API call.

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: Model name

    Returns:
        Cost in USD
    """
    pricing = get_model_pricing(model)
    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]
    return input_cost + output_cost


def truncate_text(text: str, max_tokens: int) -> str:
    """
    Truncate text to approximately max_tokens.
    Uses character-based approximation (4 chars per token).
    """
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def truncate_texts_to_fit(
    texts: List[str],
    max_total_tokens: int,
    reserve_tokens: int = 200
) -> List[str]:
    """
    Truncate a list of texts to fit within max_total_tokens budget.

    Args:
        texts: List of texts to truncate
        max_total_tokens: Maximum total tokens allowed
        reserve_tokens: Tokens to reserve for prompt template

    Returns:
        List of truncated texts
    """
    available_tokens = max_total_tokens - reserve_tokens
    tokens_per_text = available_tokens // len(texts) if texts else 0

    # Ensure minimum viable length
    tokens_per_text = max(tokens_per_text, 50)

    return [truncate_text(text, tokens_per_text) for text in texts]


def format_cost(cost_usd: float) -> str:
    """Format cost in USD with appropriate precision."""
    if cost_usd < 0.01:
        return f"${cost_usd:.4f}"
    return f"${cost_usd:.2f}"


def setup_logger(log_file: Path = None) -> None:
    """Configure loguru logger."""
    logger.remove()  # Remove default handler
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO"
    )

    if log_file:
        ensure_dir(log_file.parent)
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            level="DEBUG",
            rotation="10 MB"
        )
