# Database Scripts

## `init_db.py`

Initialize database tables. Run this once after setting up PostgreSQL/Supabase.

```bash
python scripts/init_db.py
```

Creates:
- `users` table
- `user_settings` table
- `analyses` table
- `audit_logs` table

## `migrate_settings.py`

Migrate settings from `data/settings.json` to database.

```bash
python scripts/migrate_settings.py
```

This:
1. Reads `backend/data/settings.json`
2. Creates a "system" user (if it doesn't exist)
3. Migrates all settings to `user_settings` table
4. Creates backup: `settings.json.backup`

**Note**: After migration, you can delete `settings.json` (the backup is kept for safety).
