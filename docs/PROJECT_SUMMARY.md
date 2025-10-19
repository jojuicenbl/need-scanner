# need_scanner - Project Summary

## Implementation Status: COMPLETE ✓

All components of the need_scanner pipeline have been successfully implemented according to the specifications.

## What Was Built

### Core Features
1. **Reddit Data Collection**: Fetch posts from any subreddit with pagination and rate limiting
2. **Data Processing**: Clean, normalize, and deduplicate posts using fuzzy matching
3. **AI Analysis**:
   - Generate embeddings with OpenAI text-embedding-3-small
   - Cluster posts using KMeans
   - Summarize clusters with GPT-4o-mini (structured JSON output)
4. **Pain Scoring**: Dual scoring system (LLM + heuristic) to identify high-value opportunities
5. **Cost Controls**: Token estimation, automatic truncation, and budget warnings
6. **Export**: JSON and CSV formats for easy analysis

### Project Structure

```
need_scanner/
├── .env.example                   # Environment configuration template
├── .gitignore                     # Git ignore rules
├── requirements.txt               # Python dependencies
├── setup.py                       # Package installation
├── README.md                      # Full documentation
├── QUICKSTART.md                  # Quick start guide
├── PROJECT_SUMMARY.md             # This file
│
├── src/need_scanner/              # Main package
│   ├── __init__.py
│   ├── __main__.py                # Entry point for python -m
│   ├── cli.py                     # Typer CLI (collect, run, estimate)
│   ├── config.py                  # Config management + pricing
│   ├── schemas.py                 # Pydantic models
│   ├── utils.py                   # I/O, token estimation, cost calc
│   │
│   ├── fetchers/
│   │   └── reddit.py              # Reddit API integration
│   │
│   ├── processing/
│   │   ├── clean.py               # Text normalization
│   │   ├── dedupe.py              # Fuzzy + hash deduplication
│   │   ├── embed.py               # OpenAI embeddings
│   │   ├── index.py               # FAISS (optional, graceful fallback)
│   │   └── cluster.py             # KMeans clustering
│   │
│   ├── analysis/
│   │   ├── summarize.py           # LLM summarization + JSON parsing
│   │   └── scoring.py             # Pain score heuristics
│   │
│   └── export/
│       └── writer.py              # JSON/CSV export
│
└── tests/
    ├── __init__.py
    ├── mock_posts.json            # Sample data (10 posts)
    └── test_json_parsing.py       # JSON response parsing tests
```

### CLI Commands Implemented

1. **collect**: Fetch posts from Reddit
   ```bash
   python -m need_scanner collect --subreddit freelance --limit 200
   ```

2. **run**: Execute full pipeline
   ```bash
   python -m need_scanner run --input "data/raw/posts_*.json" --clusters 10
   ```

3. **estimate**: Cost estimation without API calls
   ```bash
   python -m need_scanner estimate --input "data/raw/posts_*.json"
   ```

## Key Specifications Met

### ✓ Configuration Management
- All settings via .env (OPENAI_API_KEY, model names, limits, costs)
- Centralized config with validation
- Missing API key error is clear and helpful

### ✓ Data Pipeline
- Reddit fetcher with pagination, retry logic, rate limiting
- Cleaning: whitespace normalization, text truncation
- Deduplication: hash-based + fuzzy matching (rapidfuzz ratio > 90)
- Embeddings: batched API calls with retry, cost tracking
- Clustering: KMeans with configurable clusters
- FAISS: Optional index building (graceful fallback if unavailable)

### ✓ LLM Integration
- Structured prompts (French, per specification)
- JSON parsing with markdown code block extraction
- Retry logic for malformed responses
- Cost estimation before calls
- Warning/skip if prompt exceeds cost threshold

### ✓ Scoring System
- LLM pain score (1-10)
- Heuristic score based on:
  - Average Reddit score
  - Number of comments
  - Pain keyword density
- Combined score: 60% LLM + 40% heuristic

### ✓ Cost Controls
- Token estimation (chars / 4)
- Automatic text truncation to fit budgets
- Per-prompt cost warnings
- Total cost tracking and reporting
- Pricing constants for all models

### ✓ Export & Results
- **cluster_results.json**: Full structured output with statistics
- **insights.csv**: Easy-to-read tabular format
- **embeddings.npy**: Reusable embeddings
- **meta.json**: Post metadata

### ✓ Testing
- Mock data (10 sample posts covering 3 themes)
- JSON parsing unit tests (5 test cases)
- Test can run without API calls for validation

## Acceptance Criteria Status

| Criterion | Status | Notes |
|-----------|--------|-------|
| Collect ≥50 posts from Reddit | ✓ | Configurable limit, tested with 200 |
| Clean + dedupe pipeline | ✓ | Removes duplicates, normalizes text |
| Generate embeddings.npy | ✓ | Saves to data/ directory |
| Create cluster_results.json | ✓ | ≥5 clusters with all fields |
| Generate insights.csv | ✓ | ≥5 rows, readable format |
| Each cluster has required fields | ✓ | title, description, monetizable, mvp, pain_score_llm |
| Cost estimation before/after | ✓ | Logs estimate and actual cost |
| Warning if prompt > threshold | ✓ | Logs WARNING, truncates or skips |
| FAISS optional | ✓ | Graceful fallback, no crash |
| No silent cost overruns | ✓ | All costs logged and warned |

## Configuration Reference

### Default Values (.env.example)
```
OPENAI_API_KEY=                           # Required
NS_DEFAULT_SUBREDDIT=freelance            # Default subreddit
NS_FETCH_LIMIT=200                        # Posts per fetch
NS_SLEEP_BETWEEN=1.0                      # Seconds between requests
NS_EMBED_MODEL=text-embedding-3-small     # Embedding model
NS_SUMMARY_MODEL=gpt-4o-mini              # Summary model
NS_NUM_CLUSTERS=10                        # Number of clusters
NS_MAX_DOCS_PER_CLUSTER=6                 # Examples per summary
NS_MAX_INPUT_TOKENS_PER_PROMPT=1200       # Max input tokens
NS_MAX_OUTPUT_TOKENS=400                  # Max output tokens
NS_COST_WARN_PROMPT_USD=0.50              # Cost warning threshold
```

### Model Pricing (config.py)
- text-embedding-3-small: $0.00002 / 1K tokens
- gpt-4o-mini: $0.00015 / 1K input, $0.0006 / 1K output

## Example Output

### insights.csv
```
cluster_id,size,title,monetizable,pain_score_final,mvp
0,15,Automatisation facturation,true,8,Template facture auto-remplissage PDF
1,8,Time tracking simple,true,7,Timer app avec intégration facture
2,12,Gestion contrats freelance,false,5,Bibliothèque templates gratuits
```

### Cost Example (200 posts, 10 clusters)
- Embeddings: ~$0.002
- Summaries: ~$0.045
- **Total: ~$0.047**

## Dependencies

### Required
- openai >= 1.0.0
- pydantic >= 2.0.0
- pydantic-settings >= 2.0.0
- python-dotenv >= 1.0.0
- typer >= 0.9.0
- loguru >= 0.7.0
- numpy >= 1.24.0
- scikit-learn >= 1.3.0
- rapidfuzz >= 3.0.0
- requests >= 2.31.0
- pandas >= 2.0.0

### Optional
- faiss-cpu >= 1.7.4 (for indexing)
- streamlit >= 1.28.0 (for dashboard)

## Getting Started

1. **Install**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure**:
   ```bash
   cp .env.example .env
   # Add your OPENAI_API_KEY to .env
   ```

3. **Test**:
   ```bash
   python tests/test_json_parsing.py
   ```

4. **Run with Mock Data**:
   ```bash
   python -m need_scanner run --input tests/mock_posts.json --clusters 3
   ```

5. **Fetch Real Data**:
   ```bash
   python -m need_scanner collect --subreddit freelance --limit 50
   python -m need_scanner run --input "data/raw/posts_*.json" --clusters 5
   ```

## Next Steps (Roadmap)

The current implementation is production-ready for the core use case. Potential enhancements:

1. **Additional Sources**:
   - ProductHunt fetcher
   - X/Twitter fetcher
   - HackerNews fetcher

2. **Advanced Analytics**:
   - HDBSCAN for dynamic cluster count
   - UMAP for dimensionality reduction
   - Trend detection over time

3. **User Interface**:
   - Streamlit dashboard
   - Interactive filters
   - Visualization of clusters

4. **Automation**:
   - Scheduled cron jobs
   - Email/Slack notifications
   - Automatic reporting

5. **Optimization**:
   - Cache LLM responses by content hash
   - Batch mode for large datasets
   - Resume from checkpoint

## Notes

- **Security**: .env is gitignored, never commit secrets
- **Costs**: Monitor via OpenAI dashboard, set usage limits
- **Rate Limits**: Reddit allows ~60 req/min, adjust NS_SLEEP_BETWEEN if needed
- **FAISS**: Optional but recommended for >1000 posts
- **Python**: Requires 3.10+ for modern Pydantic features

## Contact & Support

For issues or questions:
1. Check README.md and QUICKSTART.md
2. Review error logs in console output
3. Verify .env configuration
4. Check OpenAI API key and billing status

---

**Status**: Production Ready ✓
**Version**: 0.1.0
**Last Updated**: 2025-10-15
