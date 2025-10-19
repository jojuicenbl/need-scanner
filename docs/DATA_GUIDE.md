# 📂 Guide d'Organisation des Données - need_scanner

## 🗂️ Structure des Répertoires

```
data/
├── raw/                    # Données brutes collectées
│   ├── posts_freelance_*.json    # Posts Reddit
│   ├── posts_hn_*.json           # Posts Hacker News
│   ├── posts_rss_*.json          # Posts RSS
│   └── posts_multi_*.json        # Posts multi-sources filtrés
│
├── embeddings.npy         # Vecteurs d'embeddings (analyse ancienne)
├── meta.json              # Métadonnées des posts analysés
├── cluster_results.json   # Résultats complets avec statistiques
├── insights.csv           # Vue tableur des insights
│
└── phase1_test/           # Test de validation Phase 1
    ├── embeddings.npy
    ├── meta.json
    ├── cluster_results.json
    └── insights.csv
```

---

## 📥 Données Brutes (`data/raw/`)

### Format des fichiers

**Nom** : `posts_{source}_{timestamp}.json`
- `{source}` : `freelance` (Reddit), `hn` (Hacker News), `rss`, `multi`
- `{timestamp}` : `YYYYMMDD_HHMMSS`

### Structure d'un post

#### Reddit
```json
{
  "id": "1o5wdq1",
  "source": "reddit",
  "title": "How to avoid getting scammed via W9?",
  "selftext": "Hey all, I'm a graphic designer...",
  "created_utc": 1760389840.0,
  "permalink": "https://reddit.com/r/freelance/comments/...",
  "score": 16,
  "num_comments": 8
}
```

#### Hacker News
```json
{
  "id": "hn_45599308",
  "source": "hn",
  "title": "Ask HN: Can't get hired – what's next?",
  "body": "Hey HN, I feel like I've wasted...",
  "created_ts": 1760568807.0,
  "url": "https://news.ycombinator.com/item?id=45599308",
  "score": 43,
  "comments_count": 130
}
```

#### RSS
```json
{
  "id": "rss_1907244541",
  "source": "rss",
  "title": "Waymo is bringing autonomous...",
  "body": "<p>Article URL: ...",
  "created_ts": 1760596633.0,
  "url": "https://9to5google.com/...",
  "score": 0,
  "comments_count": 0
}
```

#### Multi-source (filtré)
```json
{
  "id": "hn_45599308",
  "source": "hn",
  "title": "Ask HN: Can't get hired – what's next?",
  "body": "...",
  "created_ts": 1760568807.0,
  "url": "https://news.ycombinator.com/item?id=45599308",
  "score": 43,
  "comments_count": 130,
  "lang": "en",           // ✨ Ajouté par filter
  "intent": "pain",       // ✨ Ajouté par filter
  "raw": {}
}
```

### Fichiers actuels

| Fichier | Taille | Posts | Source(s) | Date |
|---------|--------|-------|-----------|------|
| `posts_freelance_20251015_131017.json` | 373 KB | 50 | Reddit | 2025-10-15 13:10 |
| `posts_freelance_20251016_130220.json` | 130 KB | 20 | Reddit | 2025-10-16 13:02 |
| `posts_hn_20251016_130227.json` | 214 KB | 29 | HN | 2025-10-16 13:02 |
| `posts_rss_20251016_130312.json` | 15 KB | 22 | RSS | 2025-10-16 13:03 |
| `posts_multi_20251016_130313.json` | 33 KB | 13 | Reddit + HN (filtré) | 2025-10-16 13:03 |

---

## 📊 Résultats d'Analyse

### `cluster_results.json`

Fichier complet contenant :

```json
{
  "statistics": {
    "total_posts": 13,
    "after_cleaning": 13,
    "after_dedup": 7,        // ✨ Déduplication cross-source
    "num_clusters": 3,
    "embeddings_cost_usd": 0.0,
    "summary_cost_usd": 0.0004,
    "total_cost_usd": 0.0004
  },
  "insights": [
    {
      "cluster_id": 0,
      "summary": {
        "title": "Difficulté d'analyse des données",
        "description": "Les utilisateurs rencontrent...",
        "monetizable": true,
        "justification": "Le besoin de solutions...",
        "mvp": "Développer un outil simple...",
        "pain_score_llm": 8,
        "size": 4
      },
      "pain_score_final": 7,
      "examples": [
        {
          "id": "hn_45583667",
          "url": "https://news.ycombinator.com/item?id=45583667",
          "score": 36,
          "num_comments": 7,
          "title": "Show HN: An open source access logs..."
        }
      ]
    }
  ]
}
```

### `insights.csv`

Vue tableur pour analyse rapide (Excel, Google Sheets) :

| cluster_id | size | title | description | monetizable | pain_score_llm | pain_score_final | mvp |
|------------|------|-------|-------------|-------------|----------------|------------------|-----|
| 0 | 4 | Difficulté d'analyse des données | Les utilisateurs rencontrent... | True | 8 | 7 | Développer un outil simple... |
| 2 | 2 | Difficultés d'embauche dans la tech | Les professionnels de la tech... | True | 8 | 7 | Lancer un webinaire gratuit... |
| 1 | 1 | Perte de contrat freelance | La perte soudaine d'un contrat... | True | 8 | 6 | Développer une plateforme... |

### `embeddings.npy`

Vecteurs d'embeddings OpenAI (format NumPy binaire)
- Dimensions : (nombre_posts, 1536)
- Utilisé pour le clustering KMeans

### `meta.json`

Métadonnées complètes des posts analysés :

```json
[
  {
    "id": "hn_45599308",
    "title": "Ask HN: Can't get hired – what's next?",
    "url": "https://news.ycombinator.com/item?id=45599308",
    "score": 43,
    "num_comments": 130
  }
]
```

---

## 🔄 Flux de Données

### 1. Collection

```bash
# Reddit seul
python -m need_scanner collect --subreddit freelance --limit 50
→ data/raw/posts_freelance_{timestamp}.json

# Hacker News seul
python -m need_scanner collect-hn --days 7 --min-points 20
→ data/raw/posts_hn_{timestamp}.json

# RSS seul
python -m need_scanner collect-rss --feeds-file config/rss_feeds.txt
→ data/raw/posts_rss_{timestamp}.json

# Multi-source avec filtres
python -m need_scanner collect-all \
  --reddit-subreddit freelance \
  --rss-feeds-file config/rss_feeds.txt \
  --filter-lang en \
  --filter-intent \
  --min-score 5
→ data/raw/posts_multi_{timestamp}.json
```

### 2. Analyse

```bash
python -m need_scanner run \
  --input-pattern "data/raw/posts_multi_*.json" \
  --clusters 5 \
  --output-dir data/
```

**Pipeline** :
1. Chargement → `posts_multi_*.json`
2. Nettoyage → normalisation texte
3. Déduplication → hash + fuzzy + Jaccard (cross-source)
4. Embeddings → OpenAI API
5. Clustering → KMeans
6. Summarization → GPT-4o-mini (LLM)
7. Scoring → pain_score (LLM + heuristic)
8. Export → `cluster_results.json` + `insights.csv`

---

## 📖 Comment Consulter les Données

### Option 1 : Ligne de commande

```bash
# Compter les posts par source
jq -r '.[] | .source' data/raw/posts_multi_*.json | sort | uniq -c

# Voir les titres
jq -r '.[] | .title' data/raw/posts_hn_*.json | head -10

# Posts avec score > 50
jq '.[] | select(.score > 50)' data/raw/posts_hn_*.json
```

### Option 2 : Python

```python
import json

# Charger les posts
with open('data/raw/posts_multi_20251016_130313.json') as f:
    posts = json.load(f)

# Statistiques
print(f"Total posts: {len(posts)}")
sources = {}
for post in posts:
    src = post['source']
    sources[src] = sources.get(src, 0) + 1
print(f"Sources: {sources}")

# Filtrer
high_score = [p for p in posts if p['score'] > 30]
print(f"High score posts: {len(high_score)}")
```

### Option 3 : Excel / Google Sheets

Ouvrir directement `data/insights.csv` ou `data/phase1_test/insights.csv`

---

## 🎯 Exemples d'Insights Générés

### Cluster 0 - Difficulté d'analyse des données
- **Taille** : 4 posts
- **Pain Score** : 7/10
- **Monétisable** : ✅ Oui
- **MVP** : Outil d'analyse de logs avec blocage de bots
- **Sources** : HN (Show HN posts sur analytics)

### Cluster 2 - Difficultés d'embauche dans la tech
- **Taille** : 2 posts
- **Pain Score** : 7/10
- **Monétisable** : ✅ Oui
- **MVP** : Webinaire sur compétences tech en demande
- **Sources** : HN (Ask HN career posts)

### Cluster 1 - Perte de contrat freelance
- **Taille** : 1 post
- **Pain Score** : 6/10
- **Monétisable** : ✅ Oui
- **MVP** : Plateforme de mise en relation rapide
- **Sources** : Reddit (r/freelance)

---

## 🔍 Champs Enrichis (Phase 1)

Les fichiers `posts_multi_*.json` contiennent des champs supplémentaires :

| Champ | Type | Source | Description |
|-------|------|--------|-------------|
| `lang` | str | langdetect | Code langue ISO (en, fr, es...) |
| `intent` | str | rule-based | pain, request, howto, promo, news, other |

**Filtrage appliqué** :
- ✅ Langue : anglais uniquement
- ✅ Intent : pain + request uniquement
- ✅ Score : ≥5
- ✅ Déduplication : cross-source (6/13 doublons détectés)

---

## 💡 Prochaines Étapes (Phase 2)

**Nouveaux champs à venir** :
- `persona` : Freelance designer, SaaS founder, etc.
- `jtbd` : Job-To-Be-Done structuré
- `context` : Outils actuels, contraintes
- `alternatives` : Solutions mentionnées
- `willingness_to_pay_signal` : Signaux WTP

**Nouvelles sources** :
- X/Twitter
- Product Hunt
- Stack Exchange
- App Store Reviews

**Nouveaux exports** :
- `insights_enriched.csv` (20 colonnes)
- Notifications Slack
