# 🔍 Need Scanner

**Radar de découverte de marché multi-secteur** - Détecte automatiquement les besoins utilisateurs non satisfaits à partir de posts Reddit, Hacker News, Stack Exchange et autres sources en ligne.

## 🎯 Objectif

Transformer des milliers de posts utilisateurs en insights actionnables pour identifier des opportunités de produits/services à lancer.

## ✨ Fonctionnalités

### 🚀 **NOUVEAU : Améliorations Moteur (v2.0)**
- ✅ **Configuration Multi-Modèle** : gpt-4o pour TOP K, gpt-4o-mini pour le reste (optimisation coûts)
- ✅ **Tags Sectoriels** : Classification automatique en 13 secteurs (dev_tools, business_pme, health_wellbeing, etc.)
- ✅ **MMR Reranking** : Sélection diversifiée des TOP N clusters (pertinence + diversité)
- ✅ **Mémoire Inter-Jour** : Pénalité automatique des clusters similaires à l'historique
- ✅ **Scoring Discriminant** : Prompts améliorés pour des scores pain/novelty/trend plus expressifs
- ✅ **Sources Multi-Secteur** : Configuration YAML avec catégories et quotas par secteur

### 🎯 **NOUVEAU : Améliorations ÉTAPE 1 (2025-11)**
- ✅ **Trend Score LLM** : Score hybride marché (70% analyse LLM + 30% croissance historique)
- ✅ **Founder Fit Score** : Évaluation adéquation opportunité vs profil fondateur (1-10)
- ✅ **MVP améliorés** : Prompts optimisés pour éviter les "guides PDF" et privilégier vrais produits/services

### 📚 **NOUVEAU : Lib + Base SQLite (ÉTAPE 2)**
- ✅ **API Python** : Fonction `run_scan()` réutilisable pour intégration programmatique
- ✅ **Base SQLite** : Stockage persistant runs & insights (query, filtrage, historique)
- ✅ **CLI Enrichi** : Commandes `scan`, `list-runs`, `show-insights` pour usage simplifié
- ✅ **Rétrocompatibilité** : Conservation exports CSV/JSON + anciens scripts

📖 **Voir documentation** : [docs/ENGINE_IMPROVEMENTS.md](docs/ENGINE_IMPROVEMENTS.md) | [docs/STEP1_ENGINE_IMPROVEMENTS.md](docs/STEP1_ENGINE_IMPROVEMENTS.md) | [docs/STEP2_LIB_AND_DATABASE.md](docs/STEP2_LIB_AND_DATABASE.md)

### 📊 **Analyse Enrichie**
- **10 champs extraits par insight** : persona, Job-To-Be-Done, contexte, alternatives, signaux WTP, MVP suggéré
- **Priority scoring** : Formule multi-composantes (Pain 30% + Traction 25% + Novelty 15% + WTP 20% + Trend 10%)
- **Founder Fit scoring** : Signal complémentaire pour filtrage personnel (1-10)
- **Détection WTP** : 7 types de signaux de volonté de payer (FR/EN)
- **Classification intent** : 6 types (pain, request, howto, promo, news, other)
- **Support multilingue** : Détection de 23+ langues

### 🌐 **Sources Multi-Secteur**

**Opérationnelles (sans authentification)** :
- ✅ **Reddit** - 26+ subreddits (freelance, PME, santé, éducation, restauration, marketing, etc.)
- ✅ **Hacker News** - Ask HN, Show HN
- ✅ **RSS feeds** - Flux personnalisables
- ✅ **Stack Exchange** - 14+ sites (stackoverflow, workplace, freelancing, startups, etc.)

**Prêtes (nécessitent API keys)** :
- 🔑 **Product Hunt** - Nouveaux produits et commentaires
- 🔑 **Twitter/X** - Recherches configurables

### 📈 **Pipeline Complet**

```
Collecte → Filtrage → Déduplication → Embeddings → Clustering → LLM Enrichi → Priority Scoring → Export
```

### 📤 **Export**

- **JSON enrichi** : Résultats complets avec métadonnées
- **CSV 20 colonnes** : Compatible Excel/Google Sheets
- Includes : rank, priority_score, persona, JTBD, context, alternatives, WTP signals, tous les scores

## 🚀 Installation

```bash
# Cloner le repo
git clone <repo-url>
cd need_scanner

# Créer environnement virtuel
python -m venv env
source env/bin/activate  # Linux/Mac
# env\Scripts\activate  # Windows

# Installer dépendances
pip install -r requirements.txt

# Configurer variables d'environnement
cp .env.example .env
# Éditer .env et ajouter votre OPENAI_API_KEY
```

### Configuration Requise

**Obligatoire** :
- Python 3.11+
- OpenAI API Key (pour embeddings + LLM)

**Optionnel** :
- Product Hunt API Token
- Twitter API v2 credentials

## ⚡ Quick Start (NOUVEAU - CLI v2.1)

```bash
# 1. Collecter des posts
python -m need_scanner collect-reddit-multi --limit-per-sub 30

# 2. Lancer un scan complet (stockage DB + CSV)
python -m need_scanner scan --mode deep --max-insights 20

# 3. Voir les résultats
python -m need_scanner show-insights <RUN_ID>

# 4. Lister l'historique
python -m need_scanner list-runs
```

**Nouveauté :** La commande `scan` orchestre tout le pipeline (embeddings, clustering, enrichissement LLM, scoring) et sauvegarde automatiquement dans une base SQLite + génère CSV/JSON.

## 📖 Guide d'Utilisation Détaillé

### 1. Collecter des Données

**Reddit multi-subreddits** (recommandé) :
```bash
python -m need_scanner collect-reddit-multi --limit-per-sub 30
# Collecte 30 posts de chaque subreddit configuré (~780 posts)
```

**Hacker News** :
```bash
python -m need_scanner collect-hn --days 30 --min-points 20
```

**Stack Exchange** :
```bash
python -m need_scanner collect-stackexchange --sites stackoverflow,workplace --days 7
```

**Toutes les sources** :
```bash
python -m need_scanner collect-all --reddit-subreddit freelance --rss-feeds-file config/rss_feeds.txt
```

### 2. Prévisualiser les Données

```bash
python -m need_scanner prefilter --filter-lang en --detect-wtp --show-sample 10
```

Affiche :
- Distribution des sources
- Distribution des langues
- Distribution des intents
- Signaux WTP détectés
- Échantillon de posts

### 3. Analyser avec le Pipeline Complet

```bash
python -m need_scanner run --input "data/raw/posts_*.json" --clusters 5 --output-dir data/results
```

**Sortie** :
- `data/results/cluster_results.json` - Résultats complets
- `data/results/embeddings.npy` - Vecteurs d'embeddings
- `data/results/meta.json` - Métadonnées des posts

### 4. Exporter en CSV

Les résultats JSON peuvent être convertis en CSV enrichi (20 colonnes) avec les scripts fournis.

## 📊 Exemple de Résultat

```
#1 - Mauvaise préparation projet (Priority: 5.68/10)

🎯 Persona: Entrepreneur en technologie

📋 JTBD: Quand je commence un nouveau projet, je veux m'assurer que
         je résous le bon problème, afin de maximiser la valeur pour
         mes utilisateurs.

😣 Problème: Les utilisateurs se retrouvent souvent confrontés à des
             problèmes inattendus dans leurs projets, ce qui entraîne
             une perte de temps et d'efforts.

🔧 Contexte: Outils de gestion de projet existants, mais manque de
             validation d'hypothèses au démarrage.

💡 MVP: Créer un outil simple de validation d'idée qui permet aux
        utilisateurs de tester leurs hypothèses rapidement.

🔄 Alternatives: [] (aucune!)

💰 WTP Signal: looking for paid solution

📊 Scores:
   Pain (LLM):    9/10
   Traction:      5.0/10
   Novelty:       10.0/10
   Priority:      5.68/10
```

## 🛠️ Configuration Avancée

### Reddit Multi-Subreddits

Éditer `config/reddit_subs.txt` :
```
# Ajouter vos subreddits (un par ligne, sans r/)
freelance
Entrepreneur
smallbusiness
# ... etc
```

### Stack Exchange Sites

Éditer `config/stackexchange_sites.txt` :
```
stackoverflow
workplace
freelancing
startups
```

### Product Hunt

1. Obtenir un token : https://www.producthunt.com/v2/oauth/applications
2. Ajouter à `.env` : `PRODUCTHUNT_API_TOKEN=your_token`
3. Utiliser : `python -m need_scanner collect-producthunt --days 7`

## 💰 Coûts

**Avec OpenAI API** :
- Embeddings (text-embedding-3-small) : ~$0.00001 par post
- Summarization (gpt-4o-mini) : ~$0.0002 par cluster

**Exemple réel** :
- 43 posts → 5 clusters enrichis = **$0.0012**
- 200 posts → 10 clusters = ~$0.02-0.05

## 📁 Structure du Projet

```
need_scanner/
├── src/need_scanner/
│   ├── fetchers/          # Collecteurs de données
│   │   ├── reddit.py      # Reddit (multi-subreddit)
│   │   ├── hn.py          # Hacker News
│   │   ├── rss.py         # RSS feeds
│   │   ├── twitter.py     # Twitter/X
│   │   ├── producthunt.py # Product Hunt
│   │   └── stackexchange.py # Stack Exchange
│   ├── analysis/          # Analyse et enrichissement
│   │   ├── intent.py      # Classification intent
│   │   ├── wtp.py         # Détection WTP
│   │   ├── summarize.py   # LLM enrichi
│   │   ├── scoring.py     # Pain scoring
│   │   └── priority.py    # Priority scoring
│   ├── processing/        # Pipeline de traitement
│   │   ├── filters.py     # Filtres (langue, score, etc.)
│   │   ├── clean.py       # Nettoyage
│   │   ├── dedupe.py      # Déduplication
│   │   ├── embed.py       # Embeddings
│   │   └── cluster.py     # Clustering
│   ├── export/            # Export des résultats
│   │   └── writer.py      # JSON + CSV
│   └── cli.py             # Interface CLI
├── config/                # Fichiers de configuration
│   ├── reddit_subs.txt    # Liste de subreddits
│   ├── twitter_queries.txt # Requêtes Twitter
│   ├── producthunt_categories.txt
│   ├── stackexchange_sites.txt
│   └── rss_feeds.txt
├── data/                  # Données (git-ignoré)
│   ├── raw/              # Posts collectés
│   └── results/          # Résultats d'analyse
└── docs/                  # Documentation
    ├── SPRINT_TRACKING.md
    ├── DATA_GUIDE.md
    └── IMPROVEMENT_PLAN.md
```

## 🧪 Tests

**Test rapide (Sprint 1)** :
```bash
python test_sprint1.py
```
Analyse 43 posts filtrés → 5 clusters enrichis ($0.0012)

**Prefilter sur dataset complet** :
```bash
python -m need_scanner prefilter --input-pattern "data/raw/posts_*.json" --filter-lang en --detect-wtp
```

## 📚 Documentation Complète

- `docs/SPRINT_TRACKING.md` - Suivi des développements
- `docs/DATA_GUIDE.md` - Guide des données
- `docs/IMPROVEMENT_PLAN.md` - Plan d'amélioration
- `.claude/` - Commandes Claude Code personnalisées

## 🤝 Contributing

Ce projet a été développé avec Claude Code. Pour contribuer :

1. Fork le repo
2. Créer une branche feature
3. Commiter vos changements
4. Pousser vers la branche
5. Ouvrir une Pull Request

## 📝 Licence

[Spécifier la licence]

## 🙏 Remerciements

- OpenAI pour les APIs (embeddings + GPT-4o-mini)
- Reddit, Hacker News, Stack Exchange pour les données publiques
- Claude Code pour l'assistance au développement

## 📈 Roadmap

**Complété** :
- ✅ Multi-source collection (7 sources)
- ✅ Analyse enrichie (10 champs)
- ✅ Priority scoring
- ✅ Export CSV 20 colonnes
- ✅ Détection WTP FR/EN

**v2.0 - Améliorations Moteur** (2025-01) :
- ✅ Configuration multi-modèle (light/heavy)
- ✅ Tags sectoriels automatiques
- ✅ MMR reranking pour diversité
- ✅ Mémoire inter-jour (historique)
- ✅ Scoring plus discriminant
- ✅ Sources multi-secteur équilibrées

**À venir** :
- [ ] Dashboard web interactif
- [ ] Notifications Slack/Discord enrichies
- [ ] Support App Store reviews
- [ ] Intégration Docker
- [ ] CI/CD pipeline

## 💬 Support

Pour questions ou suggestions :
- Ouvrir une issue sur GitHub
- Consulter la documentation dans `docs/`

---

**Made with ❤️ using Claude Code**
