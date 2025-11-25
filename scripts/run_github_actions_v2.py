"""
GitHub Actions wrapper for Need Scanner v2.0 pipeline.
Handles collection, processing, and export with backward compatibility.
"""

import sys
from pathlib import Path

# Ajouter le répertoire racine au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

import glob
import json
from datetime import datetime

from src.need_scanner.config import get_config
from src.need_scanner.schemas import Post
from src.need_scanner.processing.embed import embed_posts
from src.need_scanner.processing.cluster import cluster, get_cluster_data
from src.need_scanner.jobs.enriched_pipeline import run_enriched_pipeline
from src.need_scanner.export.csv_v2 import export_insights_to_csv


def main():
    """Pipeline v2.0 pour GitHub Actions."""

    # Configuration
    config = get_config()

    # Utiliser le même format de dossier que v1 pour compatibilité
    today = datetime.now().strftime("%Y%m%d")
    output_dir = Path(f"data/daily/{today}")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("🚀 Need Scanner v2.0 - GitHub Actions Pipeline")
    print("=" * 60)

    # 1. Charger les posts collectés
    print("\n[1/6] Loading posts...")
    posts_files = glob.glob("data/raw/posts_*.json")

    if not posts_files:
        print("❌ No posts found in data/raw/")
        print("   Collection step may have failed")
        sys.exit(1)

    all_posts = []
    for file_path in posts_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            posts_data = json.load(f)
            all_posts.extend([Post(**p) for p in posts_data])

    print(f"✓ Loaded {len(all_posts)} posts from {len(posts_files)} files")

    if len(all_posts) == 0:
        print("❌ No posts to process")
        sys.exit(1)

    # 2. Embeddings
    print("\n[2/6] Generating embeddings...")
    embeddings, metadata, embed_cost = embed_posts(
        posts=all_posts,
        model=config.ns_embed_model,
        api_key=config.openai_api_key,
        output_dir=output_dir
    )
    print(f"✓ Generated embeddings. Cost: ${embed_cost:.4f}")

    # 3. Clustering
    print("\n[3/6] Clustering...")
    n_clusters = min(config.ns_num_clusters, len(all_posts))
    labels, _ = cluster(embeddings, n_clusters=n_clusters)

    cluster_data = get_cluster_data(labels, metadata, embeddings)

    print(f"✓ Created {len(cluster_data)} clusters")

    # 4. Pipeline enrichi v2.0
    print("\n[4/6] Running enriched pipeline v2.0...")
    print("   ✓ Multi-model enrichment (light/heavy)")
    print("   ✓ Sector classification")
    print("   ✓ History-based deduplication")
    print("   ✓ MMR reranking for diversity")

    results = run_enriched_pipeline(
        cluster_data=cluster_data,
        embeddings=embeddings,
        labels=labels,
        output_dir=output_dir,
        use_mmr=True,
        use_history_penalty=True
    )

    print(f"✓ Pipeline complete")
    print(f"   - Clusters analyzed: {results['num_clusters']}")
    print(f"   - TOP insights: {results['num_top_insights']}")
    print(f"   - LLM cost: ${results['total_cost']:.4f}")

    # 5. Export CSV (backward compatibility)
    print("\n[5/6] Exporting to CSV...")

    csv_path = output_dir / "insights_enriched.csv"
    export_insights_to_csv(results['insights'], csv_path)

    print(f"✓ Exported to {csv_path}")

    # 6. Créer le fichier cluster_results.json pour compatibilité
    print("\n[6/6] Creating cluster_results.json...")

    cluster_results = {
        "date": today,
        "total_posts": len(all_posts),
        "num_clusters": results['num_clusters'],
        "num_insights": results['num_top_insights'],
        "cost_breakdown": {
            "embeddings": embed_cost,
            "llm": results['total_cost'],
            "total": embed_cost + results['total_cost']
        },
        "insights": [
            {
                "rank": ins.rank,
                "mmr_rank": ins.mmr_rank,
                "cluster_id": ins.cluster_id,
                "sector": ins.summary.sector,
                "title": ins.summary.title,
                "priority_score": ins.priority_score,
                "priority_score_adjusted": ins.priority_score_adjusted,
                "size": ins.summary.size
            }
            for ins in results['insights']
        ]
    }

    results_path = output_dir / "cluster_results.json"
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(cluster_results, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved to {results_path}")

    # Summary
    print("\n" + "=" * 60)
    print("✅ GITHUB ACTIONS PIPELINE COMPLETE")
    print("=" * 60)
    print(f"📊 Total posts: {len(all_posts)}")
    print(f"🎪 Clusters: {results['num_clusters']}")
    print(f"🏆 TOP insights: {results['num_top_insights']}")
    print(f"💰 Total cost: ${embed_cost + results['total_cost']:.4f}")
    print(f"📁 Output: {output_dir}")
    print("\nFiles created:")
    print(f"  - {csv_path.name}")
    print(f"  - {results_path.name}")
    print(f"  - enriched_results.json")
    print(f"  - embeddings.npy")
    print(f"  - meta.json")


if __name__ == "__main__":
    main()
