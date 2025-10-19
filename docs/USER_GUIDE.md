# 📖 Guide d'Utilisation Détaillé - Need Scanner

## Table des Matières

1. [Premiers Pas](#premiers-pas)
2. [Collection de Données](#collection-de-données)
3. [Analyse et Pipeline](#analyse-et-pipeline)
4. [Interprétation des Résultats](#interprétation-des-résultats)
5. [Configuration Avancée](#configuration-avancée)
6. [Cas d'Usage](#cas-dusage)
7. [Troubleshooting](#troubleshooting)

---

## Premiers Pas

### Installation

```bash
# 1. Cloner et installer
git clone <repo-url>
cd need_scanner
python -m venv env
source env/bin/activate
pip install -r requirements.txt

# 2. Configuration
cp .env.example .env
# Éditer .env et ajouter OPENAI_API_KEY=sk-...
```

### Vérification

```bash
# Tester les commandes disponibles
python -m need_scanner --help

# Lister toutes les commandes
python -m need_scanner collect-reddit-multi --help
```

---

## Collection de Données

### Reddit Multi-Subreddits (Recommandé)

**Collection rapide** :
```bash
python -m need_scanner collect-reddit-multi --limit-per-sub 30
```

**Options** :
- `--config-file` : Fichier de config des subreddits (défaut: `config/reddit_subs.txt`)
- `--limit-per-sub` : Posts par subreddit (défaut: 30)
- `--sleep-between` : Délai entre subreddits en secondes (défaut: 2.0)
- `--output` : Répertoire de sortie (défaut: `data/raw`)

**Personnaliser les subreddits** :

Éditer `config/reddit_subs.txt` :
```
# Votre secteur
YourNiche
YourIndustry

# Business général
freelance
Entrepreneur
```

### Hacker News

```bash
# Derniers 30 jours, min 20 points
python -m need_scanner collect-hn --days 30 --min-points 20 --limit 100
```

**Requêtes personnalisées** :
```bash
python -m need_scanner collect-hn --queries "Ask HN,Show HN,Tell HN"
```

### Stack Exchange

```bash
# Sites workplace + freelancing
python -m need_scanner collect-stackexchange \
  --sites workplace,freelancing \
  --days 7 \
  --min-score 10 \
  --limit 50
```

**Sites disponibles** :
- `stackoverflow` - Programmation générale
- `workplace` - Questions professionnelles
- `freelancing` - Questions freelance
- `startups` - Questions startup
- `softwareengineering` - Architecture logicielle
- Voir `config/stackexchange_sites.txt` pour la liste complète

### RSS Feeds

```bash
python -m need_scanner collect-rss \
  --feeds-file config/rss_feeds.txt \
  --days 30
```

Éditer `config/rss_feeds.txt` :
```
https://example.com/feed.xml
https://another-blog.com/rss
```

### Product Hunt

**Prérequis** : Token API

1. Obtenir token : https://www.producthunt.com/v2/oauth/applications
2. Ajouter à `.env` : `PRODUCTHUNT_API_TOKEN=your_token`
3. Collecter :

```bash
python -m need_scanner collect-producthunt \
  --days 7 \
  --limit 100 \
  --categories "developer-tools,saas,productivity"
```

### Collection Multi-Sources

```bash
python -m need_scanner collect-all \
  --reddit-subreddit freelance \
  --reddit-limit 200 \
  --hn-days 30 \
  --rss-feeds-file config/rss_feeds.txt \
  --filter-lang en \
  --filter-intent \
  --min-score 5
```

**Filtres disponibles** :
- `--filter-lang` : Langues à garder (ex: `en,fr`)
- `--filter-intent` : Garder seulement pain/request
- `--min-score` : Score minimum
- `--min-comments` : Commentaires minimum

---

## Analyse et Pipeline

### 1. Prévisualisation (Recommandé)

Avant de lancer le pipeline complet, prévisualisez vos données :

```bash
python -m need_scanner prefilter \
  --input-pattern "data/raw/posts_*.json" \
  --filter-lang en \
  --detect-wtp \
  --show-sample 10
```

**Sortie** :
- Distribution des sources
- Distribution des langues (23+ détectées)
- Distribution des intents (pain, request, howto, etc.)
- Signaux WTP détectés
- Échantillon de posts

**Interprétation** :
- Si < 10 posts après filtres → Ajuster les filtres ou collecter plus
- Vérifier que les intents "pain/request/howto" sont suffisants
- Noter le % de posts avec WTP signals

### 2. Pipeline Complet

```bash
python -m need_scanner run \
  --input "data/raw/posts_*.json" \
  --clusters 5 \
  --output-dir data/results
```

**Options** :
- `--input` : Pattern de fichiers d'entrée
- `--clusters` : Nombre de clusters (défaut: 5, automatique si non spécifié)
- `--model-sum` : Modèle LLM (défaut: gpt-4o-mini)
- `--max-examples` : Exemples par cluster pour LLM (défaut: 5)
- `--output-dir` : Répertoire de sortie

**Étapes du Pipeline** :
1. Chargement des posts
2. Nettoyage et normalisation
3. Déduplication (4 stratégies)
4. Génération d'embeddings
5. Clustering (KMeans)
6. Summarization enrichie (LLM)
7. Priority scoring
8. Export (JSON + possibilité CSV)

### 3. Estimation des Coûts

Avant de lancer le pipeline complet :

```bash
python -m need_scanner estimate \
  --input "data/raw/posts_*.json" \
  --clusters 5
```

**Sortie** :
```
Estimated costs:
  Embeddings (764 tokens): $0.00001
  Summaries (5 clusters): $0.0010
  Total: $0.0011
```

---

## Interprétation des Résultats

### Structure des Fichiers de Sortie

```
data/results/
├── cluster_results.json    # Résultats complets
├── embeddings.npy          # Vecteurs d'embeddings
└── meta.json              # Métadonnées des posts
```

### Format JSON

```json
{
  "statistics": {
    "total_posts": 200,
    "after_dedup": 43,
    "num_clusters": 5,
    "total_cost_usd": 0.0012
  },
  "insights": [
    {
      "cluster_id": 0,
      "rank": 1,
      "priority_score": 5.68,
      "summary": {
        "title": "Mauvaise préparation projet",
        "problem": "Description du problème...",
        "persona": "Entrepreneur en technologie",
        "jtbd": "Quand..., je veux..., afin de...",
        "context": "Contexte d'usage...",
        "monetizable": true,
        "mvp": "Proposition de MVP...",
        "alternatives": ["tool1", "tool2"],
        "willingness_to_pay_signal": "Signal détecté...",
        "pain_score_llm": 9
      },
      "pain_score_final": 8,
      "heuristic_score": 7.5,
      "traction_score": 5.0,
      "novelty_score": 10.0,
      "source_mix": ["reddit", "hn"],
      "examples": [...]
    }
  ]
}
```

### Scores Expliqués

**Priority Score (0-10)** :
- Formule : `30% Pain + 25% Traction + 20% Novelty + 15% WTP + 10% Recency`
- >7 = Très haute priorité
- 5-7 = Haute priorité
- 3-5 = Priorité moyenne
- <3 = Faible priorité

**Pain Score LLM (1-10)** :
- Évalué par GPT-4o-mini
- 10 = Douleur forte, urgente, récurrente
- 5 = Douleur modérée
- 1 = Douleur mineure

**Traction Score (0-10)** :
- Basé sur engagement (votes, commentaires)
- Indicateur de validation du problème

**Novelty Score (0-10)** :
- Basé sur nombre d'alternatives
- 10 = Aucune alternative (espace vide!)
- 0 = Marché saturé

**WTP Score (0-10)** :
- Signaux de volonté de payer détectés
- 10 = Multiples signaux forts
- 0 = Aucun signal

### Export CSV

Pour créer un CSV enrichi (20 colonnes) :

```python
# Utiliser le script fourni ou créer le vôtre
python -c "
import json
from pathlib import Path
from need_scanner.schemas import EnrichedInsight, EnrichedClusterSummary
from need_scanner.export.writer import write_enriched_insights_csv

# Charger résultats
with open('data/results/cluster_results.json') as f:
    data = json.load(f)

# Convertir et exporter
# (voir test_sprint1.py pour exemple complet)
"
```

**Colonnes CSV** :
1. rank
2. cluster_id
3. size
4. priority_score
5. title
6. problem
7. persona
8. jtbd
9. context
10. monetizable
11. mvp
12. alternatives
13. willingness_to_pay_signal
14. pain_score_llm
15. pain_score_final
16. heuristic_score
17. traction_score
18. novelty_score
19. source_mix
20. example_urls

---

## Configuration Avancée

### Ajuster le Nombre de Clusters

```bash
# Automatique (recommandé pour débuter)
python -m need_scanner run --input "data/raw/*.json"

# Manuel (si vous savez combien de thèmes vous voulez)
python -m need_scanner run --input "data/raw/*.json" --clusters 8
```

**Règle générale** :
- <30 posts → 3-5 clusters
- 30-100 posts → 5-8 clusters
- 100-200 posts → 8-12 clusters
- 200+ posts → 10-15 clusters

### Personnaliser les Signaux WTP

Éditer `src/need_scanner/analysis/wtp.py` pour ajouter vos patterns :

```python
WTP_PATTERNS = {
    "direct_payment": [
        r"\b(willing to pay|would pay|ready to pay)\b",
        r"\b(votre pattern personnalisé)\b",
    ],
    # ...
}
```

### Ajuster la Formule de Priority

Éditer `src/need_scanner/analysis/priority.py` :

```python
def calculate_priority_score(...):
    # Ajuster les poids
    priority = (
        combined_pain * 0.40 +    # 40% pain (modifié)
        traction_score * 0.30 +   # 30% traction (modifié)
        novelty_score * 0.20 +
        wtp_score * 0.10
    )
```

---

## Cas d'Usage

### Cas 1 : Découverte Freelance

```bash
# 1. Collecter
python -m need_scanner collect-reddit-multi \
  --config-file config/reddit_subs_freelance.txt \
  --limit-per-sub 50

# 2. Prévisualiser
python -m need_scanner prefilter \
  --filter-lang en \
  --filter-intent \
  --detect-wtp

# 3. Analyser
python -m need_scanner run \
  --input "data/raw/posts_reddit*.json" \
  --clusters 8 \
  --output-dir data/freelance_insights
```

### Cas 2 : Veille Tech Startup

```bash
# Multi-sources
python -m need_scanner collect-all \
  --reddit-subreddit startups \
  --hn-days 7 \
  --filter-lang en

python -m need_scanner collect-stackexchange \
  --sites startups,entrepreneur

# Analyse
python -m need_scanner run \
  --input "data/raw/posts_*.json" \
  --clusters 10
```

### Cas 3 : Marché Français

```bash
# Collecter subreddits FR
python -m need_scanner collect-reddit-multi \
  --config-file config/reddit_subs_fr.txt

# Filtrer FR uniquement
python -m need_scanner prefilter \
  --filter-lang fr \
  --detect-wtp

# Analyser
python -m need_scanner run --input "data/raw/*.json"
```

---

## Troubleshooting

### Erreur : "Not enough posts after filtering"

**Cause** : Trop de posts filtrés

**Solutions** :
1. Collecter plus de posts : `--limit-per-sub 50`
2. Élargir filtres langue : `--filter-lang en,fr`
3. Inclure plus d'intents : Modifier le code pour inclure "other"

### Erreur : "OpenAI API error"

**Causes possibles** :
- API key invalide
- Quota dépassé
- Rate limit

**Solutions** :
1. Vérifier `.env` : `OPENAI_API_KEY=sk-...`
2. Vérifier solde OpenAI
3. Réduire charge : `--max-examples 3` ou `--clusters 3`

### Coûts trop élevés

**Solutions** :
1. Utiliser `estimate` avant de lancer
2. Réduire nombre de posts en entrée
3. Réduire nombre de clusters
4. Réduire `--max-examples`

### Clusters de mauvaise qualité

**Causes** :
- Trop peu de posts
- Posts trop diversifiés
- Mauvais nombre de clusters

**Solutions** :
1. Filtrer par secteur/subreddit spécifique
2. Augmenter le nombre de posts
3. Ajuster `--clusters` (essayer ±2)
4. Filtrer par intent plus strictement

### Résultats en mauvaise langue

**Solution** :
```bash
python -m need_scanner prefilter --filter-lang en
# Vérifier distribution AVANT de lancer pipeline
```

---

## Workflows Recommandés

### Workflow 1 : Exploration Rapide

```bash
# 1. Collecter petit échantillon
python -m need_scanner collect-reddit-multi --limit-per-sub 10

# 2. Prévisualiser
python -m need_scanner prefilter --detect-wtp

# 3. Analyser
python -m need_scanner run --clusters 3
```

**Durée** : ~5 minutes
**Coût** : ~$0.001

### Workflow 2 : Analyse Complète

```bash
# 1. Collecter large
python -m need_scanner collect-reddit-multi --limit-per-sub 30
python -m need_scanner collect-hn --days 30
python -m need_scanner collect-stackexchange --sites-file config/stackexchange_sites.txt

# 2. Prévisualiser et décider filtres
python -m need_scanner prefilter --filter-lang en,fr --detect-wtp

# 3. Estimer coût
python -m need_scanner estimate --clusters 10

# 4. Analyser
python -m need_scanner run --clusters 10 --output-dir data/full_analysis
```

**Durée** : ~30 minutes
**Coût** : ~$0.02-0.05

---

## Astuces et Bonnes Pratiques

### Collecte

✅ **À faire** :
- Collecter régulièrement (hebdomadaire/mensuel)
- Varier les sources pour diversité
- Utiliser `prefilter` avant analyse
- Sauvegarder les configs fonctionnelles

❌ **À éviter** :
- Collecter trop de posts d'un coup (coût)
- Ignorer la distribution des langues
- Lancer pipeline sans `estimate`

### Analyse

✅ **À faire** :
- Commencer avec peu de clusters (3-5)
- Vérifier les insights manuellement
- Comparer les priority scores
- Exporter en CSV pour partage

❌ **À éviter** :
- Trop de clusters (fragmentation)
- Ignorer les scores bas (peuvent être intéressants)
- Se fier uniquement au LLM (vérifier exemples)

### Production

✅ **À faire** :
- Versionner les configs
- Documenter vos découvertes
- Créer des scripts personnalisés
- Monitorer les coûts

---

**Besoin d'aide ?** Consultez les autres docs dans `docs/` ou ouvrez une issue.
