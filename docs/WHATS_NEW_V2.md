# 🚀 What's New in Need Scanner V2

Need Scanner V2 brings major enhancements to make your pain point discovery **fresher**, **more varied**, and **signal-rich**.

## 🎯 Key Improvements

### 1. 🔍 4 New Data Sources

Expand beyond Reddit & HN with:

| Source | What It Finds | Use Case |
|--------|---------------|----------|
| **IndieHackers** | Indie founder discussions & pain points | SaaS/bootstrapper needs |
| **Nitter** (Twitter/X) | Real-time trending complaints | Viral pain points, trending issues |
| **YouTube** | Video comments & descriptions | Visual/tutorial pain points |
| **GitHub** | Open-source alternatives being built | Competitive intelligence, gaps |

**Example:**
```bash
# Fetch from all sources
python -m need_scanner collect-all \
  --hn-days 30 \
  --rss-feeds-file config/rss_feeds.txt \
  --include-keywords-file config/intent_patterns.txt
```

### 2. 📦 Subreddit Packs

Pre-configured topic bundles for fast profiling:

| Pack | Focus | Subreddits |
|------|-------|------------|
| **smallbiz_fr** | French/EU small business | freelance, vosfinances, france, entrepreneur, ecommerce... |
| **tech_dev** | Developers & SaaS builders | webdev, SaaS, programming, buildinpublic... |
| **services_humans** | Service businesses | consulting, therapy, teachers, healthcare... |
| **europe_fr** | European/French communities | france, paris, eupersonalfinance, expats... |

**Example:**
```bash
python -m need_scanner collect-all --pack smallbiz_fr --reddit-limit 300
```

Create your own pack in `config/packs/my_pack.txt`!

### 3. 🎯 Intent Keyword Filtering

Filter posts **during collection** with 50+ pre-loaded patterns:

```txt
# config/intent_patterns.txt
alternative to
too expensive
pricing too high
problem with
je cherche un outil
export csv
no show
chargeback
RGPD
...
```

**Example:**
```bash
python -m need_scanner collect-all \
  --include-keywords-file config/intent_patterns.txt
```

Only posts containing these keywords are collected → saves API costs & processing time.

### 4. 📈 Trend Analysis (Week-over-Week)

Detect **emerging** topics with trend scores:

- Compares current cluster sizes vs. historical data
- Sigmoid-normalized growth rates
- Identifies "hot" pain points gaining momentum

**Example:**
```bash
python -m need_scanner run \
  --trend-weight 0.15 \
  --history-path data/history/trends.json
```

**CSV Output:**
```
rank,cluster_id,trend_score,novelty_score,priority_score,...
1,5,9.2,7.1,8.45,"Stripe fees eating profit margins"
2,3,8.7,8.9,8.32,"GDPR compliance nightmare"
```

### 5. ✨ Novelty Detection

Spot **new** vs. **recurring** pain points:

- **Embedding-based similarity** vs. historical centroids
- **TF-IDF term rarity** for unique vocabulary
- High novelty = fresh, underexplored needs

**Example:**
```bash
python -m need_scanner run \
  --novelty-weight 0.20 \
  --history-path data/history/novelty.json
```

**Use Cases:**
- Find blue ocean opportunities (high novelty)
- Avoid crowded spaces (low novelty)

### 6. 🧹 Multi-Week Deduplication

Eliminate repeating posts across multiple runs:

```bash
python -m need_scanner collect-all \
  --history-days 45  # Dedupe against last 45 days
```

- Maintains rolling window of seen posts
- Reduces noise from recurring content
- Focuses on **new signals only**

### 7. ⚖️ Configurable Priority Weights

Customize what matters **most** to you:

```bash
# Default formula:
# 30% Pain + 25% Traction + 15% Novelty + 20% WTP + 10% Trend

# Recipe 1: Maximize freshness (trending + novel)
python -m need_scanner run \
  --priority-weights "pain=0.20,traction=0.20,novelty=0.25,wtp=0.15,trend=0.20"

# Recipe 2: Proven demand (high traction + WTP)
python -m need_scanner run \
  --priority-weights "pain=0.25,traction=0.35,novelty=0.05,wtp=0.30,trend=0.05"

# Recipe 3: Blue ocean (high novelty, ignore trends)
python -m need_scanner run \
  --novelty-weight 0.30 \
  --trend-weight 0.05
```

### 8. 🌐 Hot vs. New Modes

Choose Reddit sorting:

```bash
# Trending topics (hot posts)
python -m need_scanner collect-all \
  --pack tech_dev \
  --reddit-mode hot

# Latest discussions (new posts)
python -m need_scanner collect-all \
  --pack tech_dev \
  --reddit-mode new
```

**Hot mode** = viral pain points, proven engagement
**New mode** = early signals, less filtered

## 📊 Enhanced Output

**insights_enriched.csv** now includes:

| New Column | What It Means |
|------------|---------------|
| `trend_score` | 0-10 score for week-over-week growth |
| `novelty_score` | 0-10 score for uniqueness vs. history |
| `keywords_matched` | Intent keywords that triggered collection |
| `source_mix` | List of sources in cluster (reddit,hn,rss,x...) |

## 🎯 Complete Workflow Example

```bash
# 1. Collect (with all V2 features)
python -m need_scanner collect-all \
  --pack smallbiz_fr \
  --reddit-limit 240 \
  --reddit-mode hot \
  --hn-days 30 \
  --rss-days 30 \
  --include-keywords-file config/intent_patterns.txt \
  --history-days 45 \
  --filter-lang en,fr \
  --filter-intent

# 2. Prefilter (focus on high-intent)
python -m need_scanner prefilter \
  --filter-lang en,fr \
  --keep-intents pain,request \
  --detect-wtp

# 3. Run pipeline (with novelty + trend)
python -m need_scanner run \
  --clusters 12 \
  --novelty-weight 0.15 \
  --trend-weight 0.15 \
  --history-path data/history \
  --output-dir data/output

# 4. Explore results
cat data/output/insights_enriched.csv
```

## 🏆 Results

**Before V2:**
- 780 Reddit posts from 1 subreddit
- Basic clustering
- No history, no trends

**After V2:**
- 780+ posts from **30+ subreddits** + HN + RSS + Nitter
- **Keyword-filtered** for high intent
- **Deduplicated** against 45 days of history
- **Trend** & **novelty** scores
- **Configurable** priority formula

## 🛠️ Migration Guide

### Old Command
```bash
python -m need_scanner collect --subreddit freelance --limit 200
python -m need_scanner run
```

### New Command (V2)
```bash
python -m need_scanner collect-all \
  --pack smallbiz_fr \
  --reddit-mode hot \
  --include-keywords-file config/intent_patterns.txt

python -m need_scanner run \
  --novelty-weight 0.15 \
  --trend-weight 0.15
```

## 📚 Additional Resources

- **Implementation Status**: `docs/V2_IMPLEMENTATION_STATUS.md`
- **Config Examples**: `config/packs/`
- **Intent Patterns**: `config/intent_patterns.txt`

## 🚀 Coming Soon (Optional)

- **Trend Booster Job**: Daily hot topic collection
- **GitHub Actions**: Automated daily scans
- **Slack Integration**: Top 3 insights notifications

---

**Questions?** Check `docs/V2_IMPLEMENTATION_STATUS.md` for detailed implementation notes.
