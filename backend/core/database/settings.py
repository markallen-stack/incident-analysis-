"""
Database-backed settings management.
Handles per-user settings stored in PostgreSQL.
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from core.database.crud import (
    get_user_settings,
    update_user_setting,
    get_user_setting,
)
from core.database.models import UserSetting
import config


async def get_user_settings_for_api(
    db: AsyncSession,
    user_id: Optional[str],
    include_secrets: bool = False
) -> Dict[str, Any]:
    """
    Get settings for a user (or system defaults if user_id is None).
    Returns format: { "schema": [...], "values": {...} }
    """
    # Get user's settings from DB
    if user_id:
        db_settings = await get_user_settings(db, user_id)
    else:
        db_settings = {}
    
    # Merge with system defaults from config
    values = {}
    for s in config.SETTINGS_SCHEMA:
        k = s["key"]
        # User setting takes precedence, then system config, then default
        if k in db_settings:
            v = db_settings[k]
        else:
            # Get from system config
            v = getattr(config, k, s.get("default"))
        
        # Convert Path to string
        if isinstance(v, type(config.VECTOR_DB_PATH)) and hasattr(v, '__str__'):
            v = str(v)
        
        # Mask secrets unless include_secrets=True
        if s.get("secret") and v and not include_secrets:
            v = "********"
        
        values[k] = v
    
    return {
        "schema": config.SETTINGS_SCHEMA,
        "values": values
    }


async def update_user_settings_from_api(
    db: AsyncSession,
    user_id: str,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update user settings from API request.
    Returns updated settings.
    """
    key_to_meta = {s["key"]: s for s in config.SETTINGS_SCHEMA}
    
    for k, v in data.items():
        if k not in key_to_meta:
            continue
        
        meta = key_to_meta[k]
        
        # Skip if secret and value is masked/empty
        if meta.get("secret") and (v in (None, "", "********")):
            continue
        
        # Determine value type
        value_type = meta.get("type", "string")
        
        # Update in DB
        await update_user_setting(
            db=db,
            user_id=user_id,
            key=k,
            value=v,
            value_type=value_type
        )
    
    # Return updated settings
    return await get_user_settings_for_api(db, user_id, include_secrets=False)
