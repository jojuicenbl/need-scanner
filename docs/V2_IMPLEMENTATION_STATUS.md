# Need Scanner V2 - Implementation Status

## ✅ Completed (Phases 1-4)

### Infrastructure & Configuration
- [x] Config files (intent_patterns.txt, packs/)
- [x] 4 subreddit packs (smallbiz_fr, tech_dev, services_humans, europe_fr)
- [x] Dependencies updated (youtube-search-python, snscrape)
- [x] Config loaders (packs & keywords)

### New Fetchers
- [x] IndieHackers (RSS)
- [x] Nitter (Twitter via RSS, multi-instance failover)
- [x] YouTube Search (metadata without API)
- [x] GitHub Search (alternatives & open-source)
- [x] Reddit enhanced (hot/new modes, keyword filtering)

### Advanced Analysis
- [x] Trends module (week-over-week growth)
- [x] Novelty module (embedding similarity + TF-IDF)
- [x] Priority scoring with configurable weights

### Processing & Export
- [x] Multi-week deduplication (rolling history)
- [x] Enhanced schemas (trend_score, keywords_matched)
- [x] Export with new columns

## 🔨 Remaining Work (Phase 5)

### CLI Enhancements

#### collect-all command
Add the following flags to `src/need_scanner/cli.py::collect_all()`:

```python
--pack NAME                         # Load pack from config/packs/NAME.txt
--reddit-mode [new|hot]             # Reddit fetch mode (default: new)
--include-keywords-file PATH        # Load intent keywords for filtering
--history-days INT                  # Days of history for deduplication
```

**Implementation:**
1. Import `load_subreddit_pack`, `load_intent_keywords` from config.py
2. Add parameters to function signature
3. If `--pack` provided, load subreddits from pack instead of single subreddit
4. Load keywords if `--include-keywords-file` specified
5. Pass `mode` and `include_keywords` to Reddit fetcher
6. Pass `history_path` and `history_days` to dedupe() call

#### run command
Add scoring weight parameters:

```python
--novelty-weight FLOAT              # Weight for novelty score (default: 0.15)
--trend-weight FLOAT                # Weight for trend score (default: 0.10)
--priority-weights STR              # "pain=0.3,traction=0.25,novelty=0.15,wtp=0.2,trend=0.1"
--history-path PATH                 # Path to trend/novelty history
```

**Implementation:**
1. Add parameters for weights
2. Parse `--priority-weights` string into dict
3. Call `calculate_cluster_trends()` and `calculate_cluster_novelty()`
4. Pass weights to `calculate_priority_score()`

### Automation

#### jobs/booster.py
Daily trend booster job:

```python
def run_daily_booster(
    output_dir: Path,
    hot_subreddits: List[str],
    nitter_queries: List[str],
    min_score: int = 5
) -> List[Post]:
    """
    Morning booster: fetch hot content from multiple sources.

    Sources:
    - Reddit hot posts (5-8 dynamic subs)
    - IndieHackers RSS
    - Nitter RSS (2-3 trending queries)

    Returns posts already filtered and ready for pipeline.
    """
    ...
```

#### .github/workflows/need_scanner_daily.yml
GitHub Actions workflow for daily automation:

```yaml
name: need-scanner-daily
on:
  schedule:
    - cron: "15 6 * * *" # 08:15 Paris time
  workflow_dispatch:

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt

      # Collect
      - run: |
          python -m need_scanner collect-all \
            --pack smallbiz_fr \
            --reddit-limit 240 \
            --reddit-mode hot \
            --hn-days 30 \
            --include-keywords-file config/intent_patterns.txt \
            --history-days 45

      # Prefilter
      - run: |
          python -m need_scanner prefilter \
            --filter-lang en,fr \
            --filter-intent \
            --keep-intents pain,request \
            --detect-wtp

      # Run pipeline
      - run: |
          python -m need_scanner run \
            --clusters 12 \
            --novelty-weight 0.15 \
            --trend-weight 0.15 \
            --output-dir data/daily_$(date +%Y%m%d)

      # (Optional) Slack notification
      # - run: python scripts/notify_slack.py data/daily_*/insights.csv
```

## 📝 Documentation Updates Needed

### README.md
Add section "What's New in V2":

- 4 new data sources (IndieHackers, Nitter, YouTube, GitHub)
- Subreddit packs for quick profiling
- Keyword-based filtering at collection time
- Trend analysis (week-over-week growth)
- Novelty detection (vs historical data)
- Multi-week deduplication
- Configurable priority weights

### docs/USER_GUIDE.md
Add recipes:

**Recipe 1: Maximum Freshness**
```bash
python -m need_scanner collect-all \
  --pack smallbiz_fr \
  --reddit-mode hot \
  --include-keywords-file config/intent_patterns.txt \
  --history-days 45

python -m need_scanner run \
  --novelty-weight 0.20 \
  --trend-weight 0.15
```

**Recipe 2: Niche Discovery**
```bash
# Focus on novelty, ignore trends
python -m need_scanner run \
  --priority-weights "pain=0.25,traction=0.20,novelty=0.30,wtp=0.15,trend=0.10"
```

**Recipe 3: Trending Topics**
```bash
# Maximize trend signal
python -m need_scanner collect-all \
  --pack tech_dev \
  --reddit-mode hot

python -m need_scanner run \
  --priority-weights "pain=0.20,traction=0.25,novelty=0.10,wtp=0.15,trend=0.30"
```

## 🧪 Testing Checklist

- [ ] Test pack loading (`--pack smallbiz_fr`)
- [ ] Test keyword filtering with config/intent_patterns.txt
- [ ] Test hot vs new modes on Reddit
- [ ] Test multi-week dedupe with history
- [ ] Test trend scoring (requires 2+ runs with history)
- [ ] Test novelty scoring (requires historical centroids)
- [ ] Test priority weights parsing
- [ ] Test new fetchers (IndieHackers, Nitter, YouTube, GitHub)
- [ ] Verify CSV export includes trend_score, keywords_matched
- [ ] End-to-end: collect → prefilter → run → export

## 📊 Acceptance Criteria

✅ All fetchers return ≥50 posts cumulatively
✅ `collect-all` accepts all new flags
✅ `run` calculates novelty + trend scores
✅ `insights_enriched.csv` has all new columns
✅ Multi-week deduplication reduces duplicates by ≥20% (with history)
✅ Booster generates valid posts
✅ Documentation is complete

## 🚀 Next Steps

1. Implement CLI enhancements (collect-all, run)
2. Create booster job
3. Test full pipeline with real data
4. Write documentation updates
5. (Optional) GitHub Actions workflow
