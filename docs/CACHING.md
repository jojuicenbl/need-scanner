# Step 4: Caching of Daily Results

This document explains the caching mechanism implemented in Step 4 to avoid recomputing identical scans multiple times per day.

## Overview

When multiple users request the **same scan configuration** on the **same day**, we want to:
- Reuse previously computed results instead of running a new expensive pipeline
- Still count usage per user (freemium limits remain correct)
- Keep the job queue and worker behavior clean

The solution uses **canonical runs** and **cached runs** within the existing `runs` table.

## Key Concepts

### Canonical Run
A **canonical run** is a run that is actually processed by the worker:
- `is_cached_result = false`
- `source_run_id = NULL`
- Has insights stored directly on it
- Created when no matching run exists for today's configuration

### Cached Run
A **cached run** is a per-user run that reuses results from a canonical run:
- `is_cached_result = true`
- `source_run_id` points to the canonical run
- Has no insights stored directly (delegates to source run)
- Created when a matching canonical run already exists for today

### Cache Key
The `cache_key` is a deterministic identifier for a scan configuration + date:
- SHA256 hash of JSON containing: `mode`, `run_mode`, `max_insights`, `input_pattern`, `date`
- Does NOT include `user_id` (enables cross-user reuse)
- Includes `date` so cache resets daily at midnight UTC

## Database Schema

Three columns were added to the `runs` table:

```sql
-- Deterministic key for scan configuration + date
cache_key TEXT

-- Whether this run reuses another run's results
is_cached_result BOOLEAN NOT NULL DEFAULT false

-- For cached runs: points to the canonical run
source_run_id VARCHAR(50) REFERENCES runs(id) ON DELETE SET NULL
```

### Indexes

```sql
-- For finding canonical runs by cache_key
CREATE INDEX idx_runs_cache_key_canonical
ON runs(cache_key, is_cached_result, created_at);

-- For finding cached runs pointing to a canonical run
CREATE INDEX idx_runs_source_run_id ON runs(source_run_id);
```

## How It Works

### 1. POST /runs (Creating a Scan)

When a user creates a scan:

1. **Build cache key** from scan parameters + today's date
2. **Search for existing canonical run** with same cache_key that is `running` or `completed`
3. Based on result:

**Case A: Found completed canonical run**
- Create a new cached run for this user
- Set `status = 'completed'`, `source_run_id = canonical.id`
- Return immediately with results available

**Case B: Found running canonical run**
- Create a new cached run for this user
- Set `status = 'running'`, `source_run_id = canonical.id`
- User polls for completion (will complete when canonical completes)

**Case C: No canonical run found**
- Create a new canonical run with `status = 'queued'`
- Worker will pick it up and process it

### 2. Worker Processing

The worker query was modified to only pick canonical runs:

```sql
SELECT id FROM runs
WHERE status = 'queued'
  AND is_cached_result = false
ORDER BY created_at ASC
LIMIT 1
FOR UPDATE SKIP LOCKED
```

Cached runs are never processed by workers - they wait for their source run to complete.

### 3. GET /runs/{run_id}/insights

When fetching insights:

1. Load the run from database
2. If `run.is_cached_result = true` and `run.source_run_id` is set:
   - Use `source_run_id` as the `effective_run_id` for querying insights
3. Query insights with `run_id = effective_run_id`
4. Apply freemium limits as usual

This is transparent to the user - they just see insights for their run.

## Interaction with Existing Features

### Freemium Limits (Step 3)

Cached runs **still count** toward the user's daily scan limit:
- Each user gets their own run record with `created_at = now()`
- `count_user_scans_today()` counts all runs for the user today
- This prevents abuse (e.g., creating many cached runs)

### Job Queue (Step 2)

Only canonical runs are processed by workers:
- `claim_next_job()` filters on `is_cached_result = false`
- `count_queued_jobs()` only counts canonical queued jobs
- Workers ignore cached runs entirely

### Insights Retrieval

Cached runs delegate to their source run for insights:
- Insights are stored only on canonical runs
- `get_effective_run_id_for_insights()` handles the delegation
- Users see the same insights regardless of which run they access

## Cache Invalidation

The cache automatically resets daily because:
- `cache_key` includes the date component
- At midnight UTC, new scans will have a different cache_key
- Old cached runs remain for history/auditing but won't match new requests

## Example Flow

### First User of the Day

```
User A: POST /runs {mode: "deep", run_mode: "discover"}
→ No canonical run found
→ Create canonical run R1 (status=queued, is_cached_result=false)
→ Worker picks up R1, processes it
→ R1 completes with 20 insights stored
```

### Subsequent Users Same Day

```
User B: POST /runs {mode: "deep", run_mode: "discover"}
→ Found canonical run R1 (completed)
→ Create cached run R2 (status=completed, source_run_id=R1)
→ Return immediately

User B: GET /runs/R2/insights
→ R2.is_cached_result = true
→ effective_run_id = R1
→ Query insights from R1
→ Return insights (with freemium limit if applicable)
```

### In-Progress Cache Hit

```
User C: POST /runs {mode: "deep", run_mode: "discover"}
→ Found canonical run R1 (running, progress=40%)
→ Create cached run R3 (status=running, source_run_id=R1)
→ Return with status=running

User C: GET /runs/R3
→ Shows status=running, progress=40%

[Worker completes R1]

User C: GET /runs/R3/insights
→ Now returns insights from R1
```

## Files Changed

### Migration
- `alembic/versions/20241206_000001_004_add_caching_columns.py`

### Models
- `src/need_scanner/database/models.py` - Added caching fields to Run

### Services
- `src/need_scanner/services/cache.py` - New caching helper functions

### API
- `src/need_scanner/api.py` - Modified POST /runs and GET /runs/{run_id}/insights

### Database Operations
- `src/need_scanner/db.py` - Modified claim_next_job, count_queued_jobs, _run_to_dict

## Running the Migration

```bash
# Apply the migration
alembic upgrade head

# Verify columns exist
psql $DATABASE_URL -c "\d runs" | grep -E "cache_key|is_cached_result|source_run_id"
```

## Monitoring

To see cache usage:

```sql
-- Count of canonical vs cached runs today
SELECT
    is_cached_result,
    COUNT(*) as count
FROM runs
WHERE DATE(created_at) = CURRENT_DATE
GROUP BY is_cached_result;

-- Cache hit rate today
SELECT
    COUNT(*) FILTER (WHERE is_cached_result = true)::float /
    NULLIF(COUNT(*), 0) as cache_hit_rate
FROM runs
WHERE DATE(created_at) = CURRENT_DATE;
```
