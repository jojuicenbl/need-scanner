# 🔄 Guide de Migration v1.0 → v2.0

Ce guide explique comment migrer d'un workflow Need Scanner v1.0 vers v2.0 avec toutes les nouvelles fonctionnalités.

## 📋 Résumé des Changements

### Nouveautés v2.0
- ✅ Configuration multi-modèle (light/heavy)
- ✅ Tags sectoriels automatiques
- ✅ MMR reranking (diversité)
- ✅ Mémoire inter-jour (historique)
- ✅ Scoring plus discriminant
- ✅ Sources multi-secteur équilibrées

### Compatibilité
- ✅ **100% backward compatible** : Aucun code v1.0 ne casse
- ✅ Toutes les commandes CLI existantes fonctionnent
- ✅ Les anciens exports restent valides
- ✅ Pas de changement obligatoire

---

## 🚀 Migration Étape par Étape

### Étape 1 : Installation des Nouvelles Dépendances

```bash
# Activer environnement virtuel
source env/bin/activate  # ou env\Scripts\activate sur Windows

# Installer PyYAML (seule nouvelle dépendance)
pip install pyyaml>=6.0.0

# OU réinstaller tout
pip install -r requirements.txt
```

**Vérification** :
```bash
python test_improvements.py
# Doit afficher : ✅ ALL TESTS PASSED
```

---

### Étape 2 : Mise à Jour Configuration

#### 2.1. Fichier `.env`

Ajouter ces variables à votre `.env` existant :

```bash
# === NOUVELLES VARIABLES v2.0 ===

# Modèles OpenAI
NS_LIGHT_MODEL=gpt-4o-mini          # Modèle léger (classification, tags)
NS_HEAVY_MODEL=gpt-4o               # Modèle puissant (TOP K clusters)
NS_TOP_K_ENRICHMENT=5               # Nombre de TOP clusters avec gpt-4o

# Historique & Déduplication
NS_HISTORY_RETENTION_DAYS=30        # Jours de rétention historique
NS_HISTORY_PENALTY_FACTOR=0.3       # Force de pénalité (0-1)

# MMR Reranking
NS_MMR_LAMBDA=0.7                   # Balance relevance/diversité (0-1)
NS_MMR_TOP_K=10                     # Nombre final de clusters sélectionnés
```

**Ou copier depuis le template** :
```bash
# Sauvegarder votre .env actuel
cp .env .env.backup

# Copier le nouveau template
cp .env.example .env

# Restaurer votre OPENAI_API_KEY
# (copier manuellement depuis .env.backup)
```

#### 2.2. Configuration Sources (Optionnel)

Le fichier `config/sources_config.yaml` est **pré-configuré** et prêt à l'emploi.

**Si vous voulez le personnaliser** :
```bash
nano config/sources_config.yaml
```

Sinon, rien à faire !

---

### Étape 3 : Choix du Mode d'Utilisation

Vous avez **3 options** pour utiliser les améliorations v2.0 :

#### Option A : Mode Hybride (Recommandé)

Garder votre workflow actuel + utiliser le pipeline v2.0 pour les analyses importantes.

**Workflow v1.0 existant** (toujours fonctionnel) :
```bash
# Collecte
python -m need_scanner collect-reddit-multi --limit-per-sub 30

# Analyse standard
python -m need_scanner run --input "data/raw/posts_*.json" --clusters 10
```

**Pipeline v2.0** (analyses premium) :
```python
# Script Python personnalisé (voir Étape 4)
python scripts/run_v2_pipeline.py
```

#### Option B : Migration Complète vers v2.0

Remplacer complètement votre workflow par le pipeline v2.0.

**Avantages** :
- Toutes les fonctionnalités v2.0
- Meilleure qualité sur TOP K
- Diversité sectorielle garantie

**Inconvénients** :
- Nécessite code Python (pas de CLI simple)
- Coût légèrement plus élevé (gpt-4o sur TOP K)

#### Option C : Rester en v1.0

Continuer avec le workflow actuel sans changement.

**Quand choisir cette option** :
- Votre workflow actuel vous convient
- Budget limité (v1.0 = moins cher)
- Pas besoin de diversité sectorielle

**Note** : Vous pouvez migrer plus tard sans problème.

---

### Étape 4 : Créer un Script v2.0 (Options A ou B)

Créer un fichier `scripts/run_v2_pipeline.py` :

```python
"""
Script personnalisé pour exécuter le pipeline Need Scanner v2.0.
Adapté à votre workflow existant.
"""

import glob
import json
import numpy as np
from pathlib import Path

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
    embeddings, embed_cost = embed_posts(
        posts=all_posts,
        api_key=config.openai_api_key,
        model=config.ns_embed_model
    )
    print(f"✓ Generated embeddings. Cost: ${embed_cost:.4f}")

    # 4. Clustering
    print("\n[3/5] Clustering...")
    n_clusters = min(config.ns_num_clusters, len(all_posts))
    labels, kmeans = cluster(embeddings, n_clusters=n_clusters)

    metadata = [p.dict() for p in all_posts]
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
```

**Rendre le script exécutable** :
```bash
chmod +x scripts/run_v2_pipeline.py
```

**Exécuter** :
```bash
python scripts/run_v2_pipeline.py
```

---

### Étape 5 : Comparer v1.0 vs v2.0

Pour évaluer les améliorations, lancez les deux pipelines en parallèle :

```bash
# Pipeline v1.0
python -m need_scanner run --input "data/raw/posts_*.json" --output-dir data/results_v1

# Pipeline v2.0
python scripts/run_v2_pipeline.py  # Output: data/results_v2
```

**Comparer** :
1. **Diversité** : v2.0 devrait montrer plus de secteurs différents
2. **Qualité TOP 5** : v2.0 utilise gpt-4o pour meilleure analyse
3. **Répétitions** : v2.0 pénalise les clusters similaires à l'historique
4. **Scores** : v2.0 a des scores plus étalés (3-9 vs 7-8)

---

## 📊 Ajustements Recommandés

### Optimiser les Coûts

Si le coût v2.0 est trop élevé :

```bash
# .env
NS_TOP_K_ENRICHMENT=3  # Réduire à 3 au lieu de 5
NS_HEAVY_MODEL=gpt-4o-mini  # Utiliser uniquement le modèle léger
```

### Augmenter la Diversité

Pour favoriser encore plus la diversité :

```bash
# .env
NS_MMR_LAMBDA=0.5  # Plus de diversité (50/50 relevance/diversity)
```

### Ajuster la Mémoire Historique

Pour pénaliser plus fortement les répétitions :

```bash
# .env
NS_HISTORY_PENALTY_FACTOR=0.5  # Pénalité plus forte
NS_HISTORY_RETENTION_DAYS=60   # Garder plus longtemps
```

---

## 🔧 Intégration dans GitHub Actions

Si vous utilisez GitHub Actions pour l'exécution quotidienne :

### Mettre à jour `.github/workflows/need_scanner_daily.yml`

```yaml
name: Need Scanner Daily (v2.0)

on:
  schedule:
    - cron: '0 8 * * *'  # 8h chaque jour
  workflow_dispatch:

jobs:
  run-scanner:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run v2.0 pipeline
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          python scripts/run_v2_pipeline.py

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: results-v2
          path: data/results_v2/
```

---

## 🧪 Tester la Migration

### Checklist de Vérification

- [ ] Tests passent : `python test_improvements.py` ✅
- [ ] Configuration `.env` mise à jour
- [ ] Script v2.0 créé et testé
- [ ] Résultats v2.0 contiennent nouveaux champs (`sector`, `mmr_rank`, etc.)
- [ ] Historique créé : `data/history/clusters.jsonl` existe
- [ ] Coûts sous contrôle (vérifier les logs)

### Test Complet

```bash
# 1. Collecter données fraîches
python -m need_scanner collect-reddit-multi --limit-per-sub 20

# 2. Pipeline v1.0 (référence)
python -m need_scanner run --input "data/raw/posts_*.json" --output-dir data/results_v1

# 3. Pipeline v2.0 (nouveau)
python scripts/run_v2_pipeline.py

# 4. Comparer les résultats
ls -lh data/results_v1/
ls -lh data/results_v2/

# 5. Inspecter un insight v2.0
cat data/results_v2/enriched_results.json | jq '.[0]'
```

---

## ❓ FAQ Migration

**Q: Dois-je supprimer mes anciens résultats ?**
R: Non, v1.0 et v2.0 peuvent coexister. Gardez `data/results/` pour v1.0 et utilisez `data/results_v2/` pour v2.0.

**Q: L'historique ralentit-il le pipeline ?**
R: Non, impact négligeable (<1s). Peut même accélérer en réduisant les clusters à analyser.

**Q: Puis-je désactiver certaines fonctionnalités v2.0 ?**
R: Oui, via paramètres `use_mmr=False` et `use_history_penalty=False` dans `run_enriched_pipeline()`.

**Q: Que se passe-t-il si je ne configure pas les nouvelles variables .env ?**
R: Les valeurs par défaut seront utilisées (définies dans `config.py`). Le pipeline fonctionnera quand même.

**Q: Comment réinitialiser l'historique ?**
R: Supprimer `data/history/clusters.jsonl` ou lancer `history.cleanup_old_entries(retention_days=0)`.

**Q: Le pipeline v2.0 est-il plus lent ?**
R: Légèrement (~10-20% plus lent) à cause des étapes supplémentaires (sector classification, MMR, history). Mais la qualité est bien meilleure.

---

## 🆘 Dépannage

### Problème : Tests échouent

```bash
# Vérifier Python version
python --version  # Doit être 3.11+

# Réinstaller dépendances
pip install --upgrade -r requirements.txt

# Relancer tests
python test_improvements.py
```

### Problème : Erreur "No module named 'yaml'"

```bash
pip install pyyaml
```

### Problème : Historique corrompu

```bash
rm data/history/clusters.jsonl
# Relancer le pipeline
```

### Problème : Coûts trop élevés

```bash
# Réduire TOP K enrichment
echo "NS_TOP_K_ENRICHMENT=2" >> .env

# OU utiliser uniquement modèle léger
echo "NS_HEAVY_MODEL=gpt-4o-mini" >> .env
```

---

## 📚 Ressources

- **Documentation complète** : [docs/ENGINE_IMPROVEMENTS.md](ENGINE_IMPROVEMENTS.md)
- **Quick Start v2.0** : [QUICK_START_V2.md](../QUICK_START_V2.md)
- **Changelog** : [CHANGELOG.md](../CHANGELOG.md)
- **Tests** : `test_improvements.py`

---

## 🎉 Félicitations !

Vous avez migré vers Need Scanner v2.0 avec succès !

**Profitez des nouvelles fonctionnalités** :
- 🎯 Insights multi-secteur diversifiés
- 💎 TOP K ultra-qualitatif (gpt-4o)
- 🔄 Déduplication automatique inter-jour
- 📊 Scoring plus expressif et discriminant

**Happy market discovery! 🚀**
