"""Founder fit scoring - evaluate alignment with founder profile and skillset."""

import json
import time
from typing import Optional
from loguru import logger
from openai import OpenAI


# Default founder profile (can be overridden via config)
DEFAULT_FOUNDER_PROFILE = """
Profil fondateur :
- Développeur fullstack / product maker
- Compétences : Python, JS/TS, React, Node.js, APIs, automation
- Expérience : SaaS B2B, dev tools, no-code tools, productivité
- Affinités sectorielles :
  ✅ SaaS B2B, dev tools, business automation, éducation en ligne, PME/freelance tools
  ⚠️ Neutre : e-commerce, marketing tools, consumer apps
  ❌ Moins à l'aise : santé réglementée, hardware complexe, deep biotech, industrie lourde, finance ultra-réglementée
- Budget : Solo bootstrapping, solutions lean, MVP en quelques semaines
- Valeurs : Impact utilisateur, problèmes concrets, éviter les vanity metrics
"""


def calculate_founder_fit_score(
    cluster_title: str,
    cluster_problem: str,
    cluster_persona: str,
    cluster_sector: Optional[str],
    model: str,
    api_key: str,
    founder_profile: Optional[str] = None,
    max_retries: int = 2
) -> Optional[float]:
    """
    Calculate founder fit score using LLM.

    Evaluates how well the opportunity matches the founder's profile, skills, and interests.

    Args:
        cluster_title: Short title of the problem
        cluster_problem: Problem description
        cluster_persona: Target persona/user
        cluster_sector: Sector classification (optional)
        model: LLM model name (recommend gpt-4o-mini for cost)
        api_key: OpenAI API key
        founder_profile: Founder profile description (optional, uses default if None)
        max_retries: Maximum retry attempts

    Returns:
        Founder fit score (1.0 to 10.0) or None if failed
    """
    profile = founder_profile or DEFAULT_FOUNDER_PROFILE

    system_prompt = """Tu es un conseiller en création d'entreprise qui évalue l'adéquation entre une opportunité et le profil d'un fondateur.
Réponds uniquement en JSON strict avec un score de fit."""

    user_prompt = f"""Évalue l'ADÉQUATION FONDATEUR pour cette opportunité :

{profile}

Opportunité à évaluer :
Titre : {cluster_title}
Problème : {cluster_problem}
Persona cible : {cluster_persona}
Secteur : {cluster_sector or 'Non spécifié'}

Score de founder fit (1-10) basé sur :
- **Compétences techniques** : Le fondateur a-t-il les skills pour construire la solution ?
- **Affinité sectorielle** : Le secteur correspond-il à ses domaines de prédilection ?
- **Complexité exécution** : Peut-il construire un MVP en quelques semaines, solo ou avec ressources limitées ?
- **Connaissances domaine** : Comprend-il naturellement les besoins de la persona cible ?
- **Contraintes** : Réglementations lourdes, hardware, R&D longue → mauvais fit

Échelle DISCRIMINANTE (utilise TOUTE l'échelle 1-10) :
- 1-3 : Très mauvais fit (compétences manquantes, secteur inadapté, trop complexe)
- 4-6 : Fit moyen/possible mais pas idéal (certaines compétences à acquérir, secteur neutre)
- 7-8 : Bon fit (compétences alignées, secteur favorable, exécution réaliste)
- 9-10 : Excellent fit (compétences parfaites, sweet spot sectoriel, persona familière)

Sois RÉALISTE et DISCRIMINANT : la plupart des opportunités sont entre 4-7.

Réponds UNIQUEMENT en JSON strict :
{{"founder_fit_score": 6, "justification": "Une phrase expliquant le score"}}"""

    client = OpenAI(api_key=api_key)

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )

            response_text = response.choices[0].message.content

            # Parse JSON
            try:
                data = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to extract from markdown
                if "```json" in response_text:
                    start = response_text.find("```json") + 7
                    end = response_text.find("```", start)
                    json_str = response_text[start:end].strip()
                    data = json.loads(json_str)
                elif "```" in response_text:
                    start = response_text.find("```") + 3
                    end = response_text.find("```", start)
                    json_str = response_text[start:end].strip()
                    data = json.loads(json_str)
                else:
                    raise

            if "founder_fit_score" not in data:
                logger.warning(f"Missing founder_fit_score in LLM response")
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                return None

            fit_score = float(data["founder_fit_score"])
            justification = data.get("justification", "")

            # Clamp to 1-10
            fit_score = max(1.0, min(10.0, fit_score))

            logger.debug(f"Founder Fit: {fit_score:.1f} - {justification}")
            return fit_score

        except Exception as e:
            if attempt < max_retries:
                wait_time = 2 ** attempt
                logger.warning(
                    f"Founder fit scoring error (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to calculate founder fit score after {max_retries + 1} attempts: {e}")
                return None

    return None


def calculate_batch_founder_fit_scores(
    cluster_summaries: dict,
    model: str,
    api_key: str,
    founder_profile: Optional[str] = None
) -> dict:
    """
    Calculate founder fit scores for multiple clusters.

    Args:
        cluster_summaries: Dict mapping cluster_id to summary dict
        model: LLM model name
        api_key: OpenAI API key
        founder_profile: Founder profile description (optional)

    Returns:
        Dict mapping cluster_id to founder_fit_score
    """
    logger.info("Calculating founder fit scores...")

    fit_scores = {}

    for cluster_id, summary in cluster_summaries.items():
        fit_score = calculate_founder_fit_score(
            cluster_title=summary.get("title", ""),
            cluster_problem=summary.get("problem", summary.get("description", "")),
            cluster_persona=summary.get("persona", "Unknown"),
            cluster_sector=summary.get("sector"),
            model=model,
            api_key=api_key,
            founder_profile=founder_profile
        )

        if fit_score is not None:
            fit_scores[cluster_id] = fit_score
            logger.info(f"Cluster {cluster_id}: Founder fit = {fit_score:.1f}")
        else:
            # Default to neutral if failed
            fit_scores[cluster_id] = 5.0
            logger.warning(f"Cluster {cluster_id}: Failed to score, using default 5.0")

        # Small delay to avoid rate limits
        time.sleep(0.3)

    logger.info(f"Calculated founder fit for {len(fit_scores)} clusters")

    # Show top fits
    sorted_fits = sorted(fit_scores.items(), key=lambda x: x[1], reverse=True)
    logger.info("Top 5 best founder fits:")
    for cluster_id, score in sorted_fits[:5]:
        summary = cluster_summaries.get(cluster_id, {})
        title = summary.get("title", f"Cluster {cluster_id}")
        logger.info(f"  {title}: {score:.1f}")

    return fit_scores
