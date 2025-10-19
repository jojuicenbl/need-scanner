"""Intent classification for posts (pain, request, howto, promo, news, other)."""

import re
from typing import Optional, List
from loguru import logger
from openai import OpenAI

from ..schemas import Post
from ..config import get_config


# Rule-based keyword patterns for each intent
INTENT_PATTERNS = {
    "pain": [
        r"\b(struggling|frustrated|annoyed|angry|hate|difficult|impossible|broken|fails?|sucks?)\b",
        r"\b(problem|issue|bug|error|pain|headache|nightmare|disaster)\b",
        r"\b(doesn't work|not working|won't work|can't|unable to)\b",
        r"\b(tired of|sick of|fed up)\b",
        r"\b(why (is|does)|how come)\b",
        r"(help|sos|urgent)\s*(me|please|!)",
    ],
    "request": [
        r"\b(looking for|need|want|searching for|seeking|require)\b.*\b(tool|solution|app|software|platform|service)\b",
        r"\b(recommend|suggestion|advice).*\b(tool|app|software|platform)\b",
        r"\b(what do you (use|recommend)|which tool|best tool|any tools?)\b",
        r"\b(alternative to|replacement for|instead of)\b",
        r"\b(does anyone (use|know)|has anyone tried)\b",
        r"\b(tool|solution|app) (for|to help with)\b",
    ],
    "howto": [
        r"\b(how (do|to|can)|ways? to)\b",
        r"\b(tutorial|guide|walkthrough|instructions)\b",
        r"\b(tips?|tricks?|best practices)\b",
        r"\b(learn|teach me|show me)\b",
        r"\b(step by step)\b",
    ],
    "promo": [
        r"\b(i (built|made|created|launched|released)|check out (my|our)|announcing)\b",
        r"\b(new (tool|app|product|service|platform))\b",
        r"\b(feedback (on|for) (my|our)|try (my|our))\b",
        r"\b(just launched|now available|coming soon)\b",
        r"\b(sign up|get started|join (us|now)|limited offer)\b",
    ],
    "news": [
        r"\b(announced|announcement|releases?|update|version \d+)\b",
        r"\b(according to|reports?|study shows?|research)\b",
        r"\b(breaking|latest news|just heard)\b",
        r"\b(acquired|acquires|acquisition|merger)\b",
    ],
}


def _rule_based_intent(text: str) -> Optional[str]:
    """
    Classify intent using keyword patterns.

    Args:
        text: Combined title + body text

    Returns:
        Intent label or None if no clear match
    """
    text_lower = text.lower()

    # Score each intent based on pattern matches
    scores = {}
    for intent, patterns in INTENT_PATTERNS.items():
        score = 0
        for pattern in patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            score += len(matches)
        scores[intent] = score

    # Return intent with highest score (if > 0)
    if max(scores.values()) > 0:
        return max(scores, key=scores.get)

    return None


def _llm_intent(text: str, client: OpenAI) -> str:
    """
    Classify intent using LLM fallback for ambiguous cases.

    Args:
        text: Combined title + body text
        client: OpenAI client

    Returns:
        Intent label
    """
    # Truncate text to avoid excessive costs
    max_chars = 800
    if len(text) > max_chars:
        text = text[:max_chars] + "..."

    system_prompt = """Tu es un classificateur d'intentions pour des posts utilisateurs.
Classe chaque post dans UNE catégorie parmi :
- pain : l'utilisateur exprime une frustration, un problème, une difficulté
- request : l'utilisateur cherche un outil, une solution, une recommandation
- howto : l'utilisateur demande comment faire quelque chose
- promo : l'utilisateur fait la promotion d'un produit/service
- news : partage d'actualité, annonce, mise à jour
- other : autre (question générale, discussion, etc.)

Réponds UNIQUEMENT avec le label (un mot)."""

    user_prompt = f"""Texte :
{text}

Intention :"""

    try:
        config = get_config()
        response = client.chat.completions.create(
            model=config.ns_summary_model,  # Use gpt-4o-mini
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=10
        )

        intent = response.choices[0].message.content.strip().lower()

        # Validate intent
        valid_intents = ["pain", "request", "howto", "promo", "news", "other"]
        if intent in valid_intents:
            return intent
        else:
            logger.warning(f"Invalid LLM intent '{intent}', defaulting to 'other'")
            return "other"

    except Exception as e:
        logger.warning(f"LLM intent classification failed: {e}, defaulting to 'other'")
        return "other"


def tag_intent(post: Post, use_llm_fallback: bool = False) -> str:
    """
    Classify the intent of a post.

    Args:
        post: Post object
        use_llm_fallback: If True, use LLM for ambiguous cases (costs money)

    Returns:
        Intent label: pain, request, howto, promo, news, other
    """
    # Combine title and body for analysis
    text = f"{post.title} {post.body}".strip()

    # Try rule-based classification first
    intent = _rule_based_intent(text)

    # If no clear match and LLM fallback enabled, use LLM
    if intent is None and use_llm_fallback:
        try:
            config = get_config()
            client = OpenAI(api_key=config.openai_api_key)
            intent = _llm_intent(text, client)
            logger.debug(f"Post {post.id}: LLM classified as '{intent}'")
        except Exception as e:
            logger.warning(f"LLM fallback failed for post {post.id}: {e}")
            intent = "other"

    # Default to "other" if still no match
    if intent is None:
        intent = "other"

    return intent


def filter_by_intent(
    posts: List[Post],
    allowed_intents: List[str] = None,
    use_llm_fallback: bool = False
) -> List[Post]:
    """
    Tag and filter posts by intent.

    Args:
        posts: List of posts
        allowed_intents: List of intents to keep (default: ["pain", "request"])
        use_llm_fallback: Whether to use LLM for ambiguous cases

    Returns:
        Filtered list of posts with intent field populated
    """
    if allowed_intents is None:
        allowed_intents = ["pain", "request"]

    logger.info(f"Classifying intent for {len(posts)} posts...")
    logger.info(f"Allowed intents: {allowed_intents}")
    logger.info(f"LLM fallback: {'enabled' if use_llm_fallback else 'disabled'}")

    filtered_posts = []
    intent_counts = {}

    for post in posts:
        intent = tag_intent(post, use_llm_fallback=use_llm_fallback)
        post.intent = intent

        # Count intents
        intent_counts[intent] = intent_counts.get(intent, 0) + 1

        # Filter by allowed intents
        if intent in allowed_intents:
            filtered_posts.append(post)

    logger.info(f"Intent distribution: {intent_counts}")
    logger.info(f"Kept {len(filtered_posts)}/{len(posts)} posts with intents: {allowed_intents}")

    return filtered_posts
