# Freemium Limits Implementation

**Step 3: Freemium Limits BEFORE Launch**

This document describes the freemium tier implementation for unmet, including usage limits, enforcement mechanisms, and configuration.

## Overview

unmet uses a freemium model to control costs and encourage upgrades:

| Feature | Free Tier | Premium Tier |
|---------|-----------|--------------|
| Market scans | 1 per day | Unlimited |
| Deep explorations | 3 per month | Unlimited |
| Insights visible per run | 10 | All |
| CSV/JSON export | No | Yes |
| API access | Limited | Full |

## Architecture

### Database Schema (Step 3 Migration)

The migration `003_add_users_and_freemium.py` adds:

1. **`users` table**
   - `id` (string, primary key) - UUID or external auth ID
   - `email` (string, nullable, unique)
   - `plan` (string, default 'free') - 'free' or 'premium'
   - `created_at` (timestamp)

2. **`runs.user_id`** - Foreign key to users
3. **`insight_explorations.user_id`** - Foreign key to users

### Key Files

| File | Purpose |
|------|---------|
| `src/need_scanner/auth.py` | Authentication dependency (`get_current_user`) |
| `src/need_scanner/limits.py` | Freemium limit checks and constants |
| `src/need_scanner/database/models.py` | User model and plan constants |
| `alembic/versions/003_*.py` | Database migration |

## Limit Configuration

Limits are defined as constants in `src/need_scanner/limits.py`:

```python
# Free tier limits
FREE_SCANS_PER_DAY = 1
FREE_EXPLORATIONS_PER_MONTH = 3
FREE_INSIGHTS_PER_RUN = 10

# Premium tier limits (None = unlimited)
PREMIUM_SCANS_PER_DAY = None
PREMIUM_EXPLORATIONS_PER_MONTH = None
PREMIUM_INSIGHTS_PER_RUN = None
```

To change limits:
1. Edit the constants in `limits.py`
2. Restart the API server

## Enforcement Functions

### `ensure_can_run_scan(user, db)`

Checks if a user can create a new scan:
- Counts scans created by this user today
- Raises HTTP 403 if >= `FREE_SCANS_PER_DAY`
- Premium users bypass this check

### `ensure_can_explore_insight(user, db)`

Checks if a user can create a deep exploration:
- Counts explorations created this calendar month
- Raises HTTP 403 if >= `FREE_EXPLORATIONS_PER_MONTH`
- Premium users bypass this check

### `get_insight_limit_for_user(user)`

Returns the insight visibility limit:
- Free users: `FREE_INSIGHTS_PER_RUN` (10)
- Premium users: `None` (unlimited)

### `ensure_can_export(user)`

Checks if a user can export data:
- Free users: Always raises HTTP 403
- Premium users: Allowed

## API Endpoints

### Protected Endpoints

| Endpoint | Limit Enforced |
|----------|----------------|
| `POST /runs` | 1 scan/day (free) |
| `POST /insights/{id}/explore` | 3 explorations/month (free) |
| `GET /runs/{run_id}/insights` | 10 insights visible (free) |
| `GET /runs/{run_id}/export/csv` | Premium only |
| `GET /runs/{run_id}/export/json` | Premium only |

### Usage Stats Endpoint

`GET /me/usage` returns current usage and remaining quota:

```json
{
  "plan": "free",
  "is_premium": false,
  "scans": {
    "used_today": 0,
    "limit_per_day": 1,
    "remaining_today": 1
  },
  "explorations": {
    "used_this_month": 2,
    "limit_per_month": 3,
    "remaining_this_month": 1
  },
  "insights_per_run": 10,
  "can_export": false
}
```

## Error Responses

All limit errors return HTTP 403 with structured JSON:

```json
{
  "detail": "Free plan limit reached: 1 market scan per day. Upgrade to run more scans.",
  "code": "SCAN_LIMIT_REACHED",
  "plan": "free",
  "limit": {
    "scans_per_day": 1,
    "used_today": 1
  }
}
```

Error codes:
- `SCAN_LIMIT_REACHED` - Daily scan limit exceeded
- `EXPLORATION_LIMIT_REACHED` - Monthly exploration limit exceeded
- `EXPORT_RESTRICTED` - Export attempted on free plan

## Authentication

### Development Mode (Current)

Uses `X-Dummy-User-Id` header for identification:

```bash
curl -H "X-Dummy-User-Id: user123" http://localhost:8000/runs
```

- If user doesn't exist, auto-created with `plan='free'`
- Missing header returns HTTP 401

### Production Mode (Future)

Replace `get_current_user()` in `auth.py` with:
- Supabase Auth JWT validation
- Extract user ID from token claims
- Keep same interface for endpoints

## Upgrading Users

To upgrade a user to premium:

```sql
UPDATE users SET plan = 'premium' WHERE id = 'user123';
```

Or via Python:

```python
from need_scanner.database import get_db_session, User, PLAN_PREMIUM

with get_db_session() as db:
    user = db.query(User).filter(User.id == 'user123').first()
    if user:
        user.plan = PLAN_PREMIUM
        db.commit()
```

## Insights Response Format

The `GET /runs/{run_id}/insights` endpoint returns:

```json
{
  "items": [...],
  "total_count": 27,
  "returned_count": 10,
  "has_more": true,
  "limit_applied": 10
}
```

- `total_count`: Total insights in the run (after filters)
- `returned_count`: Number actually returned
- `has_more`: True if there are more than returned
- `limit_applied`: The freemium limit (null for premium)

This allows the frontend to show "17 more insights available with Premium".

## Testing

### Test Scan Limit

```bash
# First scan succeeds
curl -X POST -H "X-Dummy-User-Id: test-user" \
  -H "Content-Type: application/json" \
  -d '{"mode": "deep"}' \
  http://localhost:8000/runs

# Second scan same day fails with 403
curl -X POST -H "X-Dummy-User-Id: test-user" \
  -H "Content-Type: application/json" \
  -d '{"mode": "deep"}' \
  http://localhost:8000/runs
```

### Test Export Block

```bash
# Free user blocked
curl -H "X-Dummy-User-Id: free-user" \
  http://localhost:8000/runs/20251205_143022/export/csv
# Returns 403

# Premium user allowed (after upgrade)
curl -H "X-Dummy-User-Id: premium-user" \
  http://localhost:8000/runs/20251205_143022/export/csv
# Returns 501 (not implemented yet)
```

## Running Migrations

```bash
# Apply the freemium migration
alembic upgrade head

# Or specifically
alembic upgrade 003
```

## Future Enhancements

1. **Billing Integration** - Connect to Stripe/Paddle for payment processing
2. **IP Rate Limiting** - Additional abuse protection (Step 4)
3. **Daily Automated Scans** - Premium feature for scheduled scans
4. **Queue Priority** - Premium users get faster processing
5. **Real Authentication** - Replace dummy auth with Supabase Auth
