# 🚀 Quick Start - Need Scanner V2

**En 5 minutes**, découvrez les nouvelles fonctionnalités V2.

## Installation

```bash
# Installer les nouvelles dépendances
pip install youtube-search-python
```

## Test Rapide (avec vos données existantes)

Vous avez déjà collecté 780 posts Reddit. Testons la V2 directement :

```bash
# Run V2 pipeline avec novelty + trend
python -m need_scanner run \
  --input-pattern "data/raw/posts_reddit_multi_*.json" \
  --clusters 8 \
  --novelty-weight 0.20 \
  --trend-weight 0.15 \
  --output-dir data/v2_test
```

**Résultat attendu :**
- Calcul automatique des scores de **novelty** et **trend**
- Nouveau fichier `insights_enriched.csv` avec toutes les métriques
- Top 3 priorities avec scores détaillés

## Nouvelles Commandes V2

### 1. Collection avec Pack de Subreddits

```bash
# Créer un petit pack de test
cat > config/packs/my_test.txt << EOF
freelance
SaaS
Entrepreneur
EOF

# Collecter avec le pack
python -m need_scanner collect-all \
  --pack my_test \
  --reddit-limit 10 \
  --reddit-mode hot
```

### 2. Filtrage par Mots-Clés

```bash
# Voir les patterns disponibles
head -20 config/intent_patterns.txt

# Collecter uniquement les posts matchant ces keywords
python -m need_scanner collect-all \
  --pack my_test \
  --reddit-limit 10 \
  --include-keywords-file config/intent_patterns.txt
```

### 3. Déduplication Multi-Semaines

```bash
# 1ère run
python -m need_scanner collect-all \
  --pack my_test \
  --reddit-limit 10 \
  --history-days 30

# 2ème run (trouvera des duplicats)
python -m need_scanner collect-all \
  --pack my_test \
  --reddit-limit 10 \
  --history-days 30
```

### 4. Priority Scoring Personnalisé

```bash
# Maximiser la nouveauté
python -m need_scanner run \
  --novelty-weight 0.30 \
  --trend-weight 0.10 \
  --pain-weight 0.25

# Maximiser le trend
python -m need_scanner run \
  --novelty-weight 0.10 \
  --trend-weight 0.30 \
  --pain-weight 0.25
```

## Workflow Complet V2

```bash
# 1. Collect (pack + keywords + dedup)
python -m need_scanner collect-all \
  --pack smallbiz_fr \
  --reddit-limit 50 \
  --reddit-mode hot \
  --include-keywords-file config/intent_patterns.txt \
  --history-days 45 \
  --filter-lang en,fr \
  --filter-intent

# 2. Prefilter
python -m need_scanner prefilter \
  --keep-intents pain,request \
  --detect-wtp

# 3. Run avec V2
python -m need_scanner run \
  --novelty-weight 0.15 \
  --trend-weight 0.15 \
  --history-path data/history \
  --output-dir data/output

# 4. Explorer les résultats
open data/output/insights_enriched.csv
```

## Vérifier que ça Marche

```bash
# Le CSV enrichi doit avoir ces colonnes:
head -1 data/output/insights_enriched.csv
```

Vous devez voir : `novelty_score`, `trend_score`, `keywords_matched`

## Bonus : Trend Booster

Job quotidien pour capturer les trending topics :

```bash
python -m need_scanner.jobs.booster
```

Crée `data/incoming/booster_TIMESTAMP.json` avec les hot topics du jour.

## Ressources

- **Guide de test complet** : `docs/TESTING_V2.md`
- **Nouvelles fonctionnalités** : `docs/WHATS_NEW_V2.md`
- **Statut d'implémentation** : `docs/V2_IMPLEMENTATION_STATUS.md`

---

**Questions ?** Consultez `docs/TESTING_V2.md` pour des tests détaillés.
