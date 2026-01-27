#!/usr/bin/env python3
"""
Initialize database: create all tables.
Run this once after setting up PostgreSQL/Supabase.

Usage:
    python scripts/init_db.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database.session import init_db, engine
from core.database.models import Base


async def main():
    """Create all database tables"""
    print("=" * 60)
    print("Database Initialization")
    print("=" * 60)
    
    # Check DATABASE_URL
    import os

    
    try:
        await init_db()
        print("\n✅ Database tables created successfully!")
        print("\nTables created:")
        print("  - users")
        print("  - user_settings")
        print("  - analyses")
        print("  - audit_logs")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
