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
    ns_summary_model: str = "gpt-4o-mini"

    # Clustering
    ns_num_clusters: int = 10

    # LLM constraints
    ns_max_docs_per_cluster: int = 6
    ns_max_input_tokens_per_prompt: int = 1200
    ns_max_output_tokens: int = 400

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
