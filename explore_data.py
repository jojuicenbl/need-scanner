#!/usr/bin/env python
"""Script interactif pour explorer les données collectées."""

import json
from pathlib import Path
from collections import Counter
from datetime import datetime


def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def explore_raw_data():
    """Explore raw data files."""
    print_header("📁 DONNÉES BRUTES")

    raw_dir = Path("data/raw")
    files = sorted(raw_dir.glob("posts_*.json"))

    if not files:
        print("❌ Aucun fichier trouvé dans data/raw/")
        return

    total_posts = 0
    all_sources = Counter()

    for file_path in files:
        with open(file_path) as f:
            data = json.load(f)

        size_kb = file_path.stat().st_size / 1024
        mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)

        # Count sources
        sources = Counter(post.get('source', 'unknown') for post in data)
        all_sources.update(sources)
        total_posts += len(data)

        print(f"\n📄 {file_path.name}")
        print(f"   📊 Taille: {size_kb:.1f} KB")
        print(f"   📅 Date: {mod_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"   📝 Posts: {len(data)}")
        print(f"   🔗 Sources: {dict(sources)}")

        # Show sample titles
        if data:
            print(f"   💬 Exemples:")
            for i, post in enumerate(data[:3], 1):
                title = post.get('title', '')[:60]
                source = post.get('source', '?')
                score = post.get('score', 0)
                print(f"      {i}. [{source}] {title}... (score: {score})")

    print(f"\n📊 TOTAL: {total_posts} posts | Sources: {dict(all_sources)}")


def explore_insights():
    """Explore analysis results."""
    print_header("📊 RÉSULTATS D'ANALYSE")

    # Find latest cluster_results.json
    results_files = list(Path("data").glob("**/cluster_results.json"))

    if not results_files:
        print("❌ Aucun fichier d'analyse trouvé")
        return

    # Show all available results
    print("\nFichiers d'analyse disponibles:")
    for i, file_path in enumerate(sorted(results_files), 1):
        rel_path = file_path.relative_to(Path("data"))
        mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
        print(f"   {i}. {rel_path} ({mod_time.strftime('%Y-%m-%d %H:%M')})")

    # Use most recent
    latest = sorted(results_files, key=lambda p: p.stat().st_mtime)[-1]
    print(f"\n📖 Analyse du fichier: {latest.relative_to(Path('data'))}")

    with open(latest) as f:
        results = json.load(f)

    # Statistics
    stats = results.get('statistics', {})
    print(f"\n📈 STATISTIQUES:")
    for key, value in stats.items():
        if 'cost' in key:
            print(f"   {key}: ${value:.4f}")
        else:
            print(f"   {key}: {value}")

    # Insights
    insights = results.get('insights', [])
    print(f"\n🔍 INSIGHTS GÉNÉRÉS: {len(insights)}")

    for insight in insights:
        summary = insight.get('summary', {})
        examples = insight.get('examples', [])

        print(f"\n{'─' * 70}")
        print(f"📌 Cluster {insight.get('cluster_id')} - {summary.get('title')}")
        print(f"   📊 Taille: {summary.get('size')} posts")
        print(f"   💰 Monétisable: {'✅ Oui' if summary.get('monetizable') else '❌ Non'}")
        print(f"   😣 Pain Score LLM: {summary.get('pain_score_llm', 'N/A')}/10")
        print(f"   🎯 Pain Score Final: {insight.get('pain_score_final', 'N/A')}/10")
        print(f"   📝 Description:")
        desc = summary.get('description', '')
        print(f"      {desc[:200]}{'...' if len(desc) > 200 else ''}")
        print(f"   💡 MVP: {summary.get('mvp', 'N/A')}")

        if examples:
            print(f"   🔗 Exemples ({len(examples)} posts):")
            for i, ex in enumerate(examples[:3], 1):
                title = ex.get('title', '')[:50]
                url = ex.get('url', '')
                score = ex.get('score', 0)
                print(f"      {i}. {title}... (score: {score})")
                if url:
                    print(f"         {url}")


def show_post_details(source='all'):
    """Show detailed post information."""
    print_header(f"🔍 DÉTAILS DES POSTS ({source.upper()})")

    raw_dir = Path("data/raw")

    if source == 'all':
        pattern = "posts_*.json"
    else:
        pattern = f"posts_{source}_*.json"

    files = sorted(raw_dir.glob(pattern))

    if not files:
        print(f"❌ Aucun fichier trouvé pour: {pattern}")
        return

    # Use most recent file
    latest = files[-1]
    with open(latest) as f:
        posts = json.load(f)

    print(f"\n📖 Fichier: {latest.name}")
    print(f"📝 Posts: {len(posts)}")

    # Stats by intent (if available)
    intents = Counter(p.get('intent') for p in posts if p.get('intent'))
    if intents:
        print(f"\n🏷️  Intents:")
        for intent, count in intents.most_common():
            print(f"   {intent}: {count}")

    # Stats by language (if available)
    langs = Counter(p.get('lang') for p in posts if p.get('lang'))
    if langs:
        print(f"\n🌍 Langues:")
        for lang, count in langs.most_common():
            print(f"   {lang}: {count}")

    # Top posts by score
    top_posts = sorted(posts, key=lambda p: p.get('score', 0), reverse=True)[:5]
    print(f"\n⭐ TOP 5 PAR SCORE:")
    for i, post in enumerate(top_posts, 1):
        title = post.get('title', '')[:60]
        score = post.get('score', 0)
        comments = post.get('comments_count', post.get('num_comments', 0))
        source_name = post.get('source', '?')
        print(f"   {i}. [{source_name}] {title}...")
        print(f"      Score: {score} | Comments: {comments}")


def main():
    """Main interactive menu."""
    print("=" * 70)
    print("  🔍 EXPLORATEUR DE DONNÉES - need_scanner")
    print("=" * 70)

    while True:
        print("\n📋 MENU:")
        print("  1. Explorer les données brutes (data/raw/)")
        print("  2. Explorer les résultats d'analyse (insights)")
        print("  3. Détails posts Reddit")
        print("  4. Détails posts Hacker News")
        print("  5. Détails posts RSS")
        print("  6. Détails posts multi-sources")
        print("  0. Quitter")

        choice = input("\n👉 Choix (0-6): ").strip()

        if choice == '0':
            print("\n👋 Au revoir!")
            break
        elif choice == '1':
            explore_raw_data()
        elif choice == '2':
            explore_insights()
        elif choice == '3':
            show_post_details('freelance')
        elif choice == '4':
            show_post_details('hn')
        elif choice == '5':
            show_post_details('rss')
        elif choice == '6':
            show_post_details('multi')
        else:
            print("❌ Choix invalide")

        input("\n⏸️  Appuyez sur Entrée pour continuer...")


if __name__ == "__main__":
    main()
