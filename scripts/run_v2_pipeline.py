"""
Script personnalisé pour exécuter le pipeline Need Scanner v2.0.
Adapté à votre workflow existant.
"""

import sys
from pathlib import Path

# Ajouter le répertoire racine au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

import glob
import json

from src.need_scanner.config import get_config
from src.need_scanner.schemas import Post
from src.need_scanner.processing.embed import embed_posts
from src.need_scanner.processing.cluster import cluster, get_cluster_data
from src.need_scanner.jobs.enriched_pipeline import run_enriched_pipeline


def main():
    """Pipeline v2.0 avec toutes les améliorations."""

    # Configuration
    config = get_config()
    output_dir = Path("data/results_v2")

    # Créer le dossier de sortie s'il n'existe pas
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("🚀 Need Scanner v2.0 - Enhanced Pipeline")
    print("=" * 60)

    # 1. Charger les posts collectés
    print("\n[1/5] Loading posts...")
    posts_files = glob.glob("data/raw/posts_*.json")

    if not posts_files:
        print("❌ No posts found in data/raw/")
        print("   Run: python -m need_scanner collect-reddit-multi --limit-per-sub 30")
        return

    all_posts = []
    for file_path in posts_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            posts_data = json.load(f)
            all_posts.extend([Post(**p) for p in posts_data])

    print(f"✓ Loaded {len(all_posts)} posts from {len(posts_files)} files")

    # 2. Filtrage optionnel (comme en v1.0)
    # Vous pouvez ajouter des filtres ici si besoin

    # 3. Embeddings
    print("\n[2/5] Generating embeddings...")
    embeddings, metadata, embed_cost = embed_posts(
        posts=all_posts,
        model=config.ns_embed_model,
        api_key=config.openai_api_key,
        output_dir=output_dir
    )
    print(f"✓ Generated embeddings. Cost: ${embed_cost:.4f}")

    # 4. Clustering
    print("\n[3/5] Clustering...")
    n_clusters = min(config.ns_num_clusters, len(all_posts))
    labels, _ = cluster(embeddings, n_clusters=n_clusters)

    cluster_data = get_cluster_data(labels, metadata, embeddings)

    print(f"✓ Created {len(cluster_data)} clusters")

    # 5. Pipeline enrichi v2.0
    print("\n[4/5] Running enriched pipeline (v2.0)...")
    print("   - Multi-model enrichment (light/heavy)")
    print("   - Sector classification")
    print("   - History-based deduplication")
    print("   - MMR reranking for diversity")

    results = run_enriched_pipeline(
        cluster_data=cluster_data,
        embeddings=embeddings,
        labels=labels,
        output_dir=output_dir,
        use_mmr=True,
        use_history_penalty=True
    )

    # 6. Résumé
    print("\n[5/5] Summary")
    print("=" * 60)
    print(f"✅ Pipeline complete!")
    print(f"   Total clusters: {results['num_clusters']}")
    print(f"   TOP insights: {results['num_top_insights']}")
    print(f"   Total cost: ${results['total_cost']:.4f}")
    print(f"   Results saved to: {output_dir}")

    # Afficher TOP 5
    print("\n🏆 TOP 5 INSIGHTS:")
    for insight in results['insights'][:5]:
        sector_emoji = {
            'dev_tools': '💻',
            'business_pme': '💼',
            'health_wellbeing': '🏥',
            'education_learning': '📚',
            'ecommerce_retail': '🛒',
            'marketing_sales': '📊',
        }.get(insight.summary.sector, '📌')

        print(f"\n  #{insight.rank} {sector_emoji} [{insight.summary.sector}]")
        print(f"     {insight.summary.title}")
        print(f"     Priority: {insight.priority_score:.2f} → {insight.priority_score_adjusted:.2f}")
        print(f"     MMR rank: {insight.mmr_rank}")

    print("\n" + "=" * 60)
    print("📖 See docs/ENGINE_IMPROVEMENTS.md for detailed documentation")
    print("=" * 60)


if __name__ == "__main__":
    main()