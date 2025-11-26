# ÉTAPE 3 : Backend HTTP avec FastAPI

## 🎯 Objectif

Fournir une API REST complète autour de Need Scanner pour permettre :
- Le lancement de scans via HTTP
- La consultation des runs et insights
- L'exploration approfondie d'insights avec des LLMs puissants

## 📋 Fonctionnalités Implémentées

### 1. API REST FastAPI

**Fichier principal** : `src/need_scanner/api.py`

#### Endpoints disponibles :

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/` | Informations de l'API |
| GET | `/health` | Health check |
| POST | `/runs` | Créer un nouveau scan |
| GET | `/runs` | Lister les runs récents |
| GET | `/runs/{run_id}/insights` | Insights d'un run |
| GET | `/insights/{insight_id}` | Détails d'un insight |
| POST | `/insights/{insight_id}/explore` | Explorer un insight en profondeur |
| GET | `/insights/{insight_id}/explorations` | Historique des explorations |

### 2. Module LLM

**Fichier** : `src/need_scanner/llm.py`

Utilitaires pour :
- Sélection automatique modèle light/heavy
- Appels API OpenAI standardisés
- Calcul des coûts
- Exploration approfondie d'insights

**Fonctions principales** :
- `call_llm()` : Appel générique à l'API OpenAI
- `explore_insight_with_llm()` : Exploration détaillée d'un insight

### 3. Base de Données Étendue

**Nouvelle table** : `insight_explorations`

```sql
CREATE TABLE insight_explorations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insight_id TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    model_used TEXT,
    exploration_text TEXT NOT NULL,
    monetization_hypotheses TEXT,
    product_variants TEXT,
    validation_steps TEXT,
    FOREIGN KEY (insight_id) REFERENCES insights(id)
)
```

**Nouvelles fonctions DB** (`db.py`) :
- `get_insight_by_id()` : Récupérer un insight par ID
- `save_exploration()` : Sauvegarder une exploration
- `get_explorations_for_insight()` : Lister les explorations d'un insight

## 🚀 Utilisation

### Lancer le serveur

```bash
# Development mode (avec reload automatique)
uvicorn need_scanner.api:app --reload

# Production mode
uvicorn need_scanner.api:app --host 0.0.0.0 --port 8000 --workers 4
```

### Accéder à la documentation

- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc

### Exemples d'utilisation

#### 1. Créer un nouveau scan

```bash
curl -X POST "http://localhost:8000/runs" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "deep",
    "max_insights": 20
  }'
```

**Réponse** :
```json
{
  "run_id": "20251126_143022",
  "status": "completed",
  "message": "Scan completed successfully. Run ID: 20251126_143022"
}
```

#### 2. Lister les runs

```bash
curl "http://localhost:8000/runs?limit=5"
```

**Réponse** :
```json
[
  {
    "id": "20251126_143022",
    "created_at": "2025-11-26 14:30:22",
    "config_name": "default",
    "mode": "deep",
    "nb_insights": 18,
    "nb_clusters": 25,
    "total_cost_usd": 0.0456
  }
]
```

#### 3. Voir les insights d'un run

```bash
# Sans filtres
curl "http://localhost:8000/runs/20251126_143022/insights"

# Avec filtres
curl "http://localhost:8000/runs/20251126_143022/insights?sector=dev_tools&min_priority=6.0&limit=10"
```

**Réponse** :
```json
[
  {
    "id": "20251126_143022_cluster_1",
    "run_id": "20251126_143022",
    "rank": 1,
    "sector": "dev_tools",
    "title": "Better deployment tools for solo developers",
    "problem": "Solo developers struggle with complex deployment pipelines...",
    "priority_score": 7.85,
    "pain_score_final": 8.5,
    "trend_score": 7.2,
    "founder_fit_score": 8.0
  }
]
```

#### 4. Voir le détail d'un insight

```bash
curl "http://localhost:8000/insights/20251126_143022_cluster_1"
```

**Réponse** : Tous les champs de l'insight (persona, JTBD, MVP, alternatives, scores, etc.)

#### 5. Explorer un insight en profondeur

```bash
curl -X POST "http://localhost:8000/insights/20251126_143022_cluster_1/explore" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o"
  }'
```

**Réponse** :
```json
{
  "exploration_id": 1,
  "insight_id": "20251126_143022_cluster_1",
  "full_text": "# Deep Insight Exploration\n\n## Market Analysis...",
  "monetization_ideas": [
    "- **Strategy**: SaaS subscription with tiered pricing...",
    "- **Strategy**: Marketplace for deployment templates...",
    "- **Strategy**: Consulting + custom integrations..."
  ],
  "product_variants": [
    "1. **MVP Version**: Simple CLI tool...",
    "2. **Enhanced Version**: Web dashboard + integrations...",
    "3. **Ambitious Vision**: Full DevOps platform..."
  ],
  "validation_steps": [
    "1. Interview 20 solo developers about deployment pain points",
    "2. Create landing page and collect 100 email signups",
    "3. Build MVP and test with 10 beta users"
  ],
  "model_used": "gpt-4o",
  "cost_usd": 0.0234,
  "created_at": "2025-11-26T14:45:10"
}
```

#### 6. Voir l'historique des explorations

```bash
curl "http://localhost:8000/insights/20251126_143022_cluster_1/explorations"
```

**Réponse** :
```json
[
  {
    "id": 1,
    "insight_id": "20251126_143022_cluster_1",
    "model_used": "gpt-4o",
    "created_at": "2025-11-26T14:45:10",
    "preview": "# Deep Insight Exploration\n\n## Market Analysis\n\nThe market for solo developer tools has seen significant growth..."
  }
]
```

## 🔧 Configuration

### Variables d'environnement

Les variables suivantes sont utilisées (via `.env`) :

```bash
# OpenAI API
OPENAI_API_KEY=your_api_key

# Models
OPENAI_MODEL_LIGHT=gpt-4o-mini      # For batch processing
OPENAI_MODEL_HEAVY=gpt-4o           # For deep exploration

# Database (optional)
NEEDSCANNER_DB_PATH=data/needscanner.db
```

### Modèles LLM

L'API utilise deux types de modèles :

1. **Light Model** (gpt-4o-mini)
   - Utilisé pour : scoring, enrichissement standard
   - Coût : ~$0.15-0.60 per 1M tokens
   - Plus rapide et moins cher

2. **Heavy Model** (gpt-4o)
   - Utilisé pour : exploration approfondie via `/explore`
   - Coût : ~$5-15 per 1M tokens
   - Meilleure qualité d'analyse

## 📊 Modèles Pydantic

L'API utilise Pydantic pour la validation des données :

### Request Models

- `ScanRequest` : Paramètres pour créer un scan
- `ExploreRequest` : Paramètres pour explorer un insight

### Response Models

- `ScanResponse` : Résultat de création de scan
- `RunSummary` : Résumé d'un run
- `InsightSummary` : Résumé d'un insight (pour listes)
- `InsightDetail` : Détails complets d'un insight
- `ExplorationResponse` : Résultat d'exploration
- `ExplorationSummary` : Résumé d'une exploration

## 🧪 Tests

### Test manuel avec curl

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Créer un scan (mode light pour test rapide)
curl -X POST "http://localhost:8000/runs" \
  -H "Content-Type: application/json" \
  -d '{"mode": "light", "max_insights": 5}'

# 3. Récupérer le run_id et consulter les résultats
RUN_ID="20251126_143022"
curl "http://localhost:8000/runs/${RUN_ID}/insights"

# 4. Explorer le premier insight
INSIGHT_ID="${RUN_ID}_cluster_1"
curl -X POST "http://localhost:8000/insights/${INSIGHT_ID}/explore" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Test avec Python requests

```python
import requests

BASE_URL = "http://localhost:8000"

# Créer un scan
response = requests.post(
    f"{BASE_URL}/runs",
    json={"mode": "deep", "max_insights": 10}
)
run_id = response.json()["run_id"]
print(f"Run ID: {run_id}")

# Lister les insights
insights = requests.get(
    f"{BASE_URL}/runs/{run_id}/insights"
).json()
print(f"Found {len(insights)} insights")

# Explorer le premier insight
if insights:
    insight_id = insights[0]["id"]
    exploration = requests.post(
        f"{BASE_URL}/insights/{insight_id}/explore",
        json={"model": "gpt-4o"}
    ).json()
    print(f"Exploration cost: ${exploration['cost_usd']:.4f}")
```

## 🎯 Prochaines Étapes

### Tests d'intégration

- [ ] Tests automatisés avec pytest + TestClient
- [ ] Mock des appels OpenAI pour tests unitaires
- [ ] Tests de charge avec locust

### Améliorations

- [ ] Background tasks pour scans longs (avec Celery ou Redis)
- [ ] Websockets pour suivi en temps réel
- [ ] Authentification (JWT tokens)
- [ ] Rate limiting
- [ ] Caching (Redis)
- [ ] Pagination avancée
- [ ] Filtres complexes (par date, sources, etc.)
- [ ] Export direct CSV/JSON via endpoints

### Déploiement

- [ ] Dockerfile
- [ ] Docker Compose (API + Redis + PostgreSQL)
- [ ] Configuration Nginx
- [ ] CI/CD avec GitHub Actions
- [ ] Déploiement sur cloud (AWS/GCP/Azure)

## 📝 Notes Techniques

### Gestion des Erreurs

L'API gère les erreurs de manière standardisée :

- `400 Bad Request` : Paramètres invalides
- `404 Not Found` : Ressource non trouvée
- `500 Internal Server Error` : Erreur serveur

Exemple de réponse d'erreur :
```json
{
  "detail": "Insight not found: invalid_id"
}
```

### Performance

- Les scans sont exécutés de manière synchrone pour l'instant
- Pour des scans longs, considérer l'utilisation de background tasks
- La base SQLite est suffisante pour usage local/petit scale
- Pour production, migrer vers PostgreSQL

### Sécurité

Points à améliorer pour production :
- Ajouter authentification (JWT, API keys)
- Limiter le débit (rate limiting)
- Valider tous les inputs
- Logs d'audit
- HTTPS obligatoire
- CORS configuré correctement

## 🔗 Liens Utiles

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [OpenAI API Documentation](https://platform.openai.com/docs)

---

**Made with ❤️ using Claude Code**
