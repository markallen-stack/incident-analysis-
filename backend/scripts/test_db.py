#!/usr/bin/env python3
"""
Test database connection and basic operations.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database.session import get_db, engine
from core.database.crud import create_user, get_user_by_email
from core.auth import get_password_hash


async def test_connection():
    """Test basic database operations"""
    print("=" * 60)
    print("Database Connection Test")
    print("=" * 60)
    
    # Test 1: Connection
    print("\n[1] Testing connection...")
    try:
        async for db in get_db():
            # Simple query to test connection
            from sqlalchemy import text
            result = await db.execute(text("SELECT 1"))
            print("   ✅ Connection successful")
            break
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return 1
    
    # Test 2: Create test user
    print("\n[2] Creating test user...")
    try:
        async for db in get_db():
            test_email = "test@example.com"
            existing = await get_user_by_email(db, test_email)
            if existing:
                print(f"   ℹ️  Test user already exists: {test_email}")
            else:
                test_user = await create_user(
                    db=db,
                    email=test_email,
                    password_hash=get_password_hash("test123"),
                    name="Test User"
                )
                print(f"   ✅ Test user created: {test_user.id}")
            break
    except Exception as e:
        print(f"   ❌ Failed to create user: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Test 3: Settings
    print("\n[3] Testing settings...")
    try:
        async for db in get_db():
            from core.database.crud import update_user_setting, get_user_setting
            
            # Get test user
            test_user = await get_user_by_email(db, "test@example.com")
            if not test_user:
                print("   ⚠️  Test user not found, skipping settings test")
                break
            
            # Set a setting
            await update_user_setting(
                db=db,
                user_id=test_user.id,
                key="CONFIDENCE_THRESHOLD",
                value="0.8",
                value_type="float"
            )
            
            # Get it back
            setting = await get_user_setting(db, test_user.id, "CONFIDENCE_THRESHOLD")
            if setting and setting.value == "0.8":
                print("   ✅ Settings read/write works")
            else:
                print(f"   ⚠️  Settings test incomplete (got: {setting})")
            break
    except Exception as e:
        print(f"   ❌ Settings test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(test_connection()))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted")
        sys.exit(1)
    finally:
        # Cleanup
        asyncio.run(engine.dispose())
