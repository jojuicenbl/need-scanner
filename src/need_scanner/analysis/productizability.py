"""SaaS-ability and productizability classification for insights."""

import json
from typing import Dict, List, Optional, Tuple
from loguru import logger

from openai import OpenAI

from ..config import get_model_pricing


# Solution types enum
SOLUTION_TYPES = [
    "saas_b2b",           # B2B SaaS product
    "saas_b2c",           # B2C SaaS product
    "tooling_dev",        # Developer tools (CLI, libraries, etc.)
    "api_product",        # API-as-a-product
    "service_only",       # Consulting / agency / services
    "content_only",       # Ebook, blog, video, course
    "hardware_required",  # Requires hardware / physical product
    "regulation_policy",  # Policy / regulation / legal change needed
    "impractical_unclear" # Not practical or unclear solution path
]

# SaaS-viable solution types
SAAS_VIABLE_TYPES = {"saas_b2b", "saas_b2c", "tooling_dev", "api_product"}


def classify_productizability(
    title: str,
    problem: str,
    sector: Optional[str] = None,
    persona: Optional[str] = None,
    jtbd: Optional[str] = None,
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None,
    recurring_revenue_threshold: float = 5.0
) -> Tuple[Dict, float]:
    """
    Classify an insight for productizability using LLM.

    Args:
        title: Insight title
        problem: Problem description
        sector: Sector classification
        persona: Target persona
        jtbd: Job-to-be-done
        model: LLM model to use (light model recommended)
        api_key: OpenAI API key
        recurring_revenue_threshold: Min score to be SaaS-viable

    Returns:
        Tuple of (result dict, cost in USD)
        Result dict contains:
        - solution_type: str
        - recurring_revenue_potential: float (1-10)
        - saas_viable: bool
        - reasoning: str (brief explanation)
    """
    client = OpenAI(api_key=api_key)

    # Build context
    context_parts = []
    if sector:
        context_parts.append(f"Sector: {sector}")
    if persona:
        context_parts.append(f"Target persona: {persona}")
    if jtbd:
        context_parts.append(f"Job-to-be-done: {jtbd}")
    context = "\n".join(context_parts) if context_parts else "No additional context"

    prompt = f"""Analyze this pain point for productizability as a SaaS/software product.

PAIN POINT:
Title: {title}
Problem: {problem}
{context}

Classify the solution type from these options:
- saas_b2b: B2B SaaS product (web app for businesses)
- saas_b2c: B2C SaaS product (web app for consumers)
- tooling_dev: Developer tools (CLI, libraries, IDE extensions)
- api_product: API-as-a-product
- service_only: Requires human services (consulting, agency work)
- content_only: Best solved with content (course, ebook, blog)
- hardware_required: Requires hardware or physical product
- regulation_policy: Requires policy/legal/regulatory changes
- impractical_unclear: Not practical or unclear solution path

Rate the recurring revenue potential (1-10):
- 1-3: One-shot, hard to monetize repeatedly
- 4-6: Some recurring potential but not obvious
- 7-10: Natural recurring model (subscription, usage-based)

Consider:
- Can a solo developer build an MVP in 1-3 months?
- Does it solve a recurring pain (not one-time)?
- Can it be priced as a subscription or usage-based?
- Is the market reachable online?

Respond in JSON format:
{{
    "solution_type": "one of the types above",
    "recurring_revenue_potential": 1-10,
    "reasoning": "Brief 1-sentence explanation"
}}"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200,
            response_format={"type": "json_object"}
        )

        # Parse response
        content = response.choices[0].message.content
        result = json.loads(content)

        # Validate and normalize
        solution_type = result.get("solution_type", "impractical_unclear")
        if solution_type not in SOLUTION_TYPES:
            solution_type = "impractical_unclear"

        recurring_revenue = float(result.get("recurring_revenue_potential", 5))
        recurring_revenue = max(1, min(10, recurring_revenue))

        # Determine SaaS viability
        saas_viable = (
            solution_type in SAAS_VIABLE_TYPES
            and recurring_revenue >= recurring_revenue_threshold
        )

        # Calculate cost
        pricing = get_model_pricing(model)
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1000

        return {
            "solution_type": solution_type,
            "recurring_revenue_potential": recurring_revenue,
            "saas_viable": saas_viable,
            "reasoning": result.get("reasoning", "")
        }, cost

    except Exception as e:
        logger.error(f"Error classifying productizability: {e}")
        return {
            "solution_type": "impractical_unclear",
            "recurring_revenue_potential": 5.0,
            "saas_viable": False,
            "reasoning": f"Classification failed: {str(e)}"
        }, 0.0


def classify_batch_productizability(
    insights: List[Dict],
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None,
    recurring_revenue_threshold: float = 5.0
) -> Tuple[Dict[int, Dict], float]:
    """
    Classify productizability for a batch of insights.

    Args:
        insights: List of insight dicts with cluster_id, title, problem, etc.
        model: LLM model to use
        api_key: OpenAI API key
        recurring_revenue_threshold: Min score to be SaaS-viable

    Returns:
        Tuple of (results dict by cluster_id, total cost)
    """
    results = {}
    total_cost = 0.0

    logger.info(f"Classifying productizability for {len(insights)} insights...")

    for insight in insights:
        cluster_id = insight.get("cluster_id")
        if cluster_id is None:
            continue

        result, cost = classify_productizability(
            title=insight.get("title", ""),
            problem=insight.get("problem", ""),
            sector=insight.get("sector"),
            persona=insight.get("persona"),
            jtbd=insight.get("jtbd"),
            model=model,
            api_key=api_key,
            recurring_revenue_threshold=recurring_revenue_threshold
        )

        results[cluster_id] = result
        total_cost += cost

    # Log summary
    saas_viable_count = sum(1 for r in results.values() if r.get("saas_viable"))
    logger.info(
        f"Productizability classification complete: "
        f"{saas_viable_count}/{len(results)} SaaS-viable. "
        f"Cost: ${total_cost:.4f}"
    )

    # Log distribution by solution type
    type_counts = {}
    for r in results.values():
        sol_type = r.get("solution_type", "unknown")
        type_counts[sol_type] = type_counts.get(sol_type, 0) + 1
    logger.info(f"Solution type distribution: {type_counts}")

    return results, total_cost
