# Database Quick Start

**5-minute setup** to get PostgreSQL working with Incident RAG.

---

## 1. Create Supabase Project (2 min)

1. Go to [supabase.com](https://supabase.com) → Sign up (free)
2. Click **"New Project"**
3. Fill in:
   - Name: `incident-rag`
   - Password: (save it!)
   - Region: (closest to you)
4. Wait ~1 minute for provisioning

---

## 2. Get Connection String (1 min)

1. In Supabase dashboard → **Settings** → **Database**
2. Scroll to **"Connection string"** → **"URI"**
3. Select **"Session mode"** (for serverless) or **"Transaction mode"**
4. Copy the string (looks like):
   ```
   postgresql://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```
5. **Convert to asyncpg format** (add `+asyncpg`):
   ```
   postgresql+asyncpg://postgres.xxxxx:YOUR-PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```

---

## 3. Add to Backend `.env` (30 sec)

Edit `backend/.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres.xxxxx:YOUR-PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

Replace `YOUR-PASSWORD` with your actual database password.

---

## 4. Install Dependencies (1 min)

```bash
cd backend
pip install -r requirements.txt
```

This installs `sqlalchemy[asyncio]` and `asyncpg`.

---

## 5. Initialize Database (30 sec)

```bash
python scripts/init_db.py
```

You should see:
```
✅ Database tables created successfully!
```

---

## 6. (Optional) Migrate Existing Settings

If you have `data/settings.json`:

```bash
python scripts/migrate_settings.py
```

---

## ✅ Done!

Start your backend:

```bash
python run.py
```

Look for: `Database initialized` in the startup logs.

---

## Verify It Works

```bash
# Check stats (should show database_enabled: true)
curl http://localhost:8000/stats

# Run an analysis (saves to database)
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"query": "Test", "timestamp": "2024-01-15T14:32:00Z"}'
```

---

## Troubleshooting

**"could not connect"** → Check password in `DATABASE_URL`

**"relation does not exist"** → Run `python scripts/init_db.py` again

**"password authentication failed"** → Reset password in Supabase dashboard

---

## Next: Multi-User

Once database is working, you can:
- Add user authentication (JWT)
- Enable per-user settings
- Track analysis history per user

See [DATABASE_MIGRATION.md](./DATABASE_MIGRATION.md) for details.
