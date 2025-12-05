"""Centralized configuration management using environment variables."""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv()


class Config(BaseSettings):
    """Configuration settings for need_scanner."""

    # OpenAI API
    openai_api_key: str

    # Reddit fetcher defaults
    ns_default_subreddit: str = "freelance"
    ns_fetch_limit: int = 200
    ns_sleep_between: float = 1.0

    # Model configuration
    ns_embed_model: str = "text-embedding-3-small"

    # Light model: for simple tasks (sector tagging, intent classification)
    ns_light_model: str = "gpt-4o-mini"

    # Heavy model: for complex enrichment (persona, JTBD, scoring)
    ns_heavy_model: str = "gpt-4o"

    # Clustering
    ns_num_clusters: int = 10

    # LLM constraints
    ns_max_docs_per_cluster: int = 6
    ns_max_input_tokens_per_prompt: int = 1200
    ns_max_output_tokens: int = 400

    # TOP K enrichment: only enrich top K clusters with heavy model
    ns_top_k_enrichment: int = 5

    # History & deduplication
    ns_history_retention_days: int = 30  # Keep history for N days
    ns_history_penalty_factor: float = 0.3  # Similarity penalty strength (0-1)
    ns_duplicate_threshold: float = 0.90  # Similarity threshold for duplicate detection
    ns_run_mode: str = "discover"  # "discover" (filter duplicates) or "track" (show all)

    # Memory stabilization (Step 5-bis)
    ns_history_window_days_discover: int = 7  # Shorter window for discover mode penalty
    ns_history_sim_threshold_safe: float = 0.90  # tau: below this, no penalty
    ns_history_sim_penalty_alpha: float = 0.5  # alpha: penalty multiplier (0-1)
    ns_history_sim_exact_dup_threshold: float = 0.985  # Above this = exact duplicate (excluded)
    ns_min_insights_per_run: int = 10  # Minimum insights to return (fallback)

    # MMR reranking
    ns_mmr_lambda: float = 0.7  # Balance relevance vs diversity (0-1)
    ns_mmr_top_k: int = 10  # Number of items to select with MMR

    # SaaS-ability / Productizability
    ns_saas_viable_filter: bool = True  # Filter non-SaaS insights by default
    ns_recurring_revenue_threshold: float = 5.0  # Min score to be considered SaaS-viable
    ns_top_k_ideation: int = 5  # Number of top insights to run ideation on

    # Cost controls
    ns_cost_warn_prompt_usd: float = 0.50

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


def get_config() -> Config:
    """Get configuration instance with validation."""
    try:
        return Config()
    except Exception as e:
        if "openai_api_key" in str(e).lower():
            raise ValueError(
                "OPENAI_API_KEY is required but not set. "
                "Please create a .env file with your API key or set it as an environment variable."
            ) from e
        raise


# Pricing constants (USD per 1K tokens) - Updated for current OpenAI pricing
PRICING = {
    "gpt-4o-mini": {
        "input": 0.00015,
        "output": 0.0006
    },
    "gpt-4o": {
        "input": 0.0025,
        "output": 0.01
    },
    "gpt-3.5-turbo": {
        "input": 0.0005,
        "output": 0.0015
    },
    "text-embedding-3-small": {
        "input": 0.00002,
        "output": 0.0
    },
    "text-embedding-3-large": {
        "input": 0.00013,
        "output": 0.0
    }
}


def get_model_pricing(model: str) -> dict:
    """Get pricing for a model, with fallback to gpt-4o-mini."""
    return PRICING.get(model, PRICING["gpt-4o-mini"])


# ============================================================================
# Pack & Keyword Loaders
# ============================================================================

def load_subreddit_pack(pack_name: str, config_dir: Path = Path("config/packs")) -> list[str]:
    """
    Load a subreddit pack from config/packs/{pack_name}.txt

    Args:
        pack_name: Name of the pack (without .txt extension)
        config_dir: Directory containing pack files

    Returns:
        List of subreddit names

    Raises:
        FileNotFoundError: If pack file doesn't exist
    """
    pack_file = config_dir / f"{pack_name}.txt"

    if not pack_file.exists():
        raise FileNotFoundError(
            f"Pack '{pack_name}' not found at {pack_file}. "
            f"Available packs: {', '.join([f.stem for f in config_dir.glob('*.txt')])}"
        )

    subreddits = []
    with open(pack_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                subreddits.append(line)

    return subreddits


def load_intent_keywords(keywords_file: Path = Path("config/intent_patterns.txt")) -> list[str]:
    """
    Load intent keywords/patterns from config file.

    Args:
        keywords_file: Path to keywords file

    Returns:
        List of keyword patterns (case-insensitive)

    Raises:
        FileNotFoundError: If keywords file doesn't exist
    """
    if not keywords_file.exists():
        raise FileNotFoundError(
            f"Keywords file not found at {keywords_file}. "
            "Please create config/intent_patterns.txt with your keywords (one per line)."
        )

    keywords = []
    with open(keywords_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                keywords.append(line)

    return keywords


def list_available_packs(config_dir: Path = Path("config/packs")) -> list[str]:
    """
    List all available subreddit packs.

    Args:
        config_dir: Directory containing pack files

    Returns:
        List of pack names (without .txt extension)
    """
    if not config_dir.exists():
        return []

    return [f.stem for f in config_dir.glob("*.txt")]
