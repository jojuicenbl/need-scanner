"""Willingness-to-Pay (WTP) signal detection for posts."""

import re
from typing import Dict, List, Optional
from loguru import logger

from ..schemas import Post


# WTP keyword patterns (English and French)
WTP_PATTERNS = {
    # Direct payment willingness
    "direct_payment": [
        r"\b(willing to pay|would pay|ready to pay|will pay)\b",
        r"\b(take my money|shut up and take my money)\b",
        r"\b(subscription|subscribe|monthly|yearly) (fee|cost|price|plan)\b",
        r"\b(how much|what's the (price|cost)|pricing)\b",
        r"\b(prêt à payer|accepte de payer|payerais)\b",
        r"\b(combien|quel (prix|tarif)|coût)\b",
    ],

    # Budget mentions
    "budget": [
        r"\$\d+",  # Dollar amounts
        r"\b\d+\s*(dollars?|USD|EUR|€|\$)\b",
        r"\b(budget|spend|invest|cost)\s*(is|of|up to)?\s*\$?\d+",
        r"\b(budget|dépense|investir|coûter)\s*(de|d'environ)?\s*\d+",
    ],

    # Pricing inquiries
    "pricing_inquiry": [
        r"\b(price|pricing|cost|fee|rate|charge)\b",
        r"\b(affordable|cheap|expensive|worth it|value for money)\b",
        r"\b(free (trial|version|plan)|freemium|paid (plan|tier|version))\b",
        r"\b(prix|tarif|coût|frais|gratuit|payant)\b",
    ],

    # Comparison signals
    "comparison": [
        r"\b(alternative to|better than|cheaper than|more affordable)\b",
        r"\b(worth upgrading|worth paying|worth the (cost|price))\b",
        r"\b(compare|comparison|vs|versus)\b",
        r"\b(alternatif|alternative à|moins cher|plus abordable)\b",
        r"\b(vaut le coup|vaut la peine|comparaison)\b",
    ],

    # Urgency + money signals
    "urgent_need": [
        r"\b(need (now|asap|urgently))\b.*\b(pay|budget|cost|price)\b",
        r"\b(desperate|critical|must have)\b.*\b(pay|budget|invest)\b",
        r"\b(besoin urgent|besoin maintenant)\b.*\b(payer|budget|tarif)\b",
    ],

    # Existing paid tool dissatisfaction
    "dissatisfaction": [
        r"\b(paying for|subscribed to)\b.*\b(but|however|doesn't|not)\b",
        r"\b(cancel|canceling|switching from|leaving)\b.*\b(subscription|plan|service)\b",
        r"\b(overpriced|too expensive|not worth)\b",
        r"\b(trop cher|trop coûteux|pas worth)\b",
        r"\b(résilie|annule|change de)\b.*\b(abonnement|service)\b",
    ],

    # ROI mentions
    "roi": [
        r"\b(ROI|return on investment|save (time|money)|efficiency)\b",
        r"\b((would|will) pay if it (saves|helps))\b",
        r"\b(retour sur investissement|gagner du temps|économiser)\b",
        r"\b(rentable|rentabilité|efficacité)\b",
    ],
}


def detect_wtp_signals(post: Post) -> Dict[str, any]:
    """
    Detect willingness-to-pay signals in a post.

    Args:
        post: Post object

    Returns:
        Dictionary with WTP detection results:
        - has_wtp: bool (True if any WTP signal detected)
        - signal_types: List of detected signal types
        - signal_count: Total number of signals detected
        - examples: List of matching text snippets (up to 3)
    """
    text = f"{post.title} {post.body}".strip()
    text_lower = text.lower()

    detected_types = []
    examples = []
    total_count = 0

    for signal_type, patterns in WTP_PATTERNS.items():
        for pattern in patterns:
            matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
            if matches:
                detected_types.append(signal_type)
                total_count += len(matches)

                # Extract matching snippets with context
                for match in matches[:2]:  # Max 2 examples per pattern
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 30)
                    snippet = text[start:end].strip()
                    if len(examples) < 3:  # Max 3 examples total
                        examples.append(snippet)

                break  # Only count first matching pattern per type

    return {
        "has_wtp": len(detected_types) > 0,
        "signal_types": list(set(detected_types)),  # Deduplicate
        "signal_count": total_count,
        "examples": examples[:3]  # Max 3 examples
    }


def enrich_posts_with_wtp(posts: List[Post]) -> List[Post]:
    """
    Enrich posts with WTP signal detection.

    Args:
        posts: List of Post objects

    Returns:
        List of Post objects with wtp_signals field populated
    """
    logger.info(f"Detecting WTP signals in {len(posts)} posts...")

    posts_with_wtp = 0
    signal_type_counts = {}

    for post in posts:
        wtp_data = detect_wtp_signals(post)

        # Set the wtp_signals field
        post.wtp_signals = wtp_data

        if wtp_data["has_wtp"]:
            posts_with_wtp += 1

            # Count signal types
            for signal_type in wtp_data["signal_types"]:
                signal_type_counts[signal_type] = signal_type_counts.get(signal_type, 0) + 1

    logger.info(f"WTP signals detected in {posts_with_wtp}/{len(posts)} posts ({100*posts_with_wtp/len(posts):.1f}%)")
    if signal_type_counts:
        logger.info(f"Signal type distribution: {signal_type_counts}")

    return posts


def filter_by_wtp(posts: List[Post], require_wtp: bool = True) -> List[Post]:
    """
    Filter posts based on WTP signals.

    Args:
        posts: List of Post objects (must have wtp_signals field)
        require_wtp: If True, only keep posts with WTP signals

    Returns:
        Filtered list of posts
    """
    if require_wtp:
        filtered = [p for p in posts if getattr(p, 'wtp_signals', {}).get('has_wtp', False)]
        logger.info(f"Filtered to {len(filtered)}/{len(posts)} posts with WTP signals")
        return filtered

    return posts


def get_wtp_score(post: Post) -> float:
    """
    Calculate a WTP score for a post (0.0 to 10.0).

    Higher score = stronger WTP signals

    Args:
        post: Post object with wtp_signals field

    Returns:
        WTP score (0.0 to 10.0)
    """
    wtp_data = getattr(post, 'wtp_signals', None)

    if wtp_data is None or not wtp_data.get('has_wtp', False):
        return 0.0

    # Base score from signal count
    signal_count = wtp_data.get('signal_count', 0)
    base_score = min(signal_count * 2.0, 6.0)  # Max 6.0 from count

    # Bonus for specific high-value signal types
    signal_types = wtp_data.get('signal_types', [])
    type_bonuses = {
        "direct_payment": 3.0,
        "budget": 2.5,
        "dissatisfaction": 2.0,
        "urgent_need": 1.5,
        "roi": 1.0,
        "pricing_inquiry": 0.5,
        "comparison": 0.5,
    }

    bonus_score = sum(type_bonuses.get(st, 0) for st in signal_types)
    bonus_score = min(bonus_score, 4.0)  # Max 4.0 from bonuses

    total_score = min(base_score + bonus_score, 10.0)

    return round(total_score, 1)
