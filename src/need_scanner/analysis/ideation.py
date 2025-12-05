"""Product ideation for transforming pains into actionable product opportunities."""

import json
from typing import Dict, List, Optional, Tuple
from loguru import logger

from openai import OpenAI

from ..config import get_model_pricing


def generate_product_angles(
    title: str,
    problem: str,
    sector: Optional[str] = None,
    persona: Optional[str] = None,
    jtbd: Optional[str] = None,
    solution_type: Optional[str] = None,
    recurring_revenue_potential: Optional[float] = None,
    model: str = "gpt-4o",
    api_key: Optional[str] = None
) -> Tuple[Dict, float]:
    """
    Generate product angle ideas for an insight using a heavy LLM.

    This function generates 3 product angles and selects the most
    indie-friendly one as the primary opportunity.

    Args:
        title: Insight title
        problem: Problem description
        sector: Sector classification
        persona: Target persona
        jtbd: Job-to-be-done
        solution_type: Already classified solution type
        recurring_revenue_potential: Already scored revenue potential
        model: LLM model to use (heavy model recommended)
        api_key: OpenAI API key

    Returns:
        Tuple of (result dict, cost in USD)
        Result dict contains:
        - product_angle_title: str (short title for the opportunity)
        - product_angle_summary: str (description)
        - product_angle_type: str (indie_saas, b2b_saas, plugin, api, etc.)
        - product_pricing_hint: str (pricing range)
        - product_complexity: int (1-3)
        - all_angles: list (all 3 generated angles)
    """
    client = OpenAI(api_key=api_key)

    # Build context
    context_parts = [f"Pain: {problem}"]
    if sector:
        context_parts.append(f"Sector: {sector}")
    if persona:
        context_parts.append(f"Target persona: {persona}")
    if jtbd:
        context_parts.append(f"Job-to-be-done: {jtbd}")
    if solution_type:
        context_parts.append(f"Suggested solution type: {solution_type}")
    if recurring_revenue_potential:
        context_parts.append(f"Recurring revenue potential: {recurring_revenue_potential}/10")

    context = "\n".join(context_parts)

    prompt = f"""Based on this validated pain point, propose 3 product angles for a solo developer to build.

PAIN POINT:
Title: {title}
{context}

Generate 3 different product approaches:

1. **SaaS B2B angle**: A web application targeting businesses
2. **Indie-friendly angle**: A small, focused tool that one developer can build and monetize quickly (CLI, browser extension, simple web app, Notion/Airtable template, etc.)
3. **Adjacent angle**: A variation like plugin, API, integration, or marketplace

For each angle, provide:
- title: Short product name (2-4 words)
- type: indie_saas | b2b_saas | plugin | extension | api | template | marketplace
- target_customer: Who exactly pays for this
- pricing: Suggested pricing range (e.g., "$9-29/mo", "$49 one-time", "Free + $19/mo pro")
- complexity: 1 (weekend project), 2 (1-3 months), 3 (3+ months)
- description: 2-sentence pitch

Then select the BEST angle for an indie developer (considering: quick to build, clear monetization, reachable market).

Respond in JSON:
{{
    "angles": [
        {{
            "title": "...",
            "type": "...",
            "target_customer": "...",
            "pricing": "...",
            "complexity": 1-3,
            "description": "..."
        }},
        // ... 2 more angles
    ],
    "best_angle_index": 0-2,
    "reasoning": "Why this is the best angle for an indie dev"
}}"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=800,
            response_format={"type": "json_object"}
        )

        # Parse response
        content = response.choices[0].message.content
        result = json.loads(content)

        angles = result.get("angles", [])
        best_index = result.get("best_angle_index", 0)

        if not angles:
            raise ValueError("No angles generated")

        # Get the best angle
        best_angle = angles[min(best_index, len(angles) - 1)]

        # Calculate cost
        pricing = get_model_pricing(model)
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1000

        return {
            "product_angle_title": best_angle.get("title", ""),
            "product_angle_summary": best_angle.get("description", ""),
            "product_angle_type": best_angle.get("type", "indie_saas"),
            "product_pricing_hint": best_angle.get("pricing", ""),
            "product_complexity": int(best_angle.get("complexity", 2)),
            "all_angles": angles,
            "reasoning": result.get("reasoning", "")
        }, cost

    except Exception as e:
        logger.error(f"Error generating product angles: {e}")
        return {
            "product_angle_title": None,
            "product_angle_summary": None,
            "product_angle_type": None,
            "product_pricing_hint": None,
            "product_complexity": None,
            "all_angles": [],
            "reasoning": f"Generation failed: {str(e)}"
        }, 0.0


def generate_batch_product_angles(
    insights: List[Dict],
    model: str = "gpt-4o",
    api_key: Optional[str] = None,
    top_k: int = 5
) -> Tuple[Dict[int, Dict], float]:
    """
    Generate product angles for the top K insights.

    Args:
        insights: List of insight dicts with cluster_id, title, problem, etc.
        model: LLM model to use (heavy model)
        api_key: OpenAI API key
        top_k: Number of top insights to process

    Returns:
        Tuple of (results dict by cluster_id, total cost)
    """
    results = {}
    total_cost = 0.0

    # Only process top K
    insights_to_process = insights[:top_k]

    logger.info(f"Generating product angles for top {len(insights_to_process)} insights (heavy model: {model})...")

    for insight in insights_to_process:
        cluster_id = insight.get("cluster_id")
        if cluster_id is None:
            continue

        result, cost = generate_product_angles(
            title=insight.get("title", ""),
            problem=insight.get("problem", ""),
            sector=insight.get("sector"),
            persona=insight.get("persona"),
            jtbd=insight.get("jtbd"),
            solution_type=insight.get("solution_type"),
            recurring_revenue_potential=insight.get("recurring_revenue_potential"),
            model=model,
            api_key=api_key
        )

        results[cluster_id] = result
        total_cost += cost

        if result.get("product_angle_title"):
            logger.info(
                f"  Cluster {cluster_id}: {result['product_angle_title']} "
                f"({result['product_angle_type']}, complexity={result['product_complexity']})"
            )

    logger.info(
        f"Product ideation complete for {len(results)} insights. "
        f"Cost: ${total_cost:.4f}"
    )

    return results, total_cost
