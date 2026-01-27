# Database Migration Guide

This document explains how persistent data was moved from files to PostgreSQL.

---

## What Changed

### Before (File-Based)

| Data | Storage | Location |
|------|---------|----------|
| Settings | `data/settings.json` | Single file, global |
| Analysis history | In-memory `analysis_cache` | Lost on restart |
| User data | None | No multi-user support |

### After (Database)

| Data | Storage | Location |
|------|---------|----------|
| Settings | `user_settings` table | Per-user in PostgreSQL |
| Analysis history | `analyses` table | Persistent in PostgreSQL |
| User accounts | `users` table | PostgreSQL |
| Audit logs | `audit_logs` table | PostgreSQL |

---

## Database Schema

### `users`
- `id` (UUID, PK)
- `email` (unique)
- `password_hash`
- `name`
- `is_active`, `is_admin`
- `created_at`, `updated_at`

### `user_settings`
- `id` (UUID, PK)
- `user_id` (FK → users)
- `key` (e.g., "CONFIDENCE_THRESHOLD")
- `value` (text, stored as string)
- `value_type` (string, int, float, bool, path, json)
- Unique constraint: `(user_id, key)`

### `analyses`
- `id` (UUID, PK)
- `analysis_id` (unique, e.g., "analysis_1234567890")
- `user_id` (FK → users, nullable for anonymous)
- `request` (JSONB: full IncidentAnalysisRequest)
- `response` (JSONB: full IncidentAnalysisResponse)
- `status`, `confidence`, `root_cause`, `processing_time_ms`
- `created_at` (indexed)

### `audit_logs`
- `id` (UUID, PK)
- `user_id` (FK → users, nullable)
- `action` (e.g., "login", "run_analysis")
- `resource`, `details` (JSONB)
- `ip_address`, `user_agent`
- `created_at` (indexed)

---

## Migration Path

### Step 1: Set Up Database

Follow [SUPABASE_SETUP.md](./SUPABASE_SETUP.md) to:
1. Create Supabase project
2. Get connection string
3. Add to `.env`: `DATABASE_URL=...`

### Step 2: Initialize Tables

```bash
cd backend
python scripts/init_db.py
```

### Step 3: Migrate Existing Settings (Optional)

If you have `data/settings.json`:

```bash
python scripts/migrate_settings.py
```

This creates a "system" user and migrates settings.

### Step 4: Start Backend

```bash
python run.py
```

The backend will:
- Connect to database on startup
- Save new analyses to database
- Read settings from database (if user_id provided)

---

## Backward Compatibility

The system maintains backward compatibility:

1. **Settings API**:
   - If `user_id` is provided → reads from database
   - If no `user_id` → reads from `data/settings.json` (system-wide)

2. **Analysis Cache**:
   - New analyses → saved to database
   - Old analyses → still in `analysis_cache` (in-memory)
   - `GET /analysis/:id` checks database first, then cache

3. **System Defaults**:
   - `config.py` still loads from `.env` and `settings.json`
   - Database settings override system defaults per-user

---

## API Changes

### Settings Endpoints

**Before:**
```python
GET /settings  # System-wide only
PUT /settings  # System-wide only
```

**After:**
```python
GET /settings?user_id=xxx  # Per-user (when auth added)
PUT /settings?user_id=xxx  # Per-user (when auth added)
# Still works without user_id (system-wide, backward compat)
```

### Analysis Endpoints

**Before:**
```python
POST /analyze  # Saved to in-memory cache
GET /analysis/:id  # From cache only
```

**After:**
```python
POST /analyze  # Saved to database + cache (backward compat)
GET /analysis/:id  # Database first, then cache
GET /analyses?user_id=xxx&limit=100  # NEW: List user's analyses
```

---

## Code Changes Summary

### New Files

- `backend/core/database/models.py` - SQLAlchemy models
- `backend/core/database/session.py` - Database connection
- `backend/core/database/crud.py` - CRUD operations
- `backend/core/database/settings.py` - DB-backed settings API
- `backend/scripts/init_db.py` - Table initialization
- `backend/scripts/migrate_settings.py` - Settings migration

### Modified Files

- `backend/app/main.py`:
  - Added `get_db` dependency
  - `/analyze` saves to database
  - `/analysis/:id` reads from database
  - `/settings` supports per-user (when `user_id` provided)
  - `/stats` includes database counts

- `backend/requirements.txt`:
  - Added `sqlalchemy[asyncio]>=2.0.0`
  - Added `asyncpg>=0.29.0`
  - Added `alembic>=1.13.0`

---

## Next Steps: Multi-User Auth

To enable full multi-user support:

1. **Add authentication**:
   - JWT tokens (`python-jose` already in requirements)
   - Password hashing (`passlib[bcrypt]` already in requirements)
   - Login/signup endpoints

2. **Update endpoints**:
   - Extract `user_id` from JWT token
   - Pass to `get_db()` and CRUD functions
   - Enforce access control (users can only see their own analyses)

3. **Frontend**:
   - Add login/signup pages
   - Store JWT in httpOnly cookie or memory
   - Send `Authorization: Bearer <token>` header
   - Update Settings page to show per-user settings

See the main documentation for auth implementation details.

---

## Troubleshooting

### "Database tables not found"

Run: `python scripts/init_db.py`

### "Connection refused"

Check:
- `DATABASE_URL` in `.env`
- Supabase project is active
- Password is correct
- Using pooler URL (port 6543) for serverless

### "Settings not persisting"

- If using per-user settings: ensure `user_id` is provided
- If using system-wide: check `data/settings.json` still exists (backward compat)

### "Analysis not found after restart"

- Old analyses in `analysis_cache` are lost (expected)
- New analyses are in database (persistent)
- Run migration script if you need to import old data

---

## Performance Notes

- **Indexes**: Created on `user_id`, `analysis_id`, `created_at`, `status`, `confidence`
- **Connection Pooling**: Configured (pool_size=5, max_overflow=10)
- **JSONB**: Used for `request` and `response` (efficient querying)
- **Async**: All database operations are async (non-blocking)

---

## See Also

- [SUPABASE_SETUP.md](./SUPABASE_SETUP.md) - Detailed Supabase setup
- [docs/DOCUMENTATION.md](./DOCUMENTATION.md) - Full technical docs
- [backend/core/database/](../backend/core/database/) - Database code
