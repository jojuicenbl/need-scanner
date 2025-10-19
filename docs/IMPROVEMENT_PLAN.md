# 🚀 Plan d'Amélioration Multi-Secteur - need_scanner

**Objectif** : Transformer le moteur tech-centré en radar multi-secteur business

**Date** : 2025-10-16
**Statut** : 📋 Planification

---

## 📊 Vue d'Ensemble

### Transformation Majeure

```
AVANT (Phase 1)                    APRÈS (Multi-Secteur)
━━━━━━━━━━━━━━━━━━━━━━            ━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sources  : Reddit + HN + RSS       Sources  : 7 sources
Secteur  : Tech/Dev                Secteurs : 12+ métiers
Posts    : ~70/run                 Posts    : 150-300/run
Intent   : Basic                   Intent   : FR+EN enrichi
Analysis : Basic LLM               Analysis : Enriched (JTBD, WTP, etc.)
Export   : 11 colonnes             Export   : 14 colonnes + priority
Cost     : $0.0004                 Cost     : <$1.00/run
```

---

## 🎯 Axes d'Amélioration

### AXE 1 : ÉLARGIR LE RADAR (Sources & Requêtes)

**Nouvelles sources à implémenter** :

| # | Source | Module | Priorité | Effort | Impact |
|---|--------|--------|----------|--------|--------|
| 1 | Twitter/X | `fetchers/twitter.py` | 🔴 HIGH | 3h | 🌟🌟🌟 |
| 2 | Product Hunt | `fetchers/producthunt.py` | 🟡 MED | 2h | 🌟🌟 |
| 3 | Stack Exchange | `fetchers/stackexchange.py` | 🟡 MED | 2h | 🌟🌟 |
| 4 | App Store Reviews | `fetchers/appstore.py` | 🟢 LOW | 3h | 🌟 |
| 5 | Reddit (extend) | `fetchers/reddit.py` | 🔴 HIGH | 30min | 🌟🌟🌟 |
| 6 | HN (extend) | `fetchers/hn.py` | 🟡 MED | 30min | 🌟🌟 |
| 7 | RSS (extend) | `config/rss_feeds.txt` | 🟡 MED | 1h | 🌟🌟 |

**Total effort estimé** : ~12h

---

### AXE 2 : AIGUISER L'ANALYSE (Intelligence)

**Améliorations analytiques** :

| # | Composant | Module | Priorité | Effort | Impact |
|---|-----------|--------|----------|--------|--------|
| 1 | Prompt enrichi | `analysis/summarize.py` | 🔴 HIGH | 1h | 🌟🌟🌟 |
| 2 | Signaux FR/EN | `analysis/intent.py` | 🔴 HIGH | 2h | 🌟🌟🌟 |
| 3 | Scoring priorité | `analysis/scoring.py` | 🔴 HIGH | 2h | 🌟🌟🌟 |
| 4 | Export enrichi | `export/writer.py` | 🟡 MED | 1h | 🌟🌟 |
| 5 | Slack notifs | `notifications/slack.py` | 🟢 LOW | 1h | 🌟 |

**Total effort estimé** : ~7h

---

## 📋 Plan d'Implémentation Détaillé

### PHASE A : Sources Prioritaires (🔴 HIGH)

#### A1. Extension Reddit (30min)
```python
# Ajouter dans fetchers/reddit.py
BUSINESS_SUBREDDITS = [
    "Entrepreneur", "smallbusiness", "SaaS",
    "France", "AutoEntrepreneur", "restauration",
    "freelance"  # déjà présent
]
```

#### A2. Twitter/X Fetcher (3h)
```python
# Nouveau: fetchers/twitter.py
def fetch_tweets(
    queries: List[str],
    days: int = 7,
    limit: int = 200
) -> List[Post]:
    # Utiliser snscrape
    # Queries FR+EN métiers
    # Rate limiting
```

**Queries** :
```python
QUERIES_EN = [
    "need a tool", "how do you manage", "what do you use"
]
QUERIES_FR = [
    "je cherche un outil", "comment vous gérez"
]
PERSONAS = [
    "accountant", "therapist", "coach", "restaurant",
    "comptable", "thérapeute", "artisan"
]
```

#### A3. Enrichissement Signaux (2h)
```python
# analysis/intent.py - Dictionnaires FR/EN
BUSINESS_KEYWORDS_FR = [
    "facture", "devis", "relance", "rendez-vous",
    "planning", "TVA", "URSSAF", "stock"
]
BUSINESS_KEYWORDS_EN = [
    "invoice", "quote", "booking", "refund",
    "compliance", "inventory", "timesheet"
]
WTP_SIGNALS = [
    "I'd pay", "budget", "hire someone",
    "spent hours", "losing money", "cost me"
]
```

---

### PHASE B : Sources Secondaires (🟡 MED)

#### B1. Product Hunt (2h)
```python
# fetchers/producthunt.py
- RSS officiel
- Scrape top 20 comments/produit
- Throttle 2s
```

#### B2. Stack Exchange (2h)
```python
# fetchers/stackexchange.py
- Sites: workplace, money, webmasters
- Tags: automation, invoice, booking
- API officielle
```

#### B3. Requêtes HN (30min)
```python
# Ajouter dans fetchers/hn.py
EXTENDED_QUERIES = [
    "How do you manage",
    "What tool do you use",
    "Looking for",
    "Anyone using"
]
```

---

### PHASE C : Analyse Enrichie (🔴 HIGH)

#### C1. Prompt LLM Enrichi (1h)
```python
# analysis/summarize.py - Nouveau prompt
ENRICHED_PROMPT = """
Extraire :
- title (3-6 mots)
- problem (2-3 phrases)
- persona (Freelance designer, PME owner, etc.)
- jtbd (format: "Quand X, je veux Y, afin de Z")
- context (outils actuels, contraintes)
- alternatives (liste outils mentionnés)
- monetizable (bool)
- mvp (1 phrase)
- willingness_to_pay_signal (evidence WTP)
- pricing_hint (estimation budget)
- pain_score_llm (0-10)

JSON strict uniquement.
"""
```

#### C2. Nouveau Scoring (2h)
```python
# analysis/scoring.py
def compute_priority_score(
    pain_score_llm: int,
    heuristic_signal: float,
    wtp_score: float,
    addressability: float
) -> float:
    """
    priority = 0.45*pain_llm
             + 0.25*heuristic
             + 0.20*wtp
             + 0.10*addressability
    """
    return weighted_sum
```

#### C3. Export Enrichi (1h)
```python
# export/writer.py - Nouvelles colonnes CSV
ENRICHED_COLUMNS = [
    "rank", "cluster_id", "title", "persona",
    "jtbd", "problem", "context", "mvp",
    "monetizable", "pain_score_llm",
    "willingness_to_pay_signal", "pricing_hint",
    "priority", "example_urls", "source_mix"
]
```

---

### PHASE D : Infrastructure (🟡 MED)

#### D1. Commande Prefilter
```bash
python -m need_scanner prefilter \
  --input data/raw/run_*.json \
  --lang all \
  --keep-intents pain,request \
  --out data/filtered.json
```

#### D2. Slack Notifications (optionnel)
```python
# notifications/slack.py
def send_top_insights(
    insights: List[EnrichedInsight],
    webhook_url: str,
    top_n: int = 5
):
    # Envoyer Top 5 par priority
    # Format: titre + persona + mvp + priority
```

---

## 🎯 Critères d'Acceptation

### Technique
- [ ] ≥ 3 nouvelles sources fonctionnelles (Twitter, PH, SE min)
- [ ] Intent classifier FR+EN avec WTP signals
- [ ] Prompt enrichi retourne 11 champs
- [ ] Scoring priority implémenté et testé
- [ ] Export CSV avec 14 colonnes
- [ ] Coût total < $1.00 par run

### Performance
- [ ] 150-300 posts collectés / run (7 jours)
- [ ] ≥ 8 clusters générés
- [ ] Top 3 insights avec priority > 7.0
- [ ] Déduplication cross-source < 30% duplicates

### Qualité
- [ ] ≥ 3 secteurs non-tech représentés
- [ ] ≥ 50% posts avec WTP signals détectés
- [ ] Persona identifiable dans 90% des clusters
- [ ] MVP faisable dans 80% des cas

---

## 📅 Timeline Estimée

```
Jour 1-2 : PHASE A (Sources prioritaires)     [4h]
Jour 3-4 : PHASE B (Sources secondaires)      [5h]
Jour 5-6 : PHASE C (Analyse enrichie)         [4h]
Jour 7   : PHASE D (Infrastructure)           [2h]
Jour 8   : Tests & validation                 [3h]
         ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
         TOTAL : ~8 jours (18h dev effectif)
```

---

## 🔧 Configuration Recommandée

### Nouveaux paramètres `.env`
```bash
# Twitter/X
TWITTER_ENABLED=true
TWITTER_MAX_TWEETS=200

# Product Hunt
PH_ENABLED=true
PH_MAX_PRODUCTS=20

# Stack Exchange
SE_ENABLED=true
SE_MAX_QUESTIONS=50

# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
SLACK_NOTIFY_ENABLED=false

# Coûts
NS_COST_WARN_USD=0.40
NS_COST_HARD_CAP_USD=2.00
```

### Nouveaux fichiers config
```
config/
├── rss_feeds.txt           (déjà présent)
├── rss_feeds_metiers.txt   (nouveau - PME, santé, etc.)
├── reddit_subs.txt         (nouveau - liste métiers)
└── twitter_queries.txt     (nouveau - queries FR+EN)
```

---

## 🚦 Prochaines Étapes

**IMMÉDIAT** :
1. Valider ce plan d'amélioration
2. Choisir ordre d'implémentation (A→B→C→D ou autre)
3. Commencer PHASE A1 (Reddit extension)

**Questions à clarifier** :
- Préférence ordre implémentation ?
- Twitter/X : utiliser snscrape ou API officielle ?
- Product Hunt : scraping OK ou préférer API officielle ?
- Slack : priorité haute ou basse ?

---

## 📊 Métriques de Succès

### Avant (Phase 1)
- 3 sources
- ~70 posts/run
- 5 clusters tech
- $0.0004/run

### Après (Multi-Secteur)
- 7+ sources
- 150-300 posts/run
- 8-12 clusters multi-secteurs
- <$1.00/run
- 3+ secteurs non-tech
- WTP signals détectés
- Priority ranking fonctionnel

---

**Prêt à démarrer ?** 🚀
