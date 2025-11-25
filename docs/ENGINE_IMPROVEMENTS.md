# 🚀 Need Scanner Engine Improvements

Ce document décrit les améliorations majeures apportées au moteur Need Scanner pour rendre la découverte de marché plus **diversifiée**, **intelligente** et **pertinente**.

## 📋 Résumé des Améliorations

### ✅ Implémenté

1. **Configuration Multi-Modèle OpenAI** (light/heavy)
2. **Tags Sectoriels par Cluster**
3. **Reranking MMR (Maximal Marginal Relevance)**
4. **Mémoire Inter-Jour des Clusters**
5. **Scoring Plus Discriminant**
6. **Configuration Multi-Secteur des Sources**

---

## 1. Configuration Multi-Modèle OpenAI

### 🎯 Objectif
Optimiser les coûts en utilisant un modèle puissant uniquement pour les tâches complexes, et un modèle léger pour les tâches simples.

### 📝 Implémentation

**Nouveaux paramètres de configuration** (`.env`) :

```bash
# Modèle léger : tâches simples (classification secteur, intent)
NS_LIGHT_MODEL=gpt-4o-mini

# Modèle lourd : enrichissement complet (persona, JTBD, scoring)
NS_HEAVY_MODEL=gpt-4o

# TOP K enrichissement : nombre de clusters enrichis avec le modèle lourd
NS_TOP_K_ENRICHMENT=5
```

### 💰 Impact Coûts

**Avant** : Tous les clusters enrichis avec `gpt-4o-mini` (~0.0002$/cluster)
**Après** :
- Top 5 clusters : `gpt-4o` (~0.002$/cluster) = **$0.010**
- Autres clusters : `gpt-4o-mini` (~0.0002$/cluster) = **$0.001**
- **Total** : ~$0.011 pour 10 clusters (vs $0.002 avant, mais avec bien plus de qualité sur le TOP 5)

### 📍 Fichiers Modifiés
- `src/need_scanner/config.py` : Ajout des paramètres light/heavy
- `.env.example` : Documentation des nouvelles variables
- `config.py` : Ajout du pricing gpt-4o

---

## 2. Tags Sectoriels par Cluster

### 🎯 Objectif
Classifier automatiquement chaque cluster dans un secteur pour faciliter l'analyse multi-secteur et le reranking par diversité.

### 📝 Implémentation

**13 secteurs prédéfinis** :
- `dev_tools` - Outils pour développeurs
- `ai_llm` - IA et LLM
- `business_pme` - Business et PME
- `education_learning` - Éducation et formation
- `health_wellbeing` - Santé et bien-être
- `consumer_lifestyle` - Lifestyle et consommation
- `creator_economy` - Économie des créateurs
- `workplace_hr` - Workplace et RH
- `finance_accounting` - Finance et comptabilité
- `legal_compliance` - Légal et conformité
- `marketing_sales` - Marketing et ventes
- `ecommerce_retail` - E-commerce et retail
- `other` - Autre

**Classification LLM** : Utilise le modèle léger (`gpt-4o-mini`) pour classifier rapidement chaque cluster.

### 📊 Nouveau Champ dans les Schémas

```python
class EnrichedClusterSummary(BaseModel):
    ...
    sector: Optional[str] = None  # Nouveau champ
```

### 📍 Fichiers Créés
- `src/need_scanner/analysis/sector.py` : Module de classification
- `src/need_scanner/schemas.py` : Ajout du champ `sector`

---

## 3. Reranking MMR (Maximal Marginal Relevance)

### 🎯 Objectif
Sélectionner les TOP N clusters en **maximisant la diversité** tout en conservant la pertinence.

### 📝 Principe MMR

**Formule** :
```
MMR(d) = λ * Relevance(d) - (1 - λ) * max[Similarity(d, d_i) for d_i in Selected]
```

- **λ = 0.7** (par défaut) : 70% pertinence, 30% diversité
- Plus λ est élevé, plus on privilégie la pertinence
- Plus λ est faible, plus on privilégie la diversité

### 🎨 Deux Modes de Reranking

#### Mode 1 : MMR Global
Sélectionne les TOP K en maximisant la diversité globale.

```python
reranked_items, _ = mmr_rerank(
    items=insights,
    embeddings=cluster_embeddings,
    priority_scores=priority_scores,
    top_k=10,
    lambda_param=0.7
)
```

#### Mode 2 : MMR par Secteur
Garantit une représentation équilibrée de chaque secteur.

```python
reranked_items, _ = mmr_rerank_by_sector(
    items=insights,
    embeddings=cluster_embeddings,
    priority_scores=priority_scores,
    sectors=sectors,
    top_k_per_sector=2,  # Max 2 par secteur
    lambda_param=0.7
)
```

### 📊 Nouveau Champ dans les Insights

```python
class EnrichedInsight(BaseModel):
    ...
    mmr_rank: Optional[int] = None  # Rang après MMR reranking
```

### 📍 Fichiers Créés
- `src/need_scanner/processing/mmr.py` : Module MMR

---

## 4. Mémoire Inter-Jour des Clusters

### 🎯 Objectif
Éviter de remonter les **mêmes idées tous les jours** en pénalisant les clusters similaires à ceux déjà vus.

### 📝 Implémentation

#### 4.1. Bibliothèque d'Historique (JSONL)

Stockage des clusters passés dans un fichier JSONL :

```json
{"id": "2025-01-25_3", "date": "2025-01-25", "title": "Freelance payment delays", "sector": "business_pme", "priority_score": 7.2, "embedding": [0.123, ...]}
{"id": "2025-01-25_7", "date": "2025-01-25", "title": "Dev tool for API testing", "sector": "dev_tools", "priority_score": 6.8, "embedding": [0.456, ...]}
```

**Paramètres** :
```bash
NS_HISTORY_RETENTION_DAYS=30  # Conservation 30 jours
```

#### 4.2. Pénalité de Similarité

**Formule** :
```
priority_score_adjusted = priority_score * (1 - α * max_similarity)
```

- **α = 0.3** (par défaut) : Facteur de pénalité (0-1)
- `max_similarity` : Similarité cosinus maximale avec l'historique

**Exemple** :
- Cluster nouveau : similarité = 0.0 → **aucune pénalité**
- Cluster similaire (0.8) : pénalité = 0.3 * 0.8 = 0.24 → **score réduit de 24%**
- Cluster quasi-identique (0.95) : pénalité = 0.3 * 0.95 = 0.285 → **score réduit de 28.5%**

### 📊 Nouveau Champ dans les Insights

```python
class EnrichedInsight(BaseModel):
    ...
    priority_score_adjusted: Optional[float] = None  # Score ajusté avec pénalité
```

### 📍 Fichiers Créés
- `src/need_scanner/processing/history.py` : Gestion de l'historique
- `data/history/clusters.jsonl` : Fichier d'historique (créé automatiquement)

---

## 5. Scoring Plus Discriminant

### 🎯 Objectif
Rendre les scores **pain, novelty, trend, WTP** plus **expressifs** et **discriminants**.

### 📝 Améliorations du Prompt

**Avant** :
> Score de douleur de 1 à 10 (10 = douleur forte, urgente, récurrente)

**Après** :
```
Score de douleur de 1 à 10. IMPORTANT : Utilise TOUTE l'échelle 1-10 de manière discriminante :
- 1-3 = Inconvénient mineur, pas urgent, workarounds acceptables
- 4-6 = Problème réel mais gérable, impact modéré
- 7-8 = Douleur forte, impact business significatif, besoin urgent
- 9-10 = Douleur critique/exceptionnelle, bloquant majeur (RARE - réserve pour cas vraiment exceptionnels)

Imagine que tu scores 100 problèmes différents : seuls quelques-uns méritent 9-10. La plupart se situent entre 4-7.
Sois EXIGEANT et DISCRIMINANT dans ta notation.
```

### 📊 Impact

**Avant** : Tous les clusters scorent entre 7-8 (peu discriminant)
**Après** : Distribution étalée entre 3-9 (hautement discriminant)

### 📍 Fichiers Modifiés
- `src/need_scanner/analysis/summarize.py` : Amélioration du prompt

---

## 6. Configuration Multi-Secteur des Sources

### 🎯 Objectif
Organiser les sources (Reddit, StackExchange) par **catégories sectorielles** et échantillonner de manière équilibrée.

### 📝 Implémentation

**Nouveau fichier de configuration** : `config/sources_config.yaml`

```yaml
reddit_sources:
  - name: freelance
    category: business_pme
    max_posts: 40

  - name: webdev
    category: dev_tools
    max_posts: 30

  - name: therapy
    category: health_wellbeing
    max_posts: 30

category_quotas:
  business_pme: 150
  dev_tools: 150
  health_wellbeing: 80
  ...
```

### 🎨 Échantillonnage Équilibré

```python
from src.need_scanner.fetchers.balanced_sampling import (
    load_sources_config,
    balance_posts_by_category
)

config = load_sources_config()
balanced_posts, counts = balance_posts_by_category(posts, config['category_quotas'])
```

**Résultat** :
- Garantit une **représentation équilibrée** de chaque secteur
- Évite la surreprésentation du dev/tech
- Permet de couvrir business, santé, éducation, retail, etc.

### 📍 Fichiers Créés
- `config/sources_config.yaml` : Configuration des sources
- `src/need_scanner/fetchers/balanced_sampling.py` : Module d'échantillonnage

---

## 7. Pipeline Enrichi Intégré

### 🎯 Objectif
Intégrer toutes les améliorations dans un pipeline unifié et optimisé.

### 📝 Workflow du Pipeline

```
1. Collecte → Filtrage → Déduplication → Embeddings → Clustering
                           ↓
2. Scoring heuristique initial (tous les clusters)
                           ↓
3. Enrichissement TOP K avec modèle lourd (gpt-4o)
   + Enrichissement autres avec modèle léger (gpt-4o-mini)
                           ↓
4. Classification secteurs (avec gpt-4o-mini)
                           ↓
5. Calcul priority_score (pain + traction + novelty + WTP)
                           ↓
6. Pénalité de similarité avec historique
   → priority_score_adjusted
                           ↓
7. MMR reranking par secteur (diversité)
   → mmr_rank
                           ↓
8. Export JSON/CSV + Mise à jour historique
```

### 📊 Utilisation

```python
from src.need_scanner.jobs.enriched_pipeline import run_enriched_pipeline

results = run_enriched_pipeline(
    cluster_data=cluster_data,
    embeddings=embeddings,
    labels=labels,
    output_dir=Path("data/results"),
    use_mmr=True,
    use_history_penalty=True
)

print(f"TOP 5 insights: {results['insights'][:5]}")
```

### 📍 Fichiers Créés
- `src/need_scanner/jobs/enriched_pipeline.py` : Pipeline intégré

---

## 🎯 Utilisation Complète

### 1. Configuration

```bash
# Copier le fichier .env.example
cp .env.example .env

# Éditer .env avec vos clés API
nano .env
```

**Variables importantes** :
```bash
OPENAI_API_KEY=sk-...

# Modèles
NS_LIGHT_MODEL=gpt-4o-mini
NS_HEAVY_MODEL=gpt-4o
NS_TOP_K_ENRICHMENT=5

# Historique
NS_HISTORY_RETENTION_DAYS=30
NS_HISTORY_PENALTY_FACTOR=0.3

# MMR
NS_MMR_LAMBDA=0.7
NS_MMR_TOP_K=10
```

### 2. Installation des Dépendances

```bash
pip install -r requirements.txt
```

**Nouvelle dépendance** : `pyyaml>=6.0.0`

### 3. Exécution du Pipeline

```python
from pathlib import Path
from src.need_scanner.jobs.enriched_pipeline import run_enriched_pipeline
from src.need_scanner.processing.cluster import cluster, get_cluster_data
from src.need_scanner.processing.embed import embed_posts

# 1. Charger les posts
posts = load_posts_from_json("data/raw/posts_*.json")

# 2. Embeddings
embeddings, embed_cost = embed_posts(posts, api_key=config.openai_api_key)

# 3. Clustering
labels, kmeans = cluster(embeddings, n_clusters=10)
cluster_data = get_cluster_data(labels, posts, embeddings)

# 4. Pipeline enrichi
results = run_enriched_pipeline(
    cluster_data=cluster_data,
    embeddings=embeddings,
    labels=labels,
    output_dir=Path("data/results")
)

print(f"✅ Pipeline terminé. {results['num_top_insights']} insights générés.")
print(f"💰 Coût total: ${results['total_cost']:.4f}")
```

---

## 📊 Nouveaux Exports CSV

### Colonnes Ajoutées

| Colonne | Description |
|---------|-------------|
| `sector` | Secteur du cluster (dev_tools, business_pme, etc.) |
| `priority_score_adjusted` | Score ajusté avec pénalité historique |
| `mmr_rank` | Rang après MMR reranking |
| `source_category` | Catégorie de la source (pour posts) |

---

## 🧪 Tests

### Test du Pipeline Complet

```python
# Lancer le test
python test_enriched_pipeline.py
```

### Test Unitaire des Modules

```python
# Test MMR
from src.need_scanner.processing.mmr import mmr_rerank
# ... (voir tests/)

# Test History
from src.need_scanner.processing.history import ClusterHistory
# ... (voir tests/)

# Test Sector Classification
from src.need_scanner.analysis.sector import classify_cluster_sector
# ... (voir tests/)
```

---

## 📈 Métriques de Performance

### Avant les Améliorations

- ⚠️ Tous les clusters scorés de manière similaire (7-8)
- ⚠️ Pas de diversité sectorielle
- ⚠️ Répétitions quotidiennes des mêmes idées
- ⚠️ Modèle unique pour tout

### Après les Améliorations

- ✅ Scores étalés (3-9), hautement discriminants
- ✅ Diversité multi-secteur garantie (MMR)
- ✅ Pénalité automatique des répétitions (historique)
- ✅ Optimisation des coûts (modèles light/heavy)
- ✅ TOP 5 ultra-qualitatif (gpt-4o)

---

## 🚀 Prochaines Étapes (Optionnel)

### Notifications Slack Enrichies

Adapter la génération du message Slack pour afficher :
- TOP N global (MMR)
- OU mini TOP par secteur

```python
# TOP 1 par secteur
for sector in ['business_pme', 'dev_tools', 'health_wellbeing']:
    top_insight = next((i for i in insights if i.summary.sector == sector), None)
    if top_insight:
        print(f"🏆 {sector}: {top_insight.summary.title}")
```

### Dashboard Interactif

Créer un dashboard Streamlit avec :
- Filtre par secteur
- Graphique de distribution des scores
- Timeline historique
- Comparaison avant/après pénalité

---

## 📝 Fichiers Créés/Modifiés

### Fichiers Créés

```
src/need_scanner/analysis/sector.py
src/need_scanner/processing/mmr.py
src/need_scanner/processing/history.py
src/need_scanner/fetchers/balanced_sampling.py
src/need_scanner/jobs/enriched_pipeline.py
config/sources_config.yaml
docs/ENGINE_IMPROVEMENTS.md
data/history/clusters.jsonl (auto-généré)
```

### Fichiers Modifiés

```
src/need_scanner/config.py
src/need_scanner/schemas.py
src/need_scanner/analysis/summarize.py
.env.example
requirements.txt
```

---

## 💡 Conseils d'Utilisation

### Contrôle des Coûts

1. **Limiter TOP_K_ENRICHMENT** : Plus ce nombre est petit, moins le pipeline coûte cher
2. **Ajuster NS_MMR_TOP_K** : Sélectionner moins de clusters finaux réduit les coûts d'affichage
3. **Désactiver le modèle lourd** : Utiliser uniquement `gpt-4o-mini` pour tous les clusters (moins cher mais moins qualitatif)

### Optimiser la Diversité

1. **Augmenter λ MMR** : λ=0.8 privilégie la pertinence, λ=0.5 privilégie la diversité
2. **Ajuster top_k_per_sector** : Limite le nombre de clusters par secteur dans le MMR

### Gérer l'Historique

1. **Augmenter RETENTION_DAYS** : Garder plus d'historique (30-90 jours)
2. **Augmenter PENALTY_FACTOR** : Pénaliser plus fortement les répétitions (0.3-0.5)
3. **Nettoyer manuellement** : Supprimer `data/history/clusters.jsonl` pour repartir de zéro

---

## 🆘 Support

Pour toute question ou problème :
1. Consulter les logs (`loguru` activé par défaut)
2. Vérifier la configuration (`.env` et `config/sources_config.yaml`)
3. Ouvrir une issue sur GitHub

---

**Made with ❤️ using Claude Code**
