#!/usr/bin/env python
"""Afficher les insights générés de manière détaillée."""

import json

print('=' * 70)
print('  📊 RÉSULTATS D\'ANALYSE - INSIGHTS GÉNÉRÉS')
print('=' * 70)

# Load cluster results
with open('data/phase1_test/cluster_results.json') as f:
    results = json.load(f)

# Statistics
stats = results['statistics']
print('\n📈 STATISTIQUES DU PIPELINE:')
print(f'   Posts collectés: {stats["total_posts"]}')
print(f'   Après nettoyage: {stats["after_cleaning"]}')
print(f'   Après déduplication: {stats["after_dedup"]} ({stats["total_posts"] - stats["after_dedup"]} doublons)')
print(f'   Clusters créés: {stats["num_clusters"]}')
print(f'   Coût embeddings: ${stats["embeddings_cost_usd"]:.4f}')
print(f'   Coût summaries: ${stats["summary_cost_usd"]:.4f}')
print(f'   Coût TOTAL: ${stats["total_cost_usd"]:.4f}')

# Insights
insights = results['insights']
print(f'\n🔍 INSIGHTS DÉTECTÉS: {len(insights)}')
print('=' * 70)

for i, insight in enumerate(insights, 1):
    summary = insight['summary']
    examples = insight['examples']

    print(f'\n📌 INSIGHT #{i} - {summary["title"]}')
    print('─' * 70)
    print(f'   🆔 Cluster ID: {insight["cluster_id"]}')
    print(f'   📊 Taille: {summary["size"]} posts')
    print(f'   💰 Monétisable: {"✅ OUI" if summary["monetizable"] else "❌ NON"}')
    print(f'   😣 Pain Score LLM: {summary["pain_score_llm"]}/10')
    print(f'   🎯 Pain Score Final: {insight["pain_score_final"]}/10')

    print(f'\n   📝 PROBLÈME:')
    desc = summary['description']
    for line in [desc[i:i+65] for i in range(0, len(desc), 65)]:
        print(f'      {line}')

    print(f'\n   💡 MVP PROPOSÉ:')
    mvp = summary['mvp']
    for line in [mvp[i:i+65] for i in range(0, len(mvp), 65)]:
        print(f'      {line}')

    print(f'\n   🎓 JUSTIFICATION:')
    just = summary['justification']
    for line in [just[i:i+65] for i in range(0, len(just), 65)]:
        print(f'      {line}')

    print(f'\n   🔗 EXEMPLES ({len(examples)} posts):')
    for j, ex in enumerate(examples[:3], 1):
        title = ex['title'][:55]
        url = ex.get('url', 'N/A')
        score = ex.get('score', 0)
        comments = ex.get('num_comments', 0)
        print(f'      {j}. {title}...')
        print(f'         Score: {score} | Comments: {comments}')
        if url != 'N/A':
            print(f'         {url}')

print('\n' + '=' * 70)
print('  ✅ EXPLORATION TERMINÉE')
print('=' * 70)
