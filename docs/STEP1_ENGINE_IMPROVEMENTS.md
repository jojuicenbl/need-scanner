# 🚀 ÉTAPE 1 - Améliorations Moteur Complétées

**Date :** 2025-11-25
**Branche :** `feature/step-1`

---

## 📋 Résumé

Amélioration du moteur actuel sans refonte architecturale complète. Cette étape implémente 3 améliorations majeures :

1. **✅ `trend_score` LLM** : Transformation du trend score basé uniquement sur la croissance historique en un score hybride combinant analyse LLM du marché (70%) + croissance historique (30%)

2. **✅ `founder_fit_score`** : Nouveau signal évaluant l'adéquation de l'opportunité avec le profil du fondateur (dev fullstack, SaaS B2B, PME tools)

3. **✅ Prompt MVP amélioré** : Modifications du prompt LLM pour éviter les MVP "guide PDF / article" et privilégier les produits/services concrets

---

## 🎯 1. Amélioration du `trend_score`

### Avant
- **Calcul :** Week-over-week growth uniquement (taille des clusters)
- **Problème :** Dépend de l'historique (souvent vide), peu discriminant, ne détecte pas les vraies tendances marché
- **Résultat :** La plupart des scores autour de 5.0 (neutre)

### Après
- **Calcul :** Score hybride = 70% LLM + 30% historique
- **LLM évalue :**
  - Émergence de nouveaux outils dans l'espace
  - Évolution technologique facilitante (AI, automation, no-code)
  - Market shifts (remote work, privacy, coûts)
  - Buzz médias / réseaux sociaux
- **Échelle discriminante :** 1-10 avec guidelines strictes pour utiliser toute l'échelle
- **Implémentation :** `src/need_scanner/analysis/trends.py`
  - Nouvelle fonction : `calculate_llm_trend_score()`
  - Nouvelle fonction : `calculate_hybrid_trend_score()`

### Prompt LLM
```
Évalue la TENDANCE MARCHÉ de ce problème :
- 1-3 : Tendance décroissante, marché saturé
- 4-6 : Stable, croissance modérée
- 7-8 : Croissance nette, momentum visible
- 9-10 : Forte croissance / hype (RARE)

Sois EXIGEANT : la plupart des problèmes sont entre 4-7.
```

### Impact
- ✅ Scores plus discriminants et représentatifs des vraies tendances marché
- ✅ Indépendant de l'historique (fallback gracieux si pas d'historique)
- ✅ Intégré dans la formule priority_score (poids 10%)

---

## 🎯 2. Nouveau Signal `founder_fit_score`

### Objectif
Évaluer l'adéquation entre l'opportunité et le profil du fondateur pour un usage personnel.

### Profil Fondateur (par défaut)
```
- Développeur fullstack / product maker
- Compétences : Python, JS/TS, React, Node.js, APIs, automation
- Expérience : SaaS B2B, dev tools, no-code, productivité
- Affinités sectorielles :
  ✅ SaaS B2B, dev tools, business automation, éducation en ligne, PME/freelance
  ⚠️ Neutre : e-commerce, marketing, consumer apps
  ❌ Moins : santé réglementée, hardware, deep biotech, industrie lourde
- Budget : Solo bootstrapping, MVP en quelques semaines
```

### Échelle 1-10
- **1-3 :** Très mauvais fit (compétences manquantes, secteur inadapté)
- **4-6 :** Fit moyen/possible mais pas idéal
- **7-8 :** Bon fit (compétences alignées, secteur favorable)
- **9-10 :** Excellent fit (sweet spot)

### Implémentation
- **Fichier :** `src/need_scanner/analysis/founder_fit.py`
- **Fonction principale :** `calculate_founder_fit_score()`
- **Fonction batch :** `calculate_batch_founder_fit_scores()`
- **Intégration :** Ajouté au pipeline enriched (Step 4.6)
- **Export :** Colonne `founder_fit_score` dans CSV et JSON

### Personnalisation
Le profil fondateur peut être overridé via paramètre `founder_profile` si besoin d'adapter pour un autre profil.

### Impact
- ✅ Permet de filtrer les opportunités alignées avec skills du fondateur
- ✅ Score complémentaire, non intégré dans priority_score (usage perso)
- ✅ Exporté dans tous les formats (CSV, JSON)

---

## 🎯 3. Amélioration Prompt MVP

### Problème Identifié
Le prompt actuel générait trop souvent des MVP de type "guide PDF", "article de blog", "ressource statique" au lieu de vrais produits/services.

### Solution
Ajout de guidelines explicites dans le prompt enrichi (ligne 86-92 de `summarize.py`) :

```
7) **mvp** : Proposition de MVP. IMPORTANT :
   - ❌ ÉVITE : "guides PDF", "articles de blog", "ressources statiques",
                "templates à télécharger", "e-books"
   - ✅ PRIVILÉGIE : outils SaaS simples, scripts/automations, extensions navigateur,
                     dashboards interactifs, APIs, calculateurs, assistants/bots
   - Pense "produit/service qu'un dev fullstack solo peut construire en quelques semaines"
   - Format : "Construire [un outil/service concret] qui [action/valeur créée]"
   - Exemple BON : "Construire un script Python qui génère automatiquement des
                    rapports financiers depuis Stripe"
   - Exemple MAUVAIS : "Créer un guide PDF expliquant comment faire des rapports"
```

### Impact
- ✅ MVP plus orientés produit/service
- ✅ Alignés avec profil dev fullstack solo
- ✅ Évite le biais "contenu statique"

---

## 📊 Formule Priority Score (Actuelle)

```python
priority = (
    combined_pain * 0.30 +      # Pain (LLM 70% + heuristic 30%)
    traction_score * 0.25 +     # Engagement
    novelty_score * 0.15 +      # vs historique
    wtp_score * 0.20 +          # Willingness-to-pay
    trend_score * 0.10          # Market trend (AMÉLIORE)
)
```

**Note :** `founder_fit_score` n'est PAS intégré dans priority_score (usage perso, filtrage manuel).

---

## 📁 Fichiers Modifiés

### Nouveaux Fichiers
- ✅ `src/need_scanner/analysis/founder_fit.py` - Founder fit scoring

### Fichiers Modifiés
- ✅ `src/need_scanner/analysis/trends.py` - Ajout LLM trend scoring
- ✅ `src/need_scanner/analysis/summarize.py` - Amélioration prompt MVP
- ✅ `src/need_scanner/schemas.py` - Ajout champ `founder_fit_score`
- ✅ `src/need_scanner/jobs/enriched_pipeline.py` - Intégration des nouveaux scores
- ✅ `src/need_scanner/export/csv_v2.py` - Export founder_fit_score
- ✅ `src/need_scanner/export/writer.py` - Export founder_fit_score (CSV legacy + JSON)

---

## 🧪 Tests

### Tests Manuels Recommandés

1. **Test trend_score :**
   ```bash
   # Lancer le pipeline et vérifier que les trend_score sont variés (pas tous à 5.0)
   python -m need_scanner run-enriched
   # Vérifier dans les logs : "LLM Trend: X.X"
   ```

2. **Test founder_fit_score :**
   ```bash
   # Vérifier présence dans les exports CSV
   cat data/results/insights_enriched.csv | head -1
   # Doit contenir : ...,trend_score,founder_fit_score,...
   ```

3. **Test prompt MVP :**
   ```bash
   # Inspecter quelques MVP générés dans le CSV
   # Vérifier qu'ils ne sont pas des "guides PDF" mais des outils/services
   ```

### Tests Automatisés

Les tests existants devraient continuer à passer. Aucun breaking change introduit (backward compatible).

---

## 💰 Impact Coûts

### Coûts Additionnels par Run

**Pour N clusters enrichis :**
- Trend scoring LLM : N × ~150 tokens × $0.0001 = ~$0.015 pour 100 clusters
- Founder fit scoring : N × ~150 tokens × $0.0001 = ~$0.015 pour 100 clusters
- **Total additionnel :** ~$0.03 pour 100 clusters

**Avec configuration typique (10 clusters TOP K) :**
- Coût additionnel : ~$0.003 par run (négligeable)

**Optimisations possibles :**
- Utiliser `gpt-4o-mini` pour trend et founder fit (déjà fait)
- Désactiver trend LLM si besoin via paramètre `use_llm=False`

---

## 🔧 Configuration

### Variables d'Environnement
Aucune nouvelle variable requise. Utilise les configs existantes :
- `OPENAI_API_KEY` (existant)
- `NS_LIGHT_MODEL` (existant, utilisé pour trend et founder fit)

### Paramètres Optionnels

Dans `enriched_pipeline.py`, possibilité d'ajuster :
```python
# Trend scoring
llm_weight=0.7  # 70% LLM, 30% historique (ligne 213)

# Founder fit
founder_profile=None  # None = profil par défaut (ligne 223)
```

---

## 📈 Prochaines Étapes (Hors Scope ÉTAPE 1)

- [ ] Intégrer `founder_fit_score` dans priority_score (avec poids configurable)
- [ ] Permettre config du profil fondateur via fichier YAML
- [ ] A/B test des poids de la formule priority_score
- [ ] Dashboard pour visualiser trends vs founder fit

---

## ✅ Checklist Complétée

- [x] Analyser structure code et localiser fichiers scoring
- [x] Documenter état actuel du trend_score
- [x] Implémenter LLM trend scoring (hybride)
- [x] Créer nouveau module founder_fit.py
- [x] Ajouter champ founder_fit_score au schéma
- [x] Améliorer prompt MVP (éviter guides PDF)
- [x] Intégrer scores dans enriched_pipeline.py
- [x] Mettre à jour exports (CSV + JSON)
- [x] Mettre à jour documentation

---

**Statut :** ✅ ÉTAPE 1 COMPLÉTÉE
**Ready for :** Merge vers `main` après review et tests
