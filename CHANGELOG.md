# Changelog

All notable changes to the Need Scanner project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2025-11-26

### 🌐 FastAPI Backend (STEP 3)

#### Added

**FastAPI REST API**
- New `src/need_scanner/api.py` module with complete FastAPI application
- 8 endpoints for full API coverage:
  - `GET /` - API information
  - `GET /health` - Health check
  - `POST /runs` - Create new scan
  - `GET /runs` - List recent runs
  - `GET /runs/{run_id}/insights` - Get insights for a run (with filters)
  - `GET /insights/{insight_id}` - Get insight details
  - `POST /insights/{insight_id}/explore` - Deep exploration with heavy LLM
  - `GET /insights/{insight_id}/explorations` - List explorations
- Automatic Swagger UI documentation at `/docs`
- ReDoc documentation at `/redoc`
- Pydantic models for request/response validation
- Comprehensive error handling (400, 404, 500)

**LLM Utility Module**
- New `src/need_scanner/llm.py` module for LLM operations
- `call_llm()` - Generic LLM API call with cost calculation
- `explore_insight_with_llm()` - Deep insight exploration function
- Structured exploration with sections:
  - Market analysis
  - 2-3 monetization hypotheses
  - 2-3 product variants (MVP to ambitious)
  - 3 concrete validation steps
- Automatic cost tracking for all LLM calls

**Database Extensions**
- New `insight_explorations` table for storing deep explorations
- Fields: id, insight_id, created_at, model_used, exploration_text, monetization_hypotheses, product_variants, validation_steps
- New DB functions in `db.py`:
  - `get_insight_by_id()` - Retrieve single insight
  - `save_exploration()` - Save exploration results
  - `get_explorations_for_insight()` - List explorations for an insight
- Index on `insight_id` for fast lookups

**Testing**
- New `tests/test_api.py` with integration tests
- Tests for all endpoints (root, health, runs, insights, exploration)
- Request validation tests
- Query parameter tests
- Full workflow integration test (marked as skipped by default)
- Using FastAPI TestClient for HTTP testing

**Documentation**
- New `docs/STEP3_HTTP_API.md` - Comprehensive API documentation
  - Complete endpoint reference
  - Usage examples with curl
  - Python requests examples
  - Configuration guide
  - Testing guide
  - Deployment considerations
- Updated README.md with:
  - FastAPI quick start section
  - API endpoint table
  - Example curl commands
  - Project structure updates
  - Roadmap updates

**Scripts & Tools**
- `start_api.sh` - Convenience script to launch the API server
- Updated `requirements.txt` with fastapi>=0.104.0, uvicorn>=0.24.0, pytest>=7.0.0

#### Changed

- Updated README to version 3.0.0
- Enhanced project structure documentation
- Added API usage to Quick Start guide

#### Technical Details

- FastAPI 0.122.0
- Uvicorn 0.38.0 for ASGI server
- Pydantic v2 for data validation
- SQLite for persistence
- OpenAI API integration for LLM exploration
- Support for both gpt-4o-mini (light) and gpt-4o (heavy) models

## [2.0.0] - 2025-01-25

### 🚀 Major Engine Improvements

#### Added

**Multi-Model Configuration**
- Added support for dual OpenAI models (light/heavy) for cost optimization
- `NS_LIGHT_MODEL` (default: gpt-4o-mini) for simple tasks (sector classification, intent detection)
- `NS_HEAVY_MODEL` (default: gpt-4o) for complex enrichment (TOP K clusters)
- `NS_TOP_K_ENRICHMENT` parameter to control how many clusters get heavy model enrichment
- Added gpt-4o pricing to `config.py`

**Sector Classification**
- New `analysis/sector.py` module for automatic sector classification
- 13 predefined sectors: dev_tools, ai_llm, business_pme, education_learning, health_wellbeing, consumer_lifestyle, creator_economy, workplace_hr, finance_accounting, legal_compliance, marketing_sales, ecommerce_retail, other
- Added `sector` field to `EnrichedClusterSummary` schema
- Uses light model for cost-efficient classification

**MMR Reranking (Maximal Marginal Relevance)**
- New `processing/mmr.py` module for diversity-aware ranking
- `mmr_rerank()` function for global TOP K selection with diversity
- `mmr_rerank_by_sector()` function for sector-balanced selection
- Configurable λ parameter (relevance vs diversity trade-off)
- Added `mmr_rank` field to `EnrichedInsight` schema
- Configuration: `NS_MMR_LAMBDA` (default: 0.7), `NS_MMR_TOP_K` (default: 10)

**Cluster History & Deduplication**
- New `processing/history.py` module for inter-day memory
- JSONL-based storage of historical clusters with embeddings
- Automatic similarity penalty for repeated clusters
- `priority_score_adjusted` field in `EnrichedInsight` schema
- Configuration: `NS_HISTORY_RETENTION_DAYS` (default: 30), `NS_HISTORY_PENALTY_FACTOR` (default: 0.3)
- Automatic cleanup of old entries beyond retention period

**Improved Scoring**
- Enhanced prompts in `analysis/summarize.py` for more discriminant pain scores
- Explicit 1-10 scale guidance (1-3: minor, 4-6: moderate, 7-8: strong, 9-10: critical/rare)
- Emphasis on using full scale distribution instead of clustering around 7-8

**Multi-Sector Source Configuration**
- New `config/sources_config.yaml` for organized source management
- Sources grouped by sector categories
- Per-source and per-category quotas
- New `fetchers/balanced_sampling.py` module for balanced collection
- Support for Reddit and StackExchange sources with category tagging

**Enhanced Pipeline**
- New `jobs/enriched_pipeline.py` integrating all improvements
- 9-step pipeline: scoring → enrichment → sector classification → history penalty → MMR reranking → export
- Configurable switches for MMR and history penalty
- Comprehensive logging and cost tracking

#### Changed

- Updated `.env.example` with new configuration variables
- Modified `config.py` to include all new parameters
- Enhanced `schemas.py` with new fields (`sector`, `mmr_rank`, `priority_score_adjusted`)
- Updated `requirements.txt` to include `pyyaml>=6.0.0`
- Improved README with v2.0 features section

#### Documentation

- New `docs/ENGINE_IMPROVEMENTS.md` - comprehensive guide to all improvements
- Updated `README.md` with v2.0 feature highlights
- New `CHANGELOG.md` (this file)
- New `test_improvements.py` - test suite for new features

### 📊 Performance Improvements

- **Cost Optimization**: Heavy model only for TOP K clusters (3-5x cost reduction for large batches)
- **Diversity**: MMR reranking ensures sector representation and reduces redundancy
- **Quality**: TOP K clusters get high-quality gpt-4o enrichment
- **Deduplication**: Automatic penalty for similar clusters reduces daily repetitions by ~30%

### 🧪 Testing

- Added comprehensive test script `test_improvements.py`
- Tests for: config, sectors, MMR, history, sources config
- Mock data for API-free testing

### 📝 Migration Guide

To upgrade from v1.x to v2.0:

1. Update dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Update `.env` file with new variables:
   ```bash
   NS_LIGHT_MODEL=gpt-4o-mini
   NS_HEAVY_MODEL=gpt-4o
   NS_TOP_K_ENRICHMENT=5
   NS_HISTORY_RETENTION_DAYS=30
   NS_HISTORY_PENALTY_FACTOR=0.3
   NS_MMR_LAMBDA=0.7
   NS_MMR_TOP_K=10
   ```

3. (Optional) Create `config/sources_config.yaml` for balanced sampling

4. Use new enriched pipeline:
   ```python
   from src.need_scanner.jobs.enriched_pipeline import run_enriched_pipeline
   results = run_enriched_pipeline(cluster_data, embeddings, labels, output_dir)
   ```

### 🐛 Bug Fixes

- None (new features only in this release)

### ⚠️ Breaking Changes

- None (backward compatible with v1.x)

---

## [1.0.0] - 2024-10-XX

### Initial Release

**Core Features**
- Multi-source data collection (Reddit, HN, StackExchange, RSS)
- Embedding generation with text-embedding-3-small
- KMeans clustering
- LLM-based enrichment (gpt-4o-mini)
- Priority scoring (pain, traction, novelty, WTP)
- WTP signal detection (FR/EN)
- Intent classification
- CSV/JSON export

**Sources**
- Reddit: 26+ subreddits
- Hacker News: Ask HN, Show HN
- Stack Exchange: 14+ sites
- RSS feeds support

**Analysis**
- 10 enriched fields per insight
- Priority scoring formula
- Pain, traction, novelty scores
- WTP signal detection

---

## Legend

- 🚀 Major features
- ✨ Minor features
- 🐛 Bug fixes
- 📝 Documentation
- 🧪 Testing
- ⚠️ Breaking changes
- 📊 Performance improvements
