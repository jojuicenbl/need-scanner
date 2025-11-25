"""LLM-based cluster summarization with cost controls."""

import json
import time
from typing import List, Tuple, Optional
from loguru import logger
from openai import OpenAI

from ..schemas import ClusterSummary, EnrichedClusterSummary
from ..utils import (
    estimate_tokens,
    calculate_cost,
    format_cost,
    truncate_texts_to_fit
)


SYSTEM_PROMPT = """Tu es un analyste produit qui détecte des problèmes "monétisables" dans des posts utilisateurs.
Réponds uniquement en JSON strict valide."""


# Enhanced prompt for deep market discovery
ENRICHED_SYSTEM_PROMPT = """Tu es un analyste de marché expert qui effectue une analyse approfondie des besoins utilisateurs.
Tu dois extraire : persona, Job-To-Be-Done (JTBD), contexte d'usage, outils alternatifs mentionnés, et signaux de willingness-to-pay.
Réponds uniquement en JSON strict valide."""


def build_user_prompt(texts: List[str], max_examples: int) -> str:
    """
    Build user prompt for cluster summarization (legacy format).

    Args:
        texts: List of text snippets (already truncated)
        max_examples: Maximum number of examples to include

    Returns:
        User prompt string
    """
    texts = texts[:max_examples]

    prompt = f"""Voici jusqu'à {len(texts)} extraits (titre + court extrait) d'un même cluster thématique.
Tâches :
1) Donne un titre court (3-6 mots) qui résume le problème principal.
2) Décris le problème en 2-3 phrases, concret et orienté douleur métier.
3) Indique si c'est monétisable (true/false) et justifie en 1 phrase.
4) Propose un MVP (une seule phrase) pour tester rapidement.
5) Donne un "pain_score_llm" entier de 1 à 10 (10 = douleur forte, urgente, récurrente).

Réponds UNIQUEMENT en JSON strict avec les clés :
{{ "title": "...", "description": "...", "monetizable": true/false, "justification": "...", "mvp": "...", "pain_score_llm": 7 }}

Extraits :
"""

    for i, text in enumerate(texts, 1):
        prompt += f"\n---\nExtrait {i}:\n{text}\n"

    prompt += "\n---"

    return prompt


def build_enriched_user_prompt(texts: List[str], max_examples: int) -> str:
    """
    Build enhanced user prompt for deep market discovery.

    Args:
        texts: List of text snippets (already truncated)
        max_examples: Maximum number of examples to include

    Returns:
        User prompt string
    """
    texts = texts[:max_examples]

    prompt = f"""Voici jusqu'à {len(texts)} extraits (titre + court extrait) d'un même cluster thématique.

Effectue une analyse approfondie et réponds en JSON strict avec les clés suivantes :

1) **title** : Titre court (3-6 mots) résumant le problème principal
2) **problem** : Description du problème en 2-3 phrases, concrète et orientée douleur métier
3) **persona** : Profil type de l'utilisateur (ex: "Freelance designer", "E-commerce owner", "SaaS founder", "Developer", etc.)
4) **jtbd** : Job-To-Be-Done au format "Quand [situation], je veux [progrès], afin de [résultat]"
5) **context** : Contexte d'usage en 1-2 phrases : outils actuels, contraintes, fréquence du besoin
6) **monetizable** : true/false
7) **mvp** : Proposition de MVP (une seule phrase) pour tester rapidement. IMPORTANT :
   - ❌ ÉVITE : "guides PDF", "articles de blog", "ressources statiques", "templates à télécharger", "e-books"
   - ✅ PRIVILÉGIE : outils SaaS simples, scripts/automations, extensions navigateur, dashboards interactifs, APIs, calculateurs en ligne, assistants/bots, micro-services
   - Pense "produit/service qu'un dev fullstack solo peut construire en quelques semaines"
   - Format : "Construire [un outil/service concret] qui [action/valeur créée]"
   - Exemple BON : "Construire un script Python qui génère automatiquement des rapports financiers depuis Stripe"
   - Exemple MAUVAIS : "Créer un guide PDF expliquant comment faire des rapports financiers"
8) **alternatives** : Liste des outils/solutions alternatifs mentionnés (array de strings, peut être vide [])
9) **willingness_to_pay_signal** : Signal de volonté de payer détecté (ex: "mentions frustration with expensive tools", "looking for paid solution", "currently paying for X", ou "" si aucun signal)
10) **pain_score_llm** : Score de douleur de 1 à 10. IMPORTANT : Utilise TOUTE l'échelle 1-10 de manière discriminante :
    - 1-3 = Inconvénient mineur, pas urgent, workarounds acceptables
    - 4-6 = Problème réel mais gérable, impact modéré
    - 7-8 = Douleur forte, impact business significatif, besoin urgent
    - 9-10 = Douleur critique/exceptionnelle, bloquant majeur (RARE - réserve pour cas vraiment exceptionnels)

    Imagine que tu scores 100 problèmes différents : seuls quelques-uns méritent 9-10. La plupart se situent entre 4-7.
    Sois EXIGEANT et DISCRIMINANT dans ta notation.

Format JSON attendu :
{{
  "title": "...",
  "problem": "...",
  "persona": "...",
  "jtbd": "Quand ..., je veux ..., afin de ...",
  "context": "...",
  "monetizable": true,
  "mvp": "...",
  "alternatives": ["tool1", "tool2"],
  "willingness_to_pay_signal": "...",
  "pain_score_llm": 6
}}

Extraits :
"""

    for i, text in enumerate(texts, 1):
        prompt += f"\n---\nExtrait {i}:\n{text}\n"

    prompt += "\n---\nRéponds UNIQUEMENT en JSON strict."

    return prompt


def parse_llm_response(response_text: str) -> Optional[dict]:
    """
    Parse LLM response as JSON.

    Args:
        response_text: Raw response text

    Returns:
        Parsed dict or None if invalid
    """
    try:
        # Try direct JSON parsing
        data = json.loads(response_text)
        return data
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            json_str = response_text[start:end].strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            json_str = response_text[start:end].strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

    logger.warning(f"Failed to parse JSON from LLM response: {response_text[:200]}")
    return None


def summarize_cluster(
    texts: List[str],
    cluster_id: int,
    cluster_size: int,
    model: str,
    api_key: str,
    max_examples: int,
    max_input_tokens: int,
    max_output_tokens: int,
    cost_warn_threshold: float,
    max_retries: int = 2
) -> Tuple[Optional[ClusterSummary], float]:
    """
    Summarize a cluster using LLM with cost controls.

    Args:
        texts: List of texts in cluster
        cluster_id: Cluster ID
        cluster_size: Size of cluster
        model: LLM model name
        api_key: OpenAI API key
        max_examples: Maximum examples to include
        max_input_tokens: Maximum input tokens
        max_output_tokens: Maximum output tokens
        cost_warn_threshold: Cost threshold to warn (USD)
        max_retries: Maximum retry attempts

    Returns:
        Tuple of (ClusterSummary or None, cost in USD)
    """
    # Truncate texts to fit budget
    truncated_texts = truncate_texts_to_fit(
        texts[:max_examples],
        max_input_tokens,
        reserve_tokens=200
    )

    # Build prompts
    user_prompt = build_user_prompt(truncated_texts, max_examples)

    # Estimate cost
    estimated_input_tokens = estimate_tokens(SYSTEM_PROMPT + user_prompt)
    estimated_cost = calculate_cost(estimated_input_tokens, max_output_tokens, model)

    logger.info(
        f"Cluster {cluster_id}: Estimated cost {format_cost(estimated_cost)} "
        f"({estimated_input_tokens} input + {max_output_tokens} output tokens)"
    )

    # Check cost threshold
    if estimated_cost > cost_warn_threshold:
        logger.warning(
            f"Cluster {cluster_id}: Estimated cost {format_cost(estimated_cost)} "
            f"exceeds threshold {format_cost(cost_warn_threshold)}. "
            f"Consider reducing max_examples or max_input_tokens."
        )

        # If way over budget, skip
        if estimated_cost > cost_warn_threshold * 2:
            logger.error(f"Cluster {cluster_id}: Cost too high, skipping.")
            return None, 0.0

    # Call LLM
    client = OpenAI(api_key=api_key)
    total_cost = 0.0

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_output_tokens,
                temperature=0.7
            )

            # Calculate actual cost
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            total_cost = calculate_cost(input_tokens, output_tokens, model)

            logger.info(
                f"Cluster {cluster_id}: API call completed. "
                f"Actual cost: {format_cost(total_cost)} "
                f"({input_tokens} + {output_tokens} tokens)"
            )

            # Parse response
            response_text = response.choices[0].message.content
            data = parse_llm_response(response_text)

            if data is None:
                if attempt < max_retries:
                    logger.warning(f"Cluster {cluster_id}: Invalid JSON, retrying ({attempt + 1}/{max_retries})...")
                    time.sleep(1)
                    continue
                else:
                    logger.error(f"Cluster {cluster_id}: Failed to parse JSON after {max_retries} retries")
                    return None, total_cost

            # Validate required fields
            required_fields = ["title", "description", "monetizable", "justification", "mvp", "pain_score_llm"]
            if not all(field in data for field in required_fields):
                logger.error(f"Cluster {cluster_id}: Missing required fields in response")
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                return None, total_cost

            # Create ClusterSummary
            summary = ClusterSummary(
                cluster_id=cluster_id,
                size=cluster_size,
                title=data["title"],
                description=data["description"],
                monetizable=bool(data["monetizable"]),
                justification=data["justification"],
                mvp=data["mvp"],
                pain_score_llm=int(data["pain_score_llm"]) if data["pain_score_llm"] is not None else None
            )

            logger.info(f"Cluster {cluster_id}: Successfully summarized - {summary.title}")
            return summary, total_cost

        except Exception as e:
            if attempt < max_retries:
                wait_time = 2 ** attempt
                logger.warning(
                    f"Cluster {cluster_id}: API error (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"Cluster {cluster_id}: Failed after {max_retries + 1} attempts: {e}")
                return None, 0.0

    return None, 0.0


def summarize_all_clusters(
    cluster_data: dict,
    model: str,
    api_key: str,
    max_examples: int,
    max_input_tokens: int,
    max_output_tokens: int,
    cost_warn_threshold: float
) -> Tuple[List[ClusterSummary], float]:
    """
    Summarize all clusters.

    Args:
        cluster_data: Dict mapping cluster_id to list of items
        model: LLM model name
        api_key: OpenAI API key
        max_examples: Maximum examples per cluster
        max_input_tokens: Maximum input tokens
        max_output_tokens: Maximum output tokens
        cost_warn_threshold: Cost threshold to warn (USD)

    Returns:
        Tuple of (list of ClusterSummary, total cost in USD)
    """
    summaries = []
    total_cost = 0.0

    logger.info(f"Summarizing {len(cluster_data)} clusters...")

    # Estimate total cost
    estimated_total = len(cluster_data) * calculate_cost(max_input_tokens, max_output_tokens, model)
    logger.info(f"Estimated total cost: {format_cost(estimated_total)}")

    for cluster_id, items in sorted(cluster_data.items()):
        # Extract texts
        texts = [item["meta"]["title"] for item in items]

        # Summarize
        summary, cost = summarize_cluster(
            texts=texts,
            cluster_id=cluster_id,
            cluster_size=len(items),
            model=model,
            api_key=api_key,
            max_examples=max_examples,
            max_input_tokens=max_input_tokens,
            max_output_tokens=max_output_tokens,
            cost_warn_threshold=cost_warn_threshold
        )

        if summary:
            summaries.append(summary)

        total_cost += cost

        # Small delay between calls
        time.sleep(0.5)

    logger.info(f"Summarized {len(summaries)}/{len(cluster_data)} clusters. Total cost: {format_cost(total_cost)}")

    return summaries, total_cost


def summarize_enriched_cluster(
    texts: List[str],
    cluster_id: int,
    cluster_size: int,
    model: str,
    api_key: str,
    max_examples: int,
    max_input_tokens: int,
    max_output_tokens: int,
    cost_warn_threshold: float,
    max_retries: int = 2
) -> Tuple[Optional[EnrichedClusterSummary], float]:
    """
    Summarize a cluster with enriched analysis (persona, JTBD, context, alternatives).

    Args:
        texts: List of texts in cluster
        cluster_id: Cluster ID
        cluster_size: Size of cluster
        model: LLM model name
        api_key: OpenAI API key
        max_examples: Maximum examples to include
        max_input_tokens: Maximum input tokens
        max_output_tokens: Maximum output tokens (recommend 600+ for enriched)
        cost_warn_threshold: Cost threshold to warn (USD)
        max_retries: Maximum retry attempts

    Returns:
        Tuple of (EnrichedClusterSummary or None, cost in USD)
    """
    # Truncate texts to fit budget
    truncated_texts = truncate_texts_to_fit(
        texts[:max_examples],
        max_input_tokens,
        reserve_tokens=300  # More reserve for enriched prompt
    )

    # Build enriched prompts
    user_prompt = build_enriched_user_prompt(truncated_texts, max_examples)

    # Estimate cost
    estimated_input_tokens = estimate_tokens(ENRICHED_SYSTEM_PROMPT + user_prompt)
    estimated_cost = calculate_cost(estimated_input_tokens, max_output_tokens, model)

    logger.info(
        f"Cluster {cluster_id}: Estimated cost {format_cost(estimated_cost)} "
        f"({estimated_input_tokens} input + {max_output_tokens} output tokens)"
    )

    # Check cost threshold
    if estimated_cost > cost_warn_threshold:
        logger.warning(
            f"Cluster {cluster_id}: Estimated cost {format_cost(estimated_cost)} "
            f"exceeds threshold {format_cost(cost_warn_threshold)}. "
            f"Consider reducing max_examples or max_input_tokens."
        )

        # If way over budget, skip
        if estimated_cost > cost_warn_threshold * 2:
            logger.error(f"Cluster {cluster_id}: Cost too high, skipping.")
            return None, 0.0

    # Call LLM
    client = OpenAI(api_key=api_key)
    total_cost = 0.0

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": ENRICHED_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_output_tokens,
                temperature=0.7
            )

            # Calculate actual cost
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            total_cost = calculate_cost(input_tokens, output_tokens, model)

            logger.info(
                f"Cluster {cluster_id}: API call completed. "
                f"Actual cost: {format_cost(total_cost)} "
                f"({input_tokens} + {output_tokens} tokens)"
            )

            # Parse response
            response_text = response.choices[0].message.content
            data = parse_llm_response(response_text)

            if data is None:
                if attempt < max_retries:
                    logger.warning(f"Cluster {cluster_id}: Invalid JSON, retrying ({attempt + 1}/{max_retries})...")
                    time.sleep(1)
                    continue
                else:
                    logger.error(f"Cluster {cluster_id}: Failed to parse JSON after {max_retries} retries")
                    return None, total_cost

            # Validate required fields
            required_fields = [
                "title", "problem", "persona", "jtbd", "context",
                "monetizable", "mvp", "alternatives", "willingness_to_pay_signal", "pain_score_llm"
            ]
            if not all(field in data for field in required_fields):
                logger.error(f"Cluster {cluster_id}: Missing required fields in response")
                logger.debug(f"Got fields: {list(data.keys())}")
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                return None, total_cost

            # Create EnrichedClusterSummary
            summary = EnrichedClusterSummary(
                cluster_id=cluster_id,
                size=cluster_size,
                title=data["title"],
                problem=data["problem"],
                persona=data["persona"],
                jtbd=data["jtbd"],
                context=data["context"],
                monetizable=bool(data["monetizable"]),
                mvp=data["mvp"],
                alternatives=data["alternatives"] if isinstance(data["alternatives"], list) else [],
                willingness_to_pay_signal=data["willingness_to_pay_signal"],
                pain_score_llm=int(data["pain_score_llm"]) if data["pain_score_llm"] is not None else None
            )

            logger.info(f"Cluster {cluster_id}: Successfully summarized (enriched) - {summary.title}")
            return summary, total_cost

        except Exception as e:
            if attempt < max_retries:
                wait_time = 2 ** attempt
                logger.warning(
                    f"Cluster {cluster_id}: API error (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"Cluster {cluster_id}: Failed after {max_retries + 1} attempts: {e}")
                return None, 0.0

    return None, 0.0


def summarize_all_clusters_enriched(
    cluster_data: dict,
    model: str,
    api_key: str,
    max_examples: int,
    max_input_tokens: int,
    max_output_tokens: int,
    cost_warn_threshold: float
) -> Tuple[List[EnrichedClusterSummary], float]:
    """
    Summarize all clusters with enriched analysis.

    Args:
        cluster_data: Dict mapping cluster_id to list of items
        model: LLM model name
        api_key: OpenAI API key
        max_examples: Maximum examples per cluster
        max_input_tokens: Maximum input tokens
        max_output_tokens: Maximum output tokens (recommend 600+ for enriched)
        cost_warn_threshold: Cost threshold to warn (USD)

    Returns:
        Tuple of (list of EnrichedClusterSummary, total cost in USD)
    """
    summaries = []
    total_cost = 0.0

    logger.info(f"Summarizing {len(cluster_data)} clusters (enriched analysis)...")

    # Estimate total cost
    estimated_total = len(cluster_data) * calculate_cost(max_input_tokens, max_output_tokens, model)
    logger.info(f"Estimated total cost: {format_cost(estimated_total)}")

    for cluster_id, items in sorted(cluster_data.items()):
        # Extract texts
        texts = [item["meta"]["title"] for item in items]

        # Summarize with enriched analysis
        summary, cost = summarize_enriched_cluster(
            texts=texts,
            cluster_id=cluster_id,
            cluster_size=len(items),
            model=model,
            api_key=api_key,
            max_examples=max_examples,
            max_input_tokens=max_input_tokens,
            max_output_tokens=max_output_tokens,
            cost_warn_threshold=cost_warn_threshold
        )

        if summary:
            summaries.append(summary)

        total_cost += cost

        # Small delay between calls
        time.sleep(0.5)

    logger.info(f"Summarized {len(summaries)}/{len(cluster_data)} clusters (enriched). Total cost: {format_cost(total_cost)}")

    return summaries, total_cost
