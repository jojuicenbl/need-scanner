# Testing Need Scanner V2

## Quick Start Testing Guide

### Prerequisites

1. Install new dependencies:
```bash
pip install youtube-search-python
```

2. Ensure you have OPENAI_API_KEY in your `.env` file

---

## Test 1: Verify Config Files (30 seconds)

Check that all config files are created:

```bash
# List packs
ls -la config/packs/

# View intent patterns
head -20 config/intent_patterns.txt
```

**Expected output:**
- 4 pack files: `smallbiz_fr.txt`, `tech_dev.txt`, `services_humans.txt`, `europe_fr.txt`
- 50+ intent patterns visible

---

## Test 2: Test Pack Loading (Quick)

Test a small pack with limited subreddits:

```bash
# Create a tiny test pack
cat > config/packs/test_tiny.txt << EOF
freelance
SaaS
Entrepreneur
EOF

# Collect from test pack (only 3 subreddits, 5 posts each = ~30 seconds)
python -m need_scanner collect-all \
  --pack test_tiny \
  --reddit-limit 5 \
  --reddit-mode hot \
  --output data/test_v2 \
  --filter-lang en,fr
```

**Expected output:**
```
MULTI-SOURCE COLLECTION (V2)
[1/3] Collecting from Reddit pack 'test_tiny' (3 subreddits)...
✓ Collected X posts from Reddit pack
```

---

## Test 3: Test Keyword Filtering (Quick)

```bash
# Collect with keyword filtering
python -m need_scanner collect-all \
  --pack test_tiny \
  --reddit-limit 5 \
  --reddit-mode hot \
  --include-keywords-file config/intent_patterns.txt \
  --output data/test_v2
```

**Expected output:**
```
Loaded 50+ intent keywords from config/intent_patterns.txt
Filtering by keywords: ['alternative to', 'too expensive', ...]
```

Check that fewer posts are collected (only those matching keywords).

---

## Test 4: Test Multi-Week Deduplication

```bash
# First run
python -m need_scanner collect-all \
  --pack test_tiny \
  --reddit-limit 5 \
  --history-days 30 \
  --output data/test_v2

# Second run (should find duplicates)
python -m need_scanner collect-all \
  --pack test_tiny \
  --reddit-limit 5 \
  --history-days 30 \
  --output data/test_v2
```

**Expected output (2nd run):**
```
Applying multi-week deduplication (history_days=30)...
Loaded X historical hashes (30 days)
Removed X duplicates (Y historical), kept Z unique posts
```

---

## Test 5: Test Full Pipeline with V2 Features

Use the existing collected Reddit data (780 posts from earlier run):

```bash
# Run pipeline with V2 features
python -m need_scanner run \
  --input-pattern "data/raw/posts_reddit_multi_*.json" \
  --clusters 8 \
  --novelty-weight 0.20 \
  --trend-weight 0.15 \
  --pain-weight 0.25 \
  --traction-weight 0.25 \
  --wtp-weight 0.15 \
  --history-path data/history \
  --output-dir data/test_v2_output
```

**Expected output:**
```
NEED SCANNER PIPELINE (V2)
Priority weights: pain=0.25, traction=0.25, novelty=0.2, wtp=0.15, trend=0.15
...
[5.5/7] Calculating trend & novelty scores...
Calculated trends & novelty for 8 clusters
...
Top 3 priorities:
  #1: [Title]
    Priority: 8.45 | Pain: 7 | Traction: 7.2 | Novelty: 8.1 | Trend: 6.5
...
Outputs:
  data/test_v2_output/insights_enriched.csv (V2 with all scores)
```

---

## Test 6: Verify V2 CSV Output

```bash
# Check CSV columns
head -1 data/test_v2_output/insights_enriched.csv
```

**Expected columns:**
```
rank,cluster_id,size,priority_score,title,problem,persona,jtbd,context,monetizable,mvp,alternatives,willingness_to_pay_signal,pain_score_llm,pain_score_final,heuristic_score,traction_score,novelty_score,trend_score,keywords_matched,source_mix,example_urls
```

Verify `novelty_score`, `trend_score`, and `keywords_matched` columns are present.

---

## Test 7: Test New Fetchers (Optional)

### Test IndieHackers
```bash
python -c "
from src.need_scanner.fetchers.indiehackers import fetch_indiehackers
posts = fetch_indiehackers(days=7)
print(f'Fetched {len(posts)} IndieHackers posts')
"
```

### Test GitHub Search
```bash
python -c "
from src.need_scanner.fetchers.github_search import fetch_github_alternatives
posts = fetch_github_alternatives(query='saas alternative', max_results=5)
print(f'Fetched {len(posts)} GitHub repos')
"
```

### Test YouTube Search
```bash
python -c "
from src.need_scanner.fetchers.youtube_search import fetch_youtube
posts = fetch_youtube(query='saas pain points', max_results=5, min_views=1000)
print(f'Fetched {len(posts)} YouTube videos')
"
```

---

## Test 8: Test Trend Booster Job

```bash
python -m need_scanner.jobs.booster
```

**Expected output:**
```
DAILY TREND BOOSTER
[1/3] Fetching Reddit hot posts from 8 subreddits...
✓ Collected X hot posts from Reddit (min_score=5)
[2/3] Fetching IndieHackers RSS...
✓ Collected Y posts from IndieHackers
[3/3] Fetching Nitter RSS for 3 trending queries...
✓ Collected Z tweets from Nitter
✓ Total booster posts: X+Y+Z
✓ Saved booster posts to: data/incoming/booster_TIMESTAMP.json
```

---

## Test 9: End-to-End V2 Workflow

Complete workflow with all V2 features:

```bash
# Step 1: Collect (with pack, keywords, history)
python -m need_scanner collect-all \
  --pack test_tiny \
  --reddit-limit 10 \
  --reddit-mode hot \
  --include-keywords-file config/intent_patterns.txt \
  --history-days 30 \
  --filter-lang en,fr \
  --filter-intent \
  --output data/e2e_test

# Step 2: Prefilter
python -m need_scanner prefilter \
  --input-pattern "data/e2e_test/posts_*.json" \
  --filter-lang en,fr \
  --keep-intents pain,request \
  --detect-wtp

# Step 3: Run pipeline with V2 features
python -m need_scanner run \
  --input-pattern "data/e2e_test/posts_*.json" \
  --clusters 6 \
  --novelty-weight 0.20 \
  --trend-weight 0.15 \
  --history-path data/history \
  --output-dir data/e2e_output

# Step 4: Verify output
ls -lh data/e2e_output/
cat data/e2e_output/insights_enriched.csv | head -3
```

---

## Troubleshooting

### Issue: "Pack not found"
**Solution:** Check pack name matches filename without `.txt`:
```bash
ls config/packs/  # See available packs
```

### Issue: "Keywords file not found"
**Solution:** Verify path:
```bash
ls -la config/intent_patterns.txt
```

### Issue: "No posts after keyword filtering"
**Solution:** Keywords might be too restrictive. Try without keywords first:
```bash
python -m need_scanner collect-all --pack test_tiny --reddit-limit 10
```

### Issue: Import errors for new modules
**Solution:** Reinstall in development mode:
```bash
pip install -e .
```

---

## Success Criteria

✅ All config files created
✅ Pack loading works
✅ Keyword filtering reduces post count
✅ Multi-week dedup finds duplicates on 2nd run
✅ Pipeline calculates novelty & trend scores
✅ `insights_enriched.csv` has all V2 columns
✅ Priority scores use custom weights
✅ New fetchers return posts
✅ Booster job completes successfully

---

## Next Steps

Once all tests pass:

1. **Run on real data:**
   ```bash
   python -m need_scanner collect-all \
     --pack smallbiz_fr \
     --reddit-limit 50 \
     --reddit-mode hot \
     --include-keywords-file config/intent_patterns.txt \
     --history-days 45

   python -m need_scanner run \
     --novelty-weight 0.15 \
     --trend-weight 0.15
   ```

2. **Analyze results in `insights_enriched.csv`**

3. **Set up GitHub Actions** (if desired)

4. **Schedule booster job** via cron:
   ```bash
   crontab -e
   # Add: 15 6 * * * cd /path/to/need_scanner && python -m need_scanner.jobs.booster
   ```

---

For issues or questions, see:
- `docs/V2_IMPLEMENTATION_STATUS.md` - Implementation details
- `docs/WHATS_NEW_V2.md` - Feature documentation
