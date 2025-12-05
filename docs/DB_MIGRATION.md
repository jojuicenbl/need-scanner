# Database Migration: SQLite to PostgreSQL (Supabase)

This guide explains how to migrate Need Scanner from SQLite to PostgreSQL using Supabase.

## Overview

Need Scanner now uses PostgreSQL as its database backend. This provides:
- Concurrent write support (essential for multi-user SaaS)
- Better scalability for thousands of users
- Connection pooling
- Compatible with Supabase hosting

## Prerequisites

1. A PostgreSQL database (local or Supabase)
2. Python dependencies installed: `pip install -r requirements.txt`
3. (Optional) Existing SQLite data to migrate

## Step 1: Set Up PostgreSQL Database

### Option A: Using Supabase (Recommended for Production)

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **Settings → Database** to find your connection string
3. Use the **Transaction Pooler** connection string (port 6543) for better performance

Your connection string will look like:
```
postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

### Option B: Local PostgreSQL (Development)

```bash
# macOS with Homebrew
brew install postgresql@16
brew services start postgresql@16

# Create database
createdb needscanner
```

Local connection string:
```
postgresql://localhost:5432/needscanner
```

## Step 2: Configure Environment Variable

Add `DATABASE_URL` to your `.env` file:

```bash
# .env file
DATABASE_URL=postgresql+psycopg2://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

**Important:**
- Use `postgresql+psycopg2://` prefix (not just `postgresql://`)
- Never commit `.env` to version control
- The app will fail fast with a clear error if `DATABASE_URL` is not set

## Step 3: Run Alembic Migrations

Alembic manages database schema migrations.

```bash
# Apply all migrations (creates tables)
alembic upgrade head

# Check current migration status
alembic current

# View migration history
alembic history
```

### Migration Commands Reference

```bash
# Create a new migration (after modifying models)
alembic revision --autogenerate -m "description of changes"

# Downgrade one migration
alembic downgrade -1

# Downgrade to a specific revision
alembic downgrade <revision_id>

# View SQL without executing (offline mode)
alembic upgrade head --sql
```

## Step 4: Migrate Existing SQLite Data (Optional)

If you have existing data in SQLite, use the migration script:

```bash
# Default SQLite path: data/needscanner.db
python scripts/migrate_sqlite_to_postgres.py

# Custom SQLite path
python scripts/migrate_sqlite_to_postgres.py --sqlite-path /path/to/your.db

# Dry run (see what would be migrated without actually migrating)
python scripts/migrate_sqlite_to_postgres.py --dry-run
```

The migration script:
- Copies all runs, insights, and explorations
- Skips rows that already exist in PostgreSQL (idempotent)
- Logs any problematic rows instead of crashing
- Preserves existing IDs and timestamps

## Step 5: Verify Migration

```bash
# Start the API server
python -m uvicorn src.need_scanner.api:app --reload

# Check health endpoint (includes database status)
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2024-12-05T..."
}
```

## Database Schema

The schema includes these tables:

### `runs`
Scan run metadata.

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(50) | Primary key (format: `YYYYMMDD_HHMMSS`) |
| created_at | TIMESTAMP | Creation timestamp |
| mode | VARCHAR(20) | `light` or `deep` |
| nb_insights | INTEGER | Number of insights |
| nb_clusters | INTEGER | Number of clusters |
| total_cost_usd | FLOAT | Total API cost |
| ... | ... | ... |

### `insights`
Individual insights from each run.

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(100) | Primary key (format: `{run_id}_cluster_{cluster_id}`) |
| run_id | VARCHAR(50) | Foreign key to runs |
| rank | INTEGER | Ranking position |
| priority_score | FLOAT | Priority score (0-10) |
| saas_viable | INTEGER | SaaS viability (0/1/NULL) |
| ... | ... | ... |

### `insight_explorations`
Deep explorations of insights.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Auto-incrementing primary key |
| insight_id | VARCHAR(100) | Foreign key to insights |
| exploration_text | TEXT | Full exploration content |
| ... | ... | ... |

## Indexes

The following indexes are created for performance:

- `idx_runs_created_at` - For sorting runs by date
- `idx_insights_run_id` - For filtering insights by run
- `idx_insights_priority_score` - For sorting by priority
- `idx_insights_sector` - For sector filtering
- `idx_insights_saas_viable` - For SaaS viability filtering
- `idx_explorations_insight_id` - For finding explorations

## Troubleshooting

### "DATABASE_URL environment variable is not set"

Make sure you've set the environment variable:
```bash
export DATABASE_URL="postgresql+psycopg2://..."
# Or add to .env file
```

### "Connection refused" or timeout errors

1. Check your database is running
2. Verify the connection string is correct
3. For Supabase, ensure you're using the correct port (6543 for pooler)
4. Check firewall/network settings

### "relation does not exist" errors

Run Alembic migrations:
```bash
alembic upgrade head
```

### Migration script fails

1. Run with `--dry-run` first to check for issues
2. Ensure PostgreSQL schema exists (run Alembic first)
3. Check the logs for specific row errors

## Rollback

If you need to revert to SQLite:

1. Keep your SQLite database as backup
2. Git checkout the previous `db.py` version
3. Set `NEEDSCANNER_DB_PATH` instead of `DATABASE_URL`

## Security Notes

- Never commit `DATABASE_URL` or credentials to version control
- Use environment variables or secrets management
- For Supabase, consider enabling Row Level Security (RLS) if needed
- The migration script does not drop or delete any data
