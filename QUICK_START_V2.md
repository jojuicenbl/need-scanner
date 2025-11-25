# 🚀 Quick Start - Need Scanner v2.0

Guide rapide pour utiliser les nouvelles fonctionnalités du moteur amélioré.

## 📦 Installation

```bash
# 1. Activer l'environnement virtuel
source env/bin/activate  # Linux/Mac
# env\Scripts\activate  # Windows

# 2. Installer les nouvelles dépendances
pip install -r requirements.txt

# 3. Vérifier l'installation
python test_improvements.py
```

## ⚙️ Configuration

### 1. Créer/Mettre à jour `.env`

```bash
# Copier le template
cp .env.example .env

# Éditer avec vos clés API
nano .env
```

**Variables obligatoires** :
```bash
OPENAI_API_KEY=sk-...
```

**Nouvelles variables v2.0** (avec valeurs par défaut) :
```bash
# Modèles
NS_LIGHT_MODEL=gpt-4o-mini          # Modèle léger pour tâches simples
NS_HEAVY_MODEL=gpt-4o               # Modèle puissant pour TOP K
NS_TOP_K_ENRICHMENT=5               # Nombre de clusters TOP enrichis avec gpt-4o

# Historique
NS_HISTORY_RETENTION_DAYS=30        # Jours de rétention historique
NS_HISTORY_PENALTY_FACTOR=0.3       # Force de pénalité (0-1)

# MMR Reranking
NS_MMR_LAMBDA=0.7                   # Balance relevance/diversité (0-1)
NS_MMR_TOP_K=10                     # Nombre final de clusters sélectionnés
```

### 2. (Optionnel) Configuration des Sources Multi-Secteur

Le fichier `config/sources_config.yaml` est déjà pré-configuré avec :
- 27 subreddits Reddit répartis sur 10 secteurs
- 14 sites StackExchange répartis sur 7 secteurs
- Quotas par catégorie pour équilibrage

**Pour personnaliser** :
```bash
nano config/sources_config.yaml
```

## 🎯 Utilisation Basique

### Workflow Complet (CLI existant)

Les commandes existantes fonctionnent toujours :

```bash
# 1. Collecter les données
python -m need_scanner collect-reddit-multi --limit-per-sub 30

# 2. Prévisualiser
python -m need_scanner prefilter --filter-lang en --show-sample 10

# 3. Analyser
python -m need_scanner run --input "data/raw/posts_*.json" --clusters 10
```

### Nouveau : Pipeline Enrichi v2.0

Pour utiliser toutes les améliorations (multi-modèle, secteurs, MMR, historique) :

```python
from pathlib import Path
import glob
import json
import numpy as np

from src.need_scanner.config import get_config
from src.need_scanner.schemas import Post
from src.need_scanner.processing.embed import embed_posts
from src.need_scanner.processing.cluster import cluster, get_cluster_data
from src.need_scanner.jobs.enriched_pipeline import run_enriched_pipeline

# 1. Charger les posts
posts_files = glob.glob("data/raw/posts_*.json")
all_posts = []

for file_path in posts_files:
    with open(file_path, 'r', encoding='utf-8') as f:
        posts_data = json.load(f)
        all_posts.extend([Post(**p) for p in posts_data])

print(f"Loaded {len(all_posts)} posts")

# 2. Embeddings
config = get_config()
embeddings, embed_cost = embed_posts(
    posts=all_posts,
    api_key=config.openai_api_key,
    model=config.ns_embed_model
)

print(f"Generated embeddings: ${embed_cost:.4f}")

# 3. Clustering
labels, kmeans = cluster(embeddings, n_clusters=10)

# 4. Organiser par cluster
metadata = [p.dict() for p in all_posts]
cluster_data = get_cluster_data(labels, metadata, embeddings)

# 5. Pipeline enrichi v2.0
results = run_enriched_pipeline(
    cluster_data=cluster_data,
    embeddings=embeddings,
    labels=labels,
    output_dir=Path("data/results_v2"),
    use_mmr=True,
    use_history_penalty=True
)

# 6. Résultats
print(f"\n✅ Pipeline terminé!")
print(f"   Clusters analysés: {results['num_clusters']}")
print(f"   TOP insights: {results['num_top_insights']}")
print(f"   Coût total: ${results['total_cost']:.4f}")

# Afficher TOP 5
print("\n🏆 TOP 5 INSIGHTS:")
for insight in results['insights'][:5]:
    print(f"  #{insight.rank} [{insight.summary.sector}] {insight.summary.title}")
    print(f"     Priority: {insight.priority_score:.2f} → {insight.priority_score_adjusted:.2f} (ajusté)")
    print(f"     MMR rank: {insight.mmr_rank}")
```

**Fichier complet** : voir `examples/run_enriched_pipeline.py` (à créer)

## 📊 Comprendre les Résultats

### Nouveaux Champs dans les Exports

**JSON** (`data/results_v2/enriched_results.json`) :

```json
{
  "cluster_id": 3,
  "rank": 1,
  "mmr_rank": 1,
  "priority_score": 7.45,
  "priority_score_adjusted": 7.01,
  "summary": {
    "title": "Freelance payment delays",
    "sector": "business_pme",
    "persona": "Freelance consultant",
    "jtbd": "Quand j'attends un paiement client, je veux être payé rapidement, afin de maintenir ma trésorerie",
    ...
  },
  ...
}
```

**Nouveaux champs** :
- `sector` : Secteur du cluster (dev_tools, business_pme, etc.)
- `priority_score_adjusted` : Score ajusté après pénalité historique
- `mmr_rank` : Rang après reranking MMR (diversité)

### Interpréter les Scores

**priority_score vs priority_score_adjusted** :
- `priority_score` : Score brut (pain + traction + novelty + WTP)
- `priority_score_adjusted` : Score après pénalité de similarité avec l'historique
- **Différence** : Plus la différence est grande, plus le cluster est similaire à l'historique

**mmr_rank vs rank** :
- `rank` : Rang initial basé sur `priority_score_adjusted` (pertinence)
- `mmr_rank` : Rang final après MMR (pertinence + diversité)
- **Saut de rang** : Un cluster peut "monter" si unique, ou "descendre" si similaire aux déjà sélectionnés

## 🎛️ Ajuster les Paramètres

### Contrôler les Coûts

**Réduire les coûts** :
```bash
# Utiliser uniquement le modèle léger (moins cher)
NS_HEAVY_MODEL=gpt-4o-mini
NS_TOP_K_ENRICHMENT=0  # Pas d'enrichissement premium

# OU réduire le nombre de clusters TOP
NS_TOP_K_ENRICHMENT=3  # Seulement les 3 meilleurs
```

**Augmenter la qualité** :
```bash
# Enrichir plus de clusters avec gpt-4o
NS_TOP_K_ENRICHMENT=10

# Augmenter le nombre final d'insights
NS_MMR_TOP_K=15
```

### Gérer la Diversité

**Plus de pertinence, moins de diversité** :
```bash
NS_MMR_LAMBDA=0.9  # 90% relevance, 10% diversity
```

**Plus de diversité, moins de pertinence** :
```bash
NS_MMR_LAMBDA=0.5  # 50% relevance, 50% diversity
```

**Désactiver MMR** (uniquement pertinence) :
```python
results = run_enriched_pipeline(
    ...
    use_mmr=False  # Pas de reranking
)
```

### Ajuster la Mémoire Historique

**Pénaliser plus fortement les répétitions** :
```bash
NS_HISTORY_PENALTY_FACTOR=0.5  # Pénalité plus forte (0-1)
```

**Réduire la rétention** :
```bash
NS_HISTORY_RETENTION_DAYS=14  # Seulement 2 semaines
```

**Désactiver l'historique** :
```python
results = run_enriched_pipeline(
    ...
    use_history_penalty=False  # Pas de pénalité historique
)
```

**Nettoyer l'historique** :
```bash
rm data/history/clusters.jsonl
```

## 📈 Monitoring

### Logs

Le pipeline génère des logs détaillés via `loguru` :

```
[STEP 1] Computing initial heuristic scores...
[STEP 2] Enriching TOP 5 clusters with heavy model (gpt-4o)...
[STEP 3] Classifying clusters into sectors...
[STEP 4] Computing cluster embeddings...
[STEP 5] Computing priority scores...
[STEP 6] Applying history-based similarity penalty...
[STEP 7] MMR reranking (λ=0.7, top_k=10)...
[STEP 8] Saving results...
[STEP 9] Updating history...
```

### Coûts

Le pipeline affiche les coûts en temps réel :

```
Cluster 0: Estimated cost $0.0018 (1200 input + 400 output tokens)
Cluster 0: API call completed. Actual cost: $0.0016 (1150 + 380 tokens)
...
Total LLM cost: $0.0234
```

## 🧪 Tests

### Test Rapide

```bash
python test_improvements.py
```

Tests :
1. ✅ Configuration multi-modèle
2. ✅ Définition des secteurs
3. ✅ MMR reranking (mock)
4. ✅ Gestion de l'historique
5. ✅ Configuration des sources

### Test Complet (avec API)

```bash
# Test avec données réelles (coût ~$0.02)
python test_sprint1.py  # Utilise l'ancien pipeline
# Ou créer test_sprint2.py avec le nouveau pipeline
```

## 📚 Ressources

- **Documentation complète** : `docs/ENGINE_IMPROVEMENTS.md`
- **Changelog** : `CHANGELOG.md`
- **Configuration** : `.env.example`, `config/sources_config.yaml`
- **Code** :
  - Secteurs : `src/need_scanner/analysis/sector.py`
  - MMR : `src/need_scanner/processing/mmr.py`
  - Historique : `src/need_scanner/processing/history.py`
  - Pipeline : `src/need_scanner/jobs/enriched_pipeline.py`

## ❓ FAQ

**Q: Le pipeline v2.0 remplace-t-il l'ancien ?**
R: Non, l'ancien pipeline (`python -m need_scanner run`) fonctionne toujours. Le v2.0 est une option avancée avec plus de fonctionnalités.

**Q: Combien coûte une analyse complète ?**
R: Avec config par défaut (10 clusters, TOP 5 avec gpt-4o) : ~$0.02-0.05

**Q: L'historique persiste entre les runs ?**
R: Oui, `data/history/clusters.jsonl` est mis à jour automatiquement à chaque run.

**Q: Puis-je utiliser seulement certaines fonctionnalités ?**
R: Oui, MMR et historique sont désactivables via paramètres `use_mmr` et `use_history_penalty`.

**Q: Comment réinitialiser l'historique ?**
R: Supprimer `data/history/clusters.jsonl` ou utiliser `history.cleanup_old_entries(retention_days=0)`.

## 🆘 Support

Problème ? Vérifier :
1. Logs dans la console (loguru activé)
2. Configuration `.env` (toutes les variables présentes ?)
3. Historique `data/history/clusters.jsonl` (corrompu ?)
4. Tests `python test_improvements.py`

Ouvrir une issue sur GitHub avec :
- Logs complets
- Configuration (sans API key)
- Commande exécutée
- Version Python (`python --version`)

---

**Happy market discovery! 🚀**
