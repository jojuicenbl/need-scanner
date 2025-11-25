# 🚀 ÉTAPE 2 - Transformation en Lib + CLI avec SQLite

**Date :** 2025-11-25
**Branche :** `feature/step-2` (ou `feature/step-1` si continuation)

---

## 📋 Résumé

Transformation du Need Scanner en une vraie bibliothèque Python réutilisable avec stockage persistant en base de données SQLite.

### Améliorations Principales

1. **✅ Module `core.py`** : Fonction `run_scan()` réutilisable exposant le pipeline complet
2. **✅ Base SQLite** : Stockage persistant des runs et insights
3. **✅ CLI Enrichi** : Nouvelles commandes `scan`, `list-runs`, `show-insights`
4. **✅ Compatibilité** : Conservation des exports CSV/JSON existants

---

## 🎯 1. Module Core - Bibliothèque Réutilisable

### Nouveau Fichier : `src/need_scanner/core.py`

Expose la fonction principale `run_scan()` qui orchestre tout le pipeline.

### Usage Programmatique

```python
from need_scanner.core import run_scan

# Run complet avec sauvegarde DB
run_id = run_scan(
    mode="deep",              # ou "light"
    max_insights=20,
    save_to_db=True
)

print(f"Scan terminé ! Run ID: {run_id}")
```

### Signature Complète

```python
def run_scan(
    config_name: Optional[str] = None,
    mode: str = "deep",
    max_insights: Optional[int] = None,
    input_pattern: str = "data/raw/posts_*.json",
    output_dir: Optional[Path] = None,
    save_to_db: bool = True,
    db_path: Optional[Path] = None,
    use_mmr: bool = True,
    use_history_penalty: bool = True
) -> str
```

### Paramètres

| Paramètre | Type | Default | Description |
|-----------|------|---------|-------------|
| `config_name` | str | None | Nom de configuration (usage futur) |
| `mode` | str | "deep" | "light" (rapide/pas cher) ou "deep" (meilleure qualité) |
| `max_insights` | int | None | Limite nombre d'insights (post-MMR) |
| `input_pattern` | str | "data/raw/posts_*.json" | Pattern glob pour fichiers d'entrée |
| `output_dir` | Path | None | Dossier de sortie (default: data/results_v2) |
| `save_to_db` | bool | True | Sauvegarder dans la base |
| `db_path` | Path | None | Chemin DB personnalisé |
| `use_mmr` | bool | True | Utiliser MMR reranking |
| `use_history_penalty` | bool | True | Pénalité similarité historique |

### Valeur de Retour

- **`run_id`** (str) : Identifiant unique du scan (format : `YYYYMMDD_HHMMSS`)

### Modes d'Exécution

**Mode "deep" (défaut) :**
- Utilise `gpt-4o` pour TOP K insights (meilleure qualité)
- Utilise `gpt-4o-mini` pour le reste
- Plus cher mais résultats supérieurs

**Mode "light" :**
- Utilise `gpt-4o-mini` pour tout
- Plus rapide et moins cher
- Qualité légèrement inférieure

---

## 🎯 2. Base de Données SQLite

### Nouveau Fichier : `src/need_scanner/db.py`

Module complet de gestion de base de données avec SQLite.

### Emplacement DB

**Par défaut :** `data/needscanner.db`

**Personnalisation :**
```bash
# Via variable d'environnement
export NEEDSCANNER_DB_PATH=/custom/path/mydb.db

# Ou en Python
from need_scanner.core import run_scan
run_scan(db_path=Path("/custom/path/mydb.db"))
```

### Schéma de Tables

#### Table `runs`

Métadonnées de chaque scan.

```sql
CREATE TABLE runs (
    id TEXT PRIMARY KEY,              -- Run ID (YYYYMMDD_HHMMSS)
    created_at TIMESTAMP NOT NULL,
    config_name TEXT,
    mode TEXT,                        -- "light" ou "deep"
    nb_insights INTEGER,
    nb_clusters INTEGER,
    total_cost_usd REAL,
    embed_cost_usd REAL,
    summary_cost_usd REAL,
    csv_path TEXT,
    json_path TEXT,
    notes TEXT
)
```

#### Table `insights`

Insights individuels de chaque run.

```sql
CREATE TABLE insights (
    id TEXT PRIMARY KEY,              -- run_id_cluster_X
    run_id TEXT NOT NULL,
    rank INTEGER,
    mmr_rank INTEGER,
    cluster_id INTEGER,
    size INTEGER,
    sector TEXT,
    title TEXT NOT NULL,
    problem TEXT,
    persona TEXT,
    jtbd TEXT,
    context TEXT,
    mvp TEXT,
    alternatives TEXT,                -- JSON array
    willingness_to_pay_signal TEXT,
    monetizable INTEGER,              -- 0/1
    pain_score_llm REAL,
    pain_score_final REAL,
    heuristic_score REAL,
    traction_score REAL,
    novelty_score REAL,
    trend_score REAL,                 -- NOUVEAU (ÉTAPE 1)
    founder_fit_score REAL,           -- NOUVEAU (ÉTAPE 1)
    priority_score REAL,
    priority_score_adjusted REAL,
    keywords_matched TEXT,            -- JSON array
    source_mix TEXT,                  -- JSON array
    example_urls TEXT,                -- JSON array
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id)
)
```

### Index Créés

- `idx_insights_run_id` : Requêtes par run
- `idx_insights_rank` : Tri par rank
- `idx_insights_priority` : Tri par priorité
- `idx_insights_sector` : Filtrage par secteur
- `idx_runs_created` : Runs récents

### Fonctions Utilitaires

```python
from need_scanner.db import (
    init_database,
    list_runs,
    get_run_insights,
    query_insights
)

# Initialiser la DB
init_database()

# Lister runs récents
runs = list_runs(limit=10)

# Récupérer insights d'un run
insights = get_run_insights("20251125_143022", limit=20)

# Query avec filtres
insights = query_insights(
    sector="dev_tools",
    min_priority=7.0,
    min_founder_fit=8.0,
    monetizable_only=True,
    limit=50
)
```

---

## 🎯 3. CLI Enrichi

### Nouvelles Commandes

#### `scan` - Lancer un scan complet

```bash
# Mode deep (défaut)
python -m need_scanner scan

# Mode light (rapide & pas cher)
python -m need_scanner scan --mode light

# Avec limite d'insights
python -m need_scanner scan --mode deep --max-insights 20

# Custom input/output
python -m need_scanner scan \
  --input-pattern "data/custom/*.json" \
  --output-dir data/custom_results

# Sans sauvegarde DB
python -m need_scanner scan --no-db

# Sans MMR ni historique
python -m need_scanner scan --no-mmr --no-history
```

**Options disponibles :**
- `--config` : Nom de configuration (futur)
- `--mode` : "light" ou "deep" (default: deep)
- `--max-insights` : Limite nombre d'insights
- `--input-pattern` : Pattern glob pour fichiers JSON
- `--output-dir` : Dossier de sortie
- `--no-db` : Skip sauvegarde base de données
- `--no-mmr` : Désactiver MMR reranking
- `--no-history` : Désactiver pénalité historique

#### `list-runs` - Lister les runs récents

```bash
# Lister 10 runs récents
python -m need_scanner list-runs

# Lister 20 runs
python -m need_scanner list-runs --limit 20
```

**Output :**
```
📊 Recent runs (showing 10):
================================================================================

🔍 Run ID: 20251125_143022
   Created: 2025-11-25 14:30:22
   Mode: deep
   Insights: 18
   Clusters: 25
   Cost: $0.0456
   CSV: data/results_v2/insights_20251125_143022.csv

...
```

#### `show-insights` - Afficher insights d'un run

```bash
# Top 10 insights d'un run
python -m need_scanner show-insights 20251125_143022

# Top 20
python -m need_scanner show-insights 20251125_143022 --limit 20

# Filtrer par priorité
python -m need_scanner show-insights 20251125_143022 --min-priority 7.0

# Filtrer par secteur et founder fit
python -m need_scanner show-insights 20251125_143022 \
  --sector dev_tools \
  --min-fit 8.0
```

**Options de filtrage :**
- `--limit` : Nombre max d'insights
- `--sector` : Filtrer par secteur
- `--min-priority` : Score priorité minimum
- `--min-fit` : Founder fit score minimum

**Output :**
```
🎯 Insights for run 20251125_143022 (showing 10):
================================================================================

#1: API Rate Limiting Solution
   Sector: dev_tools | Persona: Backend Developer
   📊 Priority: 7.85 | Pain: 8 | Trend: 7.2 | Fit: 9.0
   Problem: Developers struggle with implementing efficient rate limiting...
   MVP: Build a lightweight API gateway with built-in rate limiting...

...
```

---

## 🎯 4. Workflow Complet

### Exemple d'Utilisation CLI

```bash
# 1. Collecter des posts
python -m need_scanner collect-reddit-multi --limit-per-sub 30

# 2. Lancer un scan
python -m need_scanner scan --mode deep --max-insights 20

# Output:
# ✅ Scan complete! Run ID: 20251125_143022
# 💡 View results:
#    python -m need_scanner show-insights 20251125_143022

# 3. Voir les résultats
python -m need_scanner show-insights 20251125_143022

# 4. Lister l'historique
python -m need_scanner list-runs --limit 5
```

### Exemple d'Utilisation Programmatique

```python
from need_scanner.core import run_scan, list_recent_runs, get_insights_for_run

# Run scan
run_id = run_scan(mode="deep", max_insights=20)

# Lister runs récents
runs = list_recent_runs(limit=5)
for run in runs:
    print(f"{run['id']}: {run['nb_insights']} insights")

# Récupérer insights d'un run
insights = get_insights_for_run(run_id, limit=10)
for insight in insights:
    print(f"#{insight['rank']}: {insight['title']}")
    print(f"  Priority: {insight['priority_score']:.2f}")
    print(f"  Fit: {insight['founder_fit_score']:.1f}")
```

---

## 📁 Fichiers Créés/Modifiés

### Nouveaux Fichiers

- ✅ `src/need_scanner/core.py` - Module principal avec `run_scan()`
- ✅ `src/need_scanner/db.py` - Gestion base SQLite
- ✅ `tests/test_db.py` - Tests pour la DB
- ✅ `docs/STEP2_LIB_AND_DATABASE.md` - Cette documentation

### Fichiers Modifiés

- ✅ `src/need_scanner/cli.py` - Ajout commandes `scan`, `list-runs`, `show-insights`

### Fichiers Non Modifiés

- ✅ `src/need_scanner/jobs/enriched_pipeline.py` - Utilisé tel quel par `core.py`
- ✅ `src/need_scanner/export/*` - Exports CSV/JSON conservés
- ✅ Tous les modules d'analyse existants

---

## 🧪 Tests

### Lancer les Tests

```bash
# Tests DB uniquement
pytest tests/test_db.py -v

# Tous les tests
pytest tests/ -v
```

### Tests Couverts

- ✅ Initialisation DB
- ✅ Génération run_id
- ✅ Sauvegarde/chargement runs
- ✅ Sauvegarde/chargement insights
- ✅ Gestion runs multiples
- ✅ Requêtes avec filtres

### Test Manuel Complet

```bash
# 1. Test scan complet
python -m need_scanner scan --mode light --max-insights 5

# 2. Vérifier DB créée
ls -lh data/needscanner.db

# 3. Lister runs
python -m need_scanner list-runs

# 4. Show insights
python -m need_scanner show-insights <RUN_ID>

# 5. Vérifier CSV généré
ls -lh data/results_v2/insights_*.csv
```

---

## 💡 Exemples Avancés

### Query Insights SQL Direct

```python
import sqlite3
from pathlib import Path

db_path = Path("data/needscanner.db")
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

# Insights avec founder fit > 8 et monetizable
cursor = conn.execute("""
    SELECT title, founder_fit_score, priority_score, mvp
    FROM insights
    WHERE founder_fit_score >= 8.0
      AND monetizable = 1
    ORDER BY priority_score DESC
    LIMIT 10
""")

for row in cursor:
    print(f"{row['title']}: Fit={row['founder_fit_score']:.1f}")
    print(f"  MVP: {row['mvp']}")

conn.close()
```

### Intégration dans Script Automatisé

```python
#!/usr/bin/env python
"""Automated daily scan."""

from need_scanner.core import run_scan
from need_scanner.db import get_run_insights
import datetime

# Run scan
run_id = run_scan(
    mode="light",
    max_insights=15,
    save_to_db=True
)

# Get top insights
insights = get_run_insights(run_id, limit=5)

# Send email/slack notification (pseudo-code)
message = f"Daily Scan {run_id} - {datetime.date.today()}\n\n"
for i, insight in enumerate(insights, 1):
    message += f"{i}. {insight['title']}\n"
    message += f"   Priority: {insight['priority_score']:.2f}\n\n"

# send_notification(message)
```

---

## 🔧 Configuration

### Variables d'Environnement

```bash
# Chemin base de données
export NEEDSCANNER_DB_PATH=/custom/path/needscanner.db

# Clé API OpenAI (déjà existante)
export OPENAI_API_KEY=sk-...
```

### Configuration Future (Multi-Config)

Le paramètre `config_name` est prévu pour supporter plusieurs configurations :
- Sources de données différentes
- Secteurs différents
- Paramètres de clustering différents

**Implémentation future :**
```python
# config/configs.yaml
default:
  sources: reddit,hn
  sectors: all

tech_only:
  sources: hn,stackexchange
  sectors: dev_tools,saas

# Usage
run_scan(config_name="tech_only")
```

---

## ⚡ Performance & Coûts

### Coûts par Mode

**Mode "light" (100 posts → 10 clusters) :**
- Embeddings : ~$0.001
- Enrichment (light model) : ~$0.015
- Trend + Founder fit : ~$0.003
- **Total : ~$0.019**

**Mode "deep" (100 posts → 10 clusters, TOP 5 heavy) :**
- Embeddings : ~$0.001
- Enrichment (5 heavy + 5 light) : ~$0.035
- Trend + Founder fit : ~$0.003
- **Total : ~$0.039**

### Taille Base de Données

Estimation pour 100 runs avec moyenne 15 insights/run :
- Runs : ~10 KB (100 runs × 0.1 KB)
- Insights : ~2.2 MB (1,500 insights × ~1.5 KB)
- **Total : ~2.2 MB**

Très léger, pas de problème de stockage.

---

## ✅ Checklist ÉTAPE 2

- [x] Créer module `core.py` avec `run_scan()`
- [x] Créer module `db.py` avec gestion SQLite
- [x] Définir schéma tables (runs, insights)
- [x] Implémenter sauvegarde automatique DB
- [x] Ajouter commande CLI `scan`
- [x] Ajouter commande CLI `list-runs`
- [x] Ajouter commande CLI `show-insights`
- [x] Conserver exports CSV/JSON
- [x] Créer tests unitaires DB
- [x] Documenter usage programmatique
- [x] Documenter usage CLI
- [x] Exemples d'intégration

---

## 🚀 Prochaines Étapes (Hors Scope ÉTAPE 2)

- [ ] Support multi-config via YAML
- [ ] API REST pour query insights
- [ ] Dashboard web (Streamlit ou Dash)
- [ ] Export vers Notion/Airtable
- [ ] Scheduled runs (cron integration)
- [ ] Alertes email/Slack pour insights prioritaires

---

**Statut :** ✅ ÉTAPE 2 COMPLÉTÉE
**Ready for :** Merge vers `main` après tests
**Rétrocompatibilité :** ✅ Complète (anciens scripts fonctionnent encore)
