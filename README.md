# need_scanner

A robust pipeline for collecting user posts from Reddit, analyzing them with AI to detect monetizable pain points, and generating actionable insights with controlled costs.

## Features

- **Multi-source collection**: Fetch posts from Reddit (v1), with extensibility for ProductHunt, X, etc.
- **Smart processing**: Cleaning, deduplication (fuzzy + hash), and normalization
- **AI-powered analysis**:
  - Text embeddings (OpenAI `text-embedding-3-small`)
  - Clustering (KMeans)
  - LLM summarization (GPT-4o-mini) with structured JSON output
  - Dual pain scoring (LLM + heuristic)
- **Cost controls**:
  - Token estimation before API calls
  - Automatic text truncation
  - Cost warnings and budget enforcement
  - Estimated monthly budget: $18 (configurable)
- **Export formats**: JSON and CSV for easy analysis
- **Optional FAISS**: Graceful fallback if FAISS not installed

## Installation

```bash
# Clone the repository
git clone <your-repo>
cd need_scanner

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install FAISS for indexing
pip install faiss-cpu
```

## Configuration

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and add your OpenAI API key:

```env
OPENAI_API_KEY=sk-...
NS_DEFAULT_SUBREDDIT=freelance
NS_FETCH_LIMIT=200
NS_SLEEP_BETWEEN=1.0
NS_EMBED_MODEL=text-embedding-3-small
NS_SUMMARY_MODEL=gpt-4o-mini
NS_NUM_CLUSTERS=10
NS_MAX_DOCS_PER_CLUSTER=6
NS_MAX_INPUT_TOKENS_PER_PROMPT=1200
NS_MAX_OUTPUT_TOKENS=400
NS_COST_WARN_PROMPT_USD=0.50
```

3. Set your OpenAI budget limit in the [OpenAI dashboard](https://platform.openai.com/account/limits).

## Usage

### 1. Collect posts from Reddit

```bash
python -m need_scanner collect --subreddit freelance --limit 200 --sleep 1.0
```

This creates `data/raw/posts_freelance_<timestamp>.json`

### 2. Run the complete pipeline

```bash
python -m need_scanner run --input "data/raw/posts_*.json" --clusters 10
```

This will:
1. Load and clean posts
2. Deduplicate
3. Generate embeddings
4. Cluster into groups
5. Summarize each cluster with LLM
6. Compute pain scores
7. Export results

**Outputs:**
- `data/cluster_results.json` - Complete structured results
- `data/insights.csv` - Easy-to-read CSV (open in Excel/Sheets)
- `data/embeddings.npy` - Embedding vectors
- `data/meta.json` - Post metadata

### 3. Estimate costs before running

```bash
python -m need_scanner estimate --input "data/raw/posts_*.json" --clusters 10
```

This shows estimated costs without making any API calls.

## Output Format

### CSV (insights.csv)

| cluster_id | size | title | description | monetizable | pain_score_final | mvp | example_urls |
|------------|------|-------|-------------|-------------|------------------|-----|--------------|
| 0 | 15 | Facture automatique | Freelancers cherchent outil pour automatiser facturation... | true | 8 | Créer template facture simple avec génération PDF | reddit.com/... |

### JSON (cluster_results.json)

```json
{
  "statistics": {
    "total_posts": 200,
    "after_cleaning": 198,
    "after_dedup": 175,
    "num_clusters": 10,
    "embeddings_cost_usd": 0.0023,
    "summary_cost_usd": 0.0456,
    "total_cost_usd": 0.0479
  },
  "insights": [
    {
      "cluster_id": 0,
      "summary": {
        "title": "Automatisation facturation",
        "description": "Freelancers cherchent solutions pour automatiser la génération et envoi de factures...",
        "monetizable": true,
        "justification": "Problème récurrent avec volonté de payer pour solution",
        "mvp": "Template facture avec auto-remplissage et génération PDF",
        "pain_score_llm": 8,
        "size": 15
      },
      "pain_score_final": 8,
      "examples": [...]
    }
  ]
}
```

## Cost Management

The pipeline includes multiple cost controls:

1. **Token estimation**: Before API calls, estimates cost based on text length
2. **Automatic truncation**: Reduces text to fit within token budgets
3. **Per-prompt warnings**: Logs warning if a single LLM call exceeds threshold
4. **Skip expensive clusters**: Automatically skips clusters that would cost >2x threshold
5. **Total cost tracking**: Reports final costs after pipeline completion

**Typical costs** (with default settings):
- 200 posts, 10 clusters: ~$0.05
- 1000 posts, 20 clusters: ~$0.25

## Architecture

```
need_scanner/
├── src/need_scanner/
│   ├── config.py              # Environment config + pricing
│   ├── utils.py               # I/O, token estimation, cost calculation
│   ├── schemas.py             # Pydantic models
│   ├── fetchers/
│   │   └── reddit.py          # Reddit API wrapper
│   ├── processing/
│   │   ├── clean.py           # Text normalization
│   │   ├── dedupe.py          # Fuzzy + hash deduplication
│   │   ├── embed.py           # OpenAI embeddings
│   │   ├── index.py           # FAISS index (optional)
│   │   └── cluster.py         # KMeans clustering
│   ├── analysis/
│   │   ├── summarize.py       # LLM summarization
│   │   └── scoring.py         # Pain score heuristics
│   ├── export/
│   │   └── writer.py          # JSON/CSV export
│   └── cli.py                 # Typer CLI
└── data/                      # Outputs (gitignored)
```

## Development

### Running tests

```bash
# Run mock data test
python tests/test_json_parsing.py

# Test with mock posts
python -m need_scanner run --input tests/mock_posts.json --clusters 3
```

### Adding new sources

Create a new fetcher in `src/need_scanner/fetchers/`:

```python
# fetchers/producthunt.py
def fetch_producthunt(limit: int) -> List[Post]:
    # Implementation
    pass
```

## Troubleshooting

**Q: "OPENAI_API_KEY is required but not set"**
A: Create a `.env` file with your OpenAI API key (see Configuration section)

**Q: FAISS warnings**
A: FAISS is optional. The pipeline works without it. To install: `pip install faiss-cpu`

**Q: Rate limiting errors (429)**
A: Increase `NS_SLEEP_BETWEEN` in `.env` or wait a few minutes

**Q: High costs**
A: Reduce `NS_NUM_CLUSTERS`, `NS_MAX_DOCS_PER_CLUSTER`, or `NS_MAX_INPUT_TOKENS_PER_PROMPT`

## Roadmap

- [ ] Add ProductHunt fetcher
- [ ] Add X/Twitter fetcher (via snscrape)
- [ ] Streamlit dashboard
- [ ] HDBSCAN clustering option
- [ ] Weekly email digest
- [ ] Slack/Discord notifications

## License

MIT

## Contributing

Pull requests welcome! Please ensure:
- Code follows existing style
- Add tests for new features
- Update README if needed
