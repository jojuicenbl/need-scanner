"""
Example usage of Need Scanner FastAPI.

This script demonstrates how to use the Need Scanner API programmatically
using Python's requests library.
"""

import requests
import json
from typing import Dict, List

# Configuration
BASE_URL = "http://localhost:8000"


def check_health() -> bool:
    """Check if API is healthy."""
    response = requests.get(f"{BASE_URL}/health")
    if response.status_code == 200:
        print("✅ API is healthy")
        return True
    else:
        print("❌ API is not responding")
        return False


def create_scan(mode: str = "deep", max_insights: int = 15) -> str:
    """
    Create a new scan.

    Args:
        mode: "light" or "deep"
        max_insights: Maximum number of insights to generate

    Returns:
        run_id: ID of the created run
    """
    print(f"\n🚀 Creating scan (mode={mode}, max_insights={max_insights})...")

    response = requests.post(
        f"{BASE_URL}/runs",
        json={
            "mode": mode,
            "max_insights": max_insights
        }
    )

    if response.status_code == 200:
        result = response.json()
        run_id = result["run_id"]
        print(f"✅ Scan created: {run_id}")
        print(f"   Status: {result['status']}")
        return run_id
    else:
        print(f"❌ Failed to create scan: {response.status_code}")
        print(f"   Error: {response.json()}")
        return None


def list_runs(limit: int = 5) -> List[Dict]:
    """
    List recent runs.

    Args:
        limit: Maximum number of runs to return

    Returns:
        List of run dictionaries
    """
    print(f"\n📋 Listing last {limit} runs...")

    response = requests.get(f"{BASE_URL}/runs?limit={limit}")

    if response.status_code == 200:
        runs = response.json()
        print(f"✅ Found {len(runs)} runs")
        for run in runs:
            print(f"   - {run['id']}: {run['nb_insights']} insights "
                  f"(mode={run['mode']}, cost=${run['total_cost_usd']:.4f})")
        return runs
    else:
        print(f"❌ Failed to list runs: {response.status_code}")
        return []


def get_insights(
    run_id: str,
    sector: str = None,
    min_priority: float = None,
    limit: int = None
) -> List[Dict]:
    """
    Get insights for a run.

    Args:
        run_id: Run identifier
        sector: Filter by sector (optional)
        min_priority: Minimum priority score (optional)
        limit: Maximum results (optional)

    Returns:
        List of insight dictionaries
    """
    print(f"\n📊 Getting insights for run {run_id}...")

    # Build query parameters
    params = {}
    if sector:
        params["sector"] = sector
    if min_priority:
        params["min_priority"] = min_priority
    if limit:
        params["limit"] = limit

    response = requests.get(
        f"{BASE_URL}/runs/{run_id}/insights",
        params=params
    )

    if response.status_code == 200:
        insights = response.json()
        print(f"✅ Found {len(insights)} insights")

        # Display top 3
        for i, insight in enumerate(insights[:3], 1):
            print(f"   #{i}: {insight['title']}")
            print(f"       Sector: {insight.get('sector', 'N/A')} | "
                  f"Priority: {insight['priority_score']:.2f} | "
                  f"Pain: {insight.get('pain_score_final', 0):.1f}")

        return insights
    else:
        print(f"❌ Failed to get insights: {response.status_code}")
        return []


def get_insight_detail(insight_id: str) -> Dict:
    """
    Get complete details for an insight.

    Args:
        insight_id: Insight identifier

    Returns:
        Insight dictionary
    """
    print(f"\n🔍 Getting details for insight {insight_id}...")

    response = requests.get(f"{BASE_URL}/insights/{insight_id}")

    if response.status_code == 200:
        insight = response.json()
        print(f"✅ Retrieved insight details")
        print(f"   Title: {insight['title']}")
        print(f"   Sector: {insight.get('sector', 'N/A')}")
        print(f"   Priority: {insight['priority_score']:.2f}")
        print(f"   Persona: {insight.get('persona', 'N/A')}")
        print(f"   MVP: {insight.get('mvp', 'N/A')[:100]}...")
        return insight
    else:
        print(f"❌ Failed to get insight: {response.status_code}")
        return None


def explore_insight(insight_id: str, model: str = None) -> Dict:
    """
    Perform deep exploration of an insight.

    Args:
        insight_id: Insight identifier
        model: LLM model to use (optional, defaults to heavy model)

    Returns:
        Exploration results
    """
    print(f"\n🔬 Exploring insight {insight_id}...")

    payload = {}
    if model:
        payload["model"] = model

    response = requests.post(
        f"{BASE_URL}/insights/{insight_id}/explore",
        json=payload
    )

    if response.status_code == 200:
        exploration = response.json()
        print(f"✅ Exploration complete")
        print(f"   Model: {exploration['model_used']}")
        print(f"   Cost: ${exploration['cost_usd']:.4f}")
        print(f"   Monetization ideas: {len(exploration.get('monetization_ideas', []))}")
        print(f"   Product variants: {len(exploration.get('product_variants', []))}")
        print(f"   Validation steps: {len(exploration.get('validation_steps', []))}")
        return exploration
    else:
        print(f"❌ Failed to explore insight: {response.status_code}")
        return None


def get_explorations(insight_id: str) -> List[Dict]:
    """
    Get exploration history for an insight.

    Args:
        insight_id: Insight identifier

    Returns:
        List of exploration summaries
    """
    print(f"\n📜 Getting exploration history for {insight_id}...")

    response = requests.get(f"{BASE_URL}/insights/{insight_id}/explorations")

    if response.status_code == 200:
        explorations = response.json()
        print(f"✅ Found {len(explorations)} explorations")
        for exp in explorations:
            print(f"   - ID {exp['id']}: {exp.get('model_used', 'N/A')} "
                  f"({exp['created_at']})")
        return explorations
    else:
        print(f"❌ Failed to get explorations: {response.status_code}")
        return []


def main():
    """Run example workflow."""
    print("=" * 60)
    print("Need Scanner API - Example Usage")
    print("=" * 60)

    # 1. Check health
    if not check_health():
        print("\n⚠️  API is not running. Start it with:")
        print("   uvicorn need_scanner.api:app --reload")
        return

    # 2. List existing runs
    runs = list_runs(limit=3)

    if runs:
        # Use the most recent run
        run_id = runs[0]["id"]
        print(f"\n✨ Using most recent run: {run_id}")

        # 3. Get insights
        insights = get_insights(run_id, limit=5)

        if insights:
            # 4. Get detail of first insight
            insight_id = insights[0]["id"]
            insight = get_insight_detail(insight_id)

            # 5. Explore the insight (commented out to avoid costs)
            print("\n💡 To explore this insight, uncomment the following lines:")
            print(f"   # exploration = explore_insight('{insight_id}')")
            print(f"   # print(exploration['full_text'])")

            # Uncomment to actually run exploration:
            # exploration = explore_insight(insight_id)
            # if exploration:
            #     print("\n📝 Exploration text:")
            #     print(exploration["full_text"])

            # 6. Check exploration history
            get_explorations(insight_id)
    else:
        print("\n💭 No runs found. Create one with:")
        print("   run_id = create_scan(mode='light', max_insights=5)")
        print("\nNote: This requires data in data/raw/posts_*.json")

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
