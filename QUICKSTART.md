# Quick Start Guide

## 1. Setup (First time only)

```bash
# Install dependencies
pip install -r requirements.txt

# OR install in development mode
pip install -e .

# Create .env file
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:
```
OPENAI_API_KEY=sk-your-key-here
```

## 2. Test Installation

Run the JSON parsing test:
```bash
python tests/test_json_parsing.py
```

Expected output:
```
Running JSON parsing tests...

✓ Valid JSON parsing works
✓ Markdown code block parsing works
✓ Generic code block parsing works
✓ Invalid JSON handling works
✓ All required fields present

==================================================
All tests passed! ✓
==================================================
```

## 3. Run with Mock Data

Test the pipeline with mock data (won't make API calls for fetching, but will use OpenAI for embeddings and summaries):

```bash
python -m need_scanner run --input tests/mock_posts.json --clusters 3
```

This will:
- Process 10 mock posts
- Create 3 clusters
- Generate summaries
- Output results to `data/`

**Cost**: ~$0.01-0.02

## 4. Collect Real Data

Fetch posts from Reddit:

```bash
python -m need_scanner collect --subreddit freelance --limit 50
```

## 5. Run Full Pipeline

Process the collected posts:

```bash
python -m need_scanner run --input "data/raw/posts_*.json" --clusters 5
```

## 6. Estimate Costs First

Before running expensive operations:

```bash
python -m need_scanner estimate --input "data/raw/posts_*.json" --clusters 10
```

## Common Commands

### Collect from specific subreddit
```bash
python -m need_scanner collect --subreddit entrepreneur --limit 200
```

### Process with custom settings
```bash
python -m need_scanner run \
  --input "data/raw/posts_*.json" \
  --clusters 15 \
  --model-sum gpt-4o-mini \
  --max-examples 8
```

### View results
```bash
# Open CSV in default application (Mac)
open data/insights.csv

# View JSON
cat data/cluster_results.json | python -m json.tool | less
```

## Troubleshooting

### No module named 'need_scanner'
Solution:
```bash
# Make sure you're in the project directory
pip install -e .
```

### OPENAI_API_KEY error
Solution: Create `.env` file with your API key

### Rate limiting (429 error)
Solution: Increase sleep time in `.env`:
```
NS_SLEEP_BETWEEN=2.0
```

## Next Steps

1. Check `data/insights.csv` for monetizable opportunities
2. Filter by `pain_score_final >= 7` for highest-pain problems
3. Review `mvp` column for quick implementation ideas
4. Sort by `monetizable = true` to find revenue opportunities

## Cost Monitoring

Set a monthly budget limit in [OpenAI Dashboard](https://platform.openai.com/account/limits).

Typical costs:
- 50 posts, 5 clusters: ~$0.02
- 200 posts, 10 clusters: ~$0.05
- 1000 posts, 20 clusters: ~$0.25
