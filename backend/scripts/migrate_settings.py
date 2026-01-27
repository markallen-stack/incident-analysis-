#!/usr/bin/env python3
"""
Migrate settings from data/settings.json to database.
Creates a system user (user_id="system") to hold system-wide settings.

Usage:
    python scripts/migrate_settings.py
"""

import asyncio
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database.session import get_db, init_db
from core.database.crud import create_user, update_user_setting, get_user_by_id
from core.database.models import User
import config


async def main():
    """Migrate settings from file to database"""
    print("=" * 60)
    print("Settings Migration: File → Database")
    print("=" * 60)
    
    # Check if settings.json exists
    settings_file = config.DATA_DIR / "settings.json"
    if not settings_file.exists():
        print("ℹ️  No settings.json found. Nothing to migrate.")
        return 0
    
    print(f"Reading settings from: {settings_file}")
    
    # Load settings from file
    try:
        with open(settings_file, "r") as f:
            file_settings = json.load(f)
    except Exception as e:
        print(f"❌ Error reading settings.json: {e}")
        return 1
    
    if not file_settings:
        print("ℹ️  settings.json is empty. Nothing to migrate.")
        return 0
    
    print(f"Found {len(file_settings)} settings to migrate")
    
    # Get or create system user
    async for db in get_db():
        # Check if system user exists
        system_user = await get_user_by_id(db, "system")
        
        if not system_user:
            print("\nCreating system user...")
            system_user = await create_user(
                db=db,
                email="system@incident-rag.local",
                password_hash="",  # System user has no password
                name="System",
                is_admin=True
            )
            # Override ID to "system" for consistency
            system_user.id = "system"
            await db.commit()
            print("✅ System user created")
        else:
            print("✅ System user already exists")
        
        # Migrate each setting
        migrated = 0
        skipped = 0
        
        print("\nMigrating settings...")
        for key, value in file_settings.items():
            # Find setting metadata
            meta = next((s for s in config.SETTINGS_SCHEMA if s["key"] == key), None)
            if not meta:
                print(f"  ⚠️  Unknown setting key: {key} (skipping)")
                skipped += 1
                continue
            
            value_type = meta.get("type", "string")
            
            # Update in database
            await update_user_setting(
                db=db,
                user_id="system",
                key=key,
                value=value,
                value_type=value_type
            )
            migrated += 1
            print(f"  ✓ {key}")
        
        print(f"\n✅ Migration complete!")
        print(f"   Migrated: {migrated}")
        print(f"   Skipped: {skipped}")
        
        # Optionally backup old file
        backup_file = settings_file.with_suffix(".json.backup")
        if not backup_file.exists():
            import shutil
            shutil.copy(settings_file, backup_file)
            print(f"\n📦 Backup created: {backup_file}")
            print("   You can delete settings.json after verifying the migration")
        
        break  # Exit the async generator
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
