# GitHub Actions Setup Guide

## ✅ Configuration Complète

Vous avez déjà configuré :
- ✅ `OPENAI_API_KEY` dans GitHub Secrets
- ✅ `SLACK_WEBHOOK_URL` dans GitHub Secrets
- ✅ Notifications Slack activées dans le workflow

---

## 🧪 Test Manuel du Workflow

### Option 1 : Via l'Interface GitHub (Recommandé)

1. **Allez sur votre repository GitHub dans votre navigateur**

2. **Cliquez sur l'onglet "Actions"** (en haut)

3. **Dans le menu de gauche, cliquez sur "Need Scanner Daily"**

4. **Cliquez sur le bouton "Run workflow"** (à droite)

5. **Configurez les paramètres (optionnel) :**
   - **pack:** `smallbiz_fr` (par défaut) ou `tech_dev`, `services_humans`, `europe_fr`
   - **reddit_limit:** `240` (par défaut) ou un nombre plus petit pour un test rapide (ex: `50`)

6. **Cliquez sur le bouton vert "Run workflow"**

7. **Rafraîchissez la page** après quelques secondes, vous verrez le workflow en cours d'exécution

8. **Cliquez sur le workflow en cours** pour voir les logs en temps réel

### Option 2 : Via GitHub CLI (Avancé)

```bash
# Installer gh si nécessaire
brew install gh

# S'authentifier
gh auth login

# Lancer le workflow avec paramètres par défaut
gh workflow run "Need Scanner Daily"

# Ou avec paramètres personnalisés
gh workflow run "Need Scanner Daily" \
  -f pack=tech_dev \
  -f reddit_limit=50

# Voir les runs
gh run list --workflow="Need Scanner Daily"

# Voir les logs du dernier run
gh run view --log
```

---

## 📊 Ce qui va se passer

### Pendant l'exécution (10-15 minutes) :

1. **Setup Python** (~30 secondes)
2. **Install dependencies** (~1 minute)
3. **Collect posts** (~5-10 minutes, selon reddit_limit)
4. **Prefilter posts** (~30 secondes)
5. **Run pipeline** (~2-3 minutes)
6. **Upload results** (~10 secondes)
7. **Commit history** (~5 secondes)
8. **Extract metrics** (~5 secondes)
9. **Send Slack notification** (~2 secondes)

### Notification Slack attendue :

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Need Scanner Daily Scan Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Posts Analyzed:          Clusters Found:
780                      8

Top Priority:
Problèmes de Nomination et Branding (Score: 6.12)

View Full Results →
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 📥 Récupérer les Résultats

### Via l'Interface GitHub :

1. Allez dans l'onglet **Actions**
2. Cliquez sur le **run terminé**
3. Scrollez en bas, section **Artifacts**
4. Téléchargez **daily-insights-XXX.zip**
5. Décompressez pour accéder à :
   - `insights_enriched.csv` (résultats V2)
   - `cluster_results.json` (données complètes)

### Via GitHub CLI :

```bash
# Lister les artifacts
gh run list --workflow="Need Scanner Daily" --limit 1

# Télécharger les artifacts du dernier run
gh run download
```

---

## 🔄 Automatisation Quotidienne

Le workflow s'exécutera automatiquement **chaque jour à 08:15 (heure de Paris)**.

Vous recevrez une notification Slack à chaque exécution réussie.

### Modifier l'horaire :

Éditez `.github/workflows/need_scanner_daily.yml` :

```yaml
schedule:
  # Format: "minute hour * * *" (UTC)
  # Exemple: 07:00 Paris = 05:00 UTC
  - cron: "0 5 * * *"
```

**Conversion UTC → Paris :**
- Paris = UTC + 1 (hiver) ou UTC + 2 (été)
- 06:15 UTC = 08:15 Paris (hiver) ou 07:15 Paris (été)

---

## 🛠️ Personnaliser le Pack Quotidien

Modifier le pack par défaut dans le workflow :

```yaml
inputs:
  pack:
    description: 'Subreddit pack to use'
    required: false
    default: 'tech_dev'  # Changez ici
```

---

## 🚨 En Cas de Problème

### Le workflow échoue :

1. Vérifiez les logs dans l'onglet Actions
2. Vérifiez que `OPENAI_API_KEY` est bien configuré dans Secrets
3. Vérifiez que les fichiers de config existent (`config/packs/`, `config/intent_patterns.txt`)

### Pas de notification Slack :

1. Vérifiez que `SLACK_WEBHOOK_URL` est bien configuré
2. Testez le webhook manuellement :
   ```bash
   curl -X POST "VOTRE_WEBHOOK_URL" \
     -H 'Content-Type: application/json' \
     -d '{"text":"Test notification"}'
   ```
3. Vérifiez que le workflow s'est terminé avec succès (if: success())

### Notifications Slack pour les erreurs aussi :

Remplacez `if: success()` par `if: always()` dans le workflow pour recevoir des notifications même en cas d'échec.

---

## 📊 Historique et Trends

Après plusieurs runs quotidiens :
- **Jour 1** : Novelty=8.0, Trend=5.0 (neutre, pas d'historique)
- **Jour 2-7** : Les scores commencent à avoir du sens
- **Après 4 semaines** : Trends et novelty très significatifs

Les fichiers d'historique sont automatiquement committés dans `data/history/`.

---

## 🎯 Next Steps

1. **Lancez un test manuel** (voir ci-dessus)
2. **Vérifiez la notification Slack**
3. **Téléchargez les résultats**
4. **Attendez la première run automatique demain matin**
5. **Explorez les insights dans le CSV**

---

**Dernière mise à jour** : 19 octobre 2025
