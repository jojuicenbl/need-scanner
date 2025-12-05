# Scan Worker Documentation

## Overview

The Need Scanner uses a **job queue architecture** where HTTP requests only enqueue scan jobs, and a separate **worker process** processes them asynchronously. This design prevents long-running HTTP requests and allows the system to scale horizontally.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   FastAPI       │────▶│   PostgreSQL    │
│   (React)       │     │   (API)         │     │   (Job Queue)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                                ┌─────────────────┐
                                                │   Worker        │
                                                │   Process       │
                                                └─────────────────┘
```

### Flow

1. **Frontend** calls `POST /runs` to create a scan job
2. **API** inserts a row into `runs` with `status = 'queued'` and returns immediately
3. **Frontend** polls `GET /runs/{run_id}` to check progress
4. **Worker** picks up queued jobs using `SELECT ... FOR UPDATE SKIP LOCKED`
5. **Worker** runs the scan pipeline and updates job status/progress
6. **Frontend** sees `status = 'completed'` and fetches insights

## Running the Worker

### Basic Usage

```bash
# Run from the project root
python -m need_scanner.worker
```

### With Environment Variables

```bash
# Set poll interval (default: 5 seconds)
SCAN_WORKER_POLL_INTERVAL_SECONDS=10 python -m need_scanner.worker

# Set worker ID (useful for logging with multiple workers)
SCAN_WORKER_ID=worker-1 python -m need_scanner.worker

# Full example
SCAN_WORKER_POLL_INTERVAL_SECONDS=5 \
SCAN_WORKER_ID=worker-1 \
DATABASE_URL="postgresql://..." \
python -m need_scanner.worker
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | (required) | PostgreSQL connection string |
| `SCAN_WORKER_POLL_INTERVAL_SECONDS` | `5` | Seconds between job queue polls |
| `SCAN_WORKER_ID` | auto-generated | Unique worker identifier for logging |
| `OPENAI_API_KEY` | (required) | OpenAI API key for LLM calls |

## Running Multiple Workers

Multiple workers can run safely in parallel. Each worker uses `FOR UPDATE SKIP LOCKED` to claim jobs atomically, preventing race conditions.

```bash
# Terminal 1
SCAN_WORKER_ID=worker-1 python -m need_scanner.worker

# Terminal 2
SCAN_WORKER_ID=worker-2 python -m need_scanner.worker

# Terminal 3
SCAN_WORKER_ID=worker-3 python -m need_scanner.worker
```

Each worker will independently claim and process different jobs.

## Job Status Lifecycle

```
┌──────────┐     ┌──────────┐     ┌───────────┐
│  queued  │────▶│ running  │────▶│ completed │
└──────────┘     └──────────┘     └───────────┘
                       │
                       │ (error)
                       ▼
                ┌──────────┐
                │  failed  │
                └──────────┘
```

| Status | Description |
|--------|-------------|
| `queued` | Job created, waiting to be picked up |
| `running` | Worker is processing the scan |
| `completed` | Scan finished successfully |
| `failed` | Scan failed with an error |

## Progress Tracking

The worker updates `progress` (0-100) at key stages:

| Progress | Stage |
|----------|-------|
| 0% | Job started |
| 2% | Fetching fresh data (if needed) |
| 10% | Loading posts |
| 15% | Generating embeddings |
| 30% | Clustering |
| 40% | Running enriched pipeline |
| 80% | Exporting results |
| 95% | Finalizing |
| 100% | Complete |

The frontend can poll `GET /runs/{run_id}` to display this progress.

## Graceful Shutdown

The worker handles `SIGINT` (Ctrl+C) and `SIGTERM` gracefully:

1. Stops accepting new jobs
2. Logs any in-progress job ID
3. Exits cleanly

**Note:** If a worker is killed during a job, that job will remain in `running` status. You may need to manually reset it via the database:

```sql
-- Reset a stuck job
UPDATE runs SET status = 'queued', started_at = NULL, progress = 0
WHERE id = 'run_id_here' AND status = 'running';
```

## Monitoring

### Queue Status Endpoint

```bash
curl http://localhost:8000/queue/status
```

Response:
```json
{
  "queued_jobs": 3,
  "running_jobs": 1,
  "timestamp": "2025-12-05T14:30:22"
}
```

### Worker Logs

The worker outputs structured logs:

```
2025-12-05 14:30:22 | INFO     | worker | Need Scanner Worker Starting
2025-12-05 14:30:22 | INFO     | worker |    Worker ID: worker-1
2025-12-05 14:30:22 | INFO     | worker |    Poll Interval: 5s
2025-12-05 14:30:22 | INFO     | worker | Database connection verified
2025-12-05 14:30:22 | INFO     | worker | Worker started. Polling for jobs...
2025-12-05 14:30:27 | INFO     | worker | Claimed job 20251205_143022 by worker worker-1
2025-12-05 14:30:27 | INFO     | worker | Processing job: 20251205_143022
2025-12-05 14:30:27 | INFO     | worker |    Mode: deep
2025-12-05 14:30:27 | INFO     | worker |    Run Mode: discover
2025-12-05 14:30:27 | INFO     | worker |    Max Insights: 20
...
2025-12-05 14:32:10 | INFO     | worker | Job 20251205_143022 completed successfully
2025-12-05 14:32:10 | INFO     | worker |    Insights: 18
2025-12-05 14:32:10 | INFO     | worker |    Cost: $0.0542
```

## Database Schema

The `runs` table serves as both job queue and results storage:

### Job Queue Columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | `String(50)` | Primary key (timestamp-based) |
| `status` | `String(20)` | `queued`, `running`, `completed`, `failed` |
| `created_at` | `DateTime` | When job was created |
| `started_at` | `DateTime` | When worker started processing |
| `completed_at` | `DateTime` | When job finished |
| `progress` | `Integer` | Progress percentage (0-100) |
| `error_message` | `Text` | Error details if failed |

### Job Configuration Columns

| Column | Type | Description |
|--------|------|-------------|
| `mode` | `String(20)` | `light` or `deep` |
| `run_mode` | `String(20)` | `discover` or `track` |
| `max_insights` | `Integer` | Maximum insights to generate |
| `input_pattern` | `String(255)` | Glob pattern for input files |
| `config_name` | `String(100)` | Configuration name |

### Indexes

| Index | Columns | Purpose |
|-------|---------|---------|
| `idx_runs_status` | `status` | Filter by status |
| `idx_runs_status_created_at` | `status, created_at` | Job claiming query |
| `idx_runs_created_at` | `created_at DESC` | List recent runs |

## Troubleshooting

### Worker not picking up jobs

1. Check that `DATABASE_URL` is set correctly
2. Check that there are jobs in `queued` status:
   ```sql
   SELECT id, status, created_at FROM runs WHERE status = 'queued';
   ```
3. Check worker logs for errors

### Jobs stuck in `running` status

This can happen if a worker crashes during processing:

```sql
-- Find stuck jobs (running for more than 30 minutes)
SELECT id, started_at, NOW() - started_at as duration
FROM runs
WHERE status = 'running'
AND started_at < NOW() - INTERVAL '30 minutes';

-- Reset stuck jobs
UPDATE runs
SET status = 'queued', started_at = NULL, progress = 0
WHERE status = 'running'
AND started_at < NOW() - INTERVAL '30 minutes';
```

### High memory usage

The scan pipeline loads embeddings and runs LLM calls, which can use significant memory. If you're running multiple workers on the same machine, consider:

1. Reducing `max_insights` for lighter jobs
2. Running fewer workers
3. Using a machine with more RAM

## Development

### Testing the worker locally

1. Start the API server:
   ```bash
   uvicorn need_scanner.api:app --reload
   ```

2. Start the worker in another terminal:
   ```bash
   python -m need_scanner.worker
   ```

3. Create a test job:
   ```bash
   curl -X POST http://localhost:8000/runs \
     -H "Content-Type: application/json" \
     -d '{"mode": "light", "max_insights": 5}'
   ```

4. Watch the worker process the job and check progress:
   ```bash
   curl http://localhost:8000/runs/{run_id}
   ```
