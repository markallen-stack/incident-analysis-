# Supabase Setup Guide for Incident RAG

This guide walks you through setting up a free PostgreSQL database on Supabase and configuring your Incident RAG backend to use it.

---

## Step 1: Create a Supabase Account

1. Go to [supabase.com](https://supabase.com)
2. Click **"Start your project"** or **"Sign in"**
3. Sign up with GitHub, Google, or email (free tier available)

---

## Step 2: Create a New Project

1. Click **"New Project"**
2. Fill in:
   - **Name**: `incident-rag` (or your choice)
   - **Database Password**: Create a strong password (save it!)
   - **Region**: Choose closest to your deployment (e.g., `us-east-1`)
   - **Pricing Plan**: Free tier is fine
3. Click **"Create new project"**
4. Wait 1-2 minutes for provisioning

---

## Step 3: Get Database Connection String

### Option A: Connection Pooler (Recommended for Serverless)

1. In your Supabase project dashboard, go to **Settings** → **Database**
2. Scroll to **"Connection string"** → **"URI"**
3. Select **"Session mode"** or **"Transaction mode"**
4. Copy the connection string (looks like):
   ```
   postgresql://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```
5. **Important**: Replace `[YOUR-PASSWORD]` with your actual database password
6. Convert to asyncpg format:
   ```
   postgresql+asyncpg://postgres.xxxxx:YOUR-PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```

### Option B: Direct Connection (For Persistent Servers)

1. In **Settings** → **Database**, find **"Connection string"** → **"URI"**
2. Select **"Direct connection"**
3. Copy and convert:
   ```
   postgresql+asyncpg://postgres.xxxxx:YOUR-PASSWORD@db.xxxxx.supabase.co:5432/postgres
   ```

---

## Step 4: Configure Backend

### 4.1 Add to `.env` file

Create or edit `backend/.env`:

```env
# Supabase Database URL (use the connection string from Step 3)
DATABASE_URL=postgresql+asyncpg://postgres.xxxxx:YOUR-PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres

# Or use SUPABASE_DB_URL (alternative name)
# SUPABASE_DB_URL=postgresql+asyncpg://postgres.xxxxx:YOUR-PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres

# Your existing settings...
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
PRIMARY_LLM=claude-sonnet-4-20250514
# ... etc
```

**Security Note**: Never commit `.env` to git! Add it to `.gitignore`.

### 4.2 Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This installs:
- `sqlalchemy[asyncio]` - ORM with async support
- `asyncpg` - PostgreSQL async driver
- `alembic` - Database migrations (optional, for advanced use)

---

## Step 5: Initialize Database Tables

Run the initialization script:

```bash
cd backend
python scripts/init_db.py
```

This creates:
- `users` - User accounts
- `user_settings` - Per-user configuration
- `analyses` - Analysis history
- `audit_logs` - Audit trail

**Expected output:**
```
============================================================
Database Initialization
============================================================
Database URL: postgresql+asyncpg://postgres.xxxxx@***
✅ Database tables created successfully!

Tables created:
  - users
  - user_settings
  - analyses
  - audit_logs
```

---

## Step 6: (Optional) Migrate Existing Settings

If you have existing settings in `data/settings.json`, migrate them:

```bash
python scripts/migrate_settings.py
```

This:
- Reads `backend/data/settings.json`
- Creates a "system" user (for system-wide defaults)
- Migrates all settings to the database
- Creates a backup: `settings.json.backup`

---

## Step 7: Verify Connection

Start your backend:

```bash
cd backend
python run.py
```

Look for:
```
🚀 Starting Incident Analysis API...
   Database initialized
   Confidence threshold: 0.7
   MCP enabled: True
```

If you see "Database initialized", you're good!

---

## Step 8: Test the API

### Check database stats:

```bash
curl http://localhost:8000/stats
```

Should return:
```json
{
  "total_analyses_db": 0,
  "database_enabled": true,
  ...
}
```

### Run an analysis:

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query": "API outage at 14:32 UTC",
    "timestamp": "2024-01-15T14:32:00Z"
  }'
```

The analysis should be saved to the database automatically.

---

## Troubleshooting

### Error: "could not connect to server"

**Cause**: Wrong connection string or network issue.

**Fix**:
1. Verify your password in the connection string
2. Check if you're using the **pooler** URL (port 6543) or **direct** URL (port 5432)
3. For serverless (Vercel/Railway), use the **pooler** URL
4. For persistent servers, either works

### Error: "relation 'users' does not exist"

**Cause**: Tables not created.

**Fix**: Run `python scripts/init_db.py` again.

### Error: "password authentication failed"

**Cause**: Wrong password in connection string.

**Fix**:
1. Go to Supabase → Settings → Database
2. Reset password if needed
3. Update `.env` with the correct password

### Connection timeout

**Cause**: Using direct connection from serverless.

**Fix**: Switch to **pooler** URL (port 6543) in your connection string.

---

## Supabase Dashboard

### View Your Data

1. Go to your Supabase project
2. Click **"Table Editor"** in the sidebar
3. You'll see:
   - `users` - User accounts
   - `user_settings` - Per-user settings
   - `analyses` - Analysis history
   - `audit_logs` - Audit trail

### SQL Editor

Use the **SQL Editor** to run queries:

```sql
-- Count analyses
SELECT COUNT(*) FROM analyses;

-- Get recent analyses
SELECT analysis_id, status, confidence, created_at 
FROM analyses 
ORDER BY created_at DESC 
LIMIT 10;

-- Get user settings
SELECT key, value, value_type 
FROM user_settings 
WHERE user_id = 'system';
```

---

## Free Tier Limits

| Resource | Free Tier Limit |
|----------|----------------|
| **Database Size** | 500 MB |
| **Bandwidth** | 2 GB/month |
| **API Requests** | Unlimited |
| **Concurrent Connections** | 60 (pooler) / 4 (direct) |

**For Incident RAG**: This is usually enough for:
- Hundreds of users
- Thousands of analyses
- Millions of settings records

If you exceed limits, Supabase will notify you. Upgrade to Pro ($25/month) for more capacity.

---

## Security Best Practices

1. **Never commit `.env`** - Add to `.gitignore`
2. **Use environment variables** in production (Railway, Render, etc.)
3. **Rotate passwords** periodically
4. **Use connection pooling** for serverless (port 6543)
5. **Enable Row Level Security (RLS)** in Supabase if you add multi-user auth later

---

## Next Steps

- ✅ Database is set up
- ✅ Tables are created
- ✅ Backend is connected

**Now you can:**
1. Deploy backend to Railway/Render (set `DATABASE_URL` in their dashboard)
2. Deploy frontend to Vercel
3. Add user authentication (see multi-user guide)
4. Start using per-user settings and analysis history

---

## Alternative: Local PostgreSQL

If you prefer to run PostgreSQL locally:

```bash
# macOS (Homebrew)
brew install postgresql@14
brew services start postgresql@14
createdb incident_rag

# Then in .env:
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/incident_rag
```

---

## Support

- **Supabase Docs**: [supabase.com/docs](https://supabase.com/docs)
- **SQLAlchemy Async**: [docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- **Project Issues**: Check your project's issue tracker
