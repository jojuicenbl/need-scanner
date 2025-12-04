"""LLM utility functions for model selection and API calls."""

import json
from typing import Dict, List, Optional
from openai import OpenAI
from loguru import logger

from .config import get_config


def get_openai_client() -> OpenAI:
    """Get configured OpenAI client."""
    config = get_config()
    return OpenAI(api_key=config.openai_api_key)


def call_llm(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    response_format: Optional[Dict] = None
) -> tuple[str, float]:
    """
    Call OpenAI LLM and return response with cost.

    Args:
        prompt: The prompt to send
        model: Model name (defaults to light model from config)
        temperature: Temperature for generation
        max_tokens: Maximum tokens to generate
        response_format: Optional response format (e.g., {"type": "json_object"})

    Returns:
        (response_text, cost_usd)
    """
    config = get_config()

    if model is None:
        model = config.ns_light_model

    client = get_openai_client()

    call_kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    if response_format:
        call_kwargs["response_format"] = response_format

    logger.debug(f"Calling LLM: {model}")

    response = client.chat.completions.create(**call_kwargs)

    response_text = response.choices[0].message.content

    # Calculate cost (approximate)
    prompt_tokens = response.usage.prompt_tokens
    completion_tokens = response.usage.completion_tokens

    # Simplified cost calculation (should be updated with real pricing)
    if "gpt-4o" in model:
        prompt_cost = prompt_tokens * 0.000005  # $5 per 1M tokens
        completion_cost = completion_tokens * 0.000015  # $15 per 1M tokens
    elif "gpt-4o-mini" in model:
        prompt_cost = prompt_tokens * 0.00000015  # $0.15 per 1M tokens
        completion_cost = completion_tokens * 0.0000006  # $0.60 per 1M tokens
    else:
        # Default fallback pricing
        prompt_cost = prompt_tokens * 0.000001
        completion_cost = completion_tokens * 0.000002

    cost = prompt_cost + completion_cost

    logger.debug(f"LLM call complete: {prompt_tokens} + {completion_tokens} tokens, ${cost:.6f}")

    return response_text, cost


def explore_insight_with_llm(
    insight_title: str,
    insight_problem: str,
    persona: Optional[str] = None,
    context: Optional[str] = None,
    pain_score: Optional[float] = None,
    trend_score: Optional[float] = None,
    model: Optional[str] = None
) -> Dict:
    """
    Perform deep exploration of an insight using a heavy LLM.

    Args:
        insight_title: Title of the insight
        insight_problem: Problem description
        persona: Target persona (optional)
        context: Context information (optional)
        pain_score: Pain score (optional)
        trend_score: Trend score (optional)
        model: Model to use (defaults to heavy model from config)

    Returns:
        Dictionary with:
            - full_text: Complete exploration text
            - monetization_ideas: List of 2-3 monetization hypotheses
            - product_variants: List of 2-3 more ambitious product variants
            - validation_steps: List of 3 concrete next steps
            - cost_usd: Cost of the LLM call
    """
    config = get_config()

    if model is None:
        model = config.ns_heavy_model

    # Build comprehensive prompt
    prompt_parts = [
        "# Deep Insight Exploration",
        "",
        f"## Insight: {insight_title}",
        "",
        f"**Problem**: {insight_problem}",
    ]

    if persona:
        prompt_parts.append(f"**Target Persona**: {persona}")

    if context:
        prompt_parts.append(f"**Context**: {context}")

    if pain_score is not None:
        prompt_parts.append(f"**Pain Score**: {pain_score}/10")

    if trend_score is not None:
        prompt_parts.append(f"**Trend Score**: {trend_score}/10")

    prompt_parts.extend([
        "",
        "---",
        "",
        "Please provide a comprehensive analysis of this market opportunity:",
        "",
        "## 1. Market Analysis",
        "- What are the key market dynamics?",
        "- Who are the main players (if any)?",
        "- What gaps exist in current solutions?",
        "- What is the market size potential?",
        "",
        "## 2. Monetization Hypotheses",
        "Provide 2-3 concrete monetization strategies:",
        "- **Strategy**: Clear monetization model",
        "- **Target Customer**: Who pays?",
        "- **Pricing Range**: Estimated pricing",
        "- **Key Risk**: Main challenge to this approach",
        "",
        "## 3. Product Variants",
        "Suggest 2-3 progressively ambitious versions of the product:",
        "1. **MVP Version**: Minimal viable version to test the core hypothesis",
        "2. **Enhanced Version**: More features, broader market",
        "3. **Ambitious Vision**: Long-term potential with network effects",
        "",
        "## 4. Validation Steps",
        "Provide 3 concrete next steps to validate this opportunity:",
        "1. [First step - most important validation]",
        "2. [Second step - market research or customer interviews]",
        "3. [Third step - prototype or landing page test]",
        "",
        "Provide a detailed, actionable analysis. Focus on practical insights and specific recommendations."
    ])

    prompt = "\n".join(prompt_parts)

    logger.info(f"Exploring insight with {model}...")

    response_text, cost = call_llm(
        prompt=prompt,
        model=model,
        temperature=0.7,
        max_tokens=3000
    )

    # Parse the response to extract structured sections
    # This is a simple extraction - could be improved with structured output
    result = {
        "full_text": response_text,
        "model_used": model,
        "cost_usd": cost
    }

    # Try to extract sections (basic parsing)
    sections = {
        "monetization_ideas": [],
        "product_variants": [],
        "validation_steps": []
    }

    # Simple section extraction
    lines = response_text.split("\n")
    current_section = None
    current_items = []

    for line in lines:
        line_lower = line.lower().strip()

        if "monetization" in line_lower and ("##" in line or "**" in line):
            if current_section and current_items:
                sections[current_section] = current_items
            current_section = "monetization_ideas"
            current_items = []
        elif "product variant" in line_lower and ("##" in line or "**" in line):
            if current_section and current_items:
                sections[current_section] = current_items
            current_section = "product_variants"
            current_items = []
        elif "validation" in line_lower and ("##" in line or "**" in line):
            if current_section and current_items:
                sections[current_section] = current_items
            current_section = "validation_steps"
            current_items = []
        elif current_section and line.strip() and (line.strip().startswith("-") or line.strip().startswith("*") or line.strip()[0].isdigit()):
            # This is an item in the current section
            current_items.append(line.strip())

    if current_section and current_items:
        sections[current_section] = current_items

    result.update(sections)

    return result
