"""
CRUD operations for database models.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, desc
from sqlalchemy.orm import selectinload
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from .models import User, UserSetting, Analysis, AuditLog


# ============================================================================
# User CRUD
# ============================================================================

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get user by email"""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    """Get user by ID"""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    password_hash: str,
    name: Optional[str] = None,
    is_admin: bool = False
) -> User:
    """Create a new user"""
    user = User(
        email=email,
        password_hash=password_hash,
        name=name,
        is_admin=is_admin
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ============================================================================
# User Settings CRUD
# ============================================================================

async def get_user_settings(db: AsyncSession, user_id: str) -> Dict[str, Any]:
    """
    Get all settings for a user as a dictionary.
    Returns: { "KEY": value, ... }
    """
    result = await db.execute(
        select(UserSetting).where(UserSetting.user_id == user_id)
    )
    settings = result.scalars().all()
    
    # Convert to dict, casting values by type
    settings_dict = {}
    for s in settings:
        if s.value_type == "int":
            settings_dict[s.key] = int(s.value) if s.value else 0
        elif s.value_type == "float":
            settings_dict[s.key] = float(s.value) if s.value else 0.0
        elif s.value_type == "bool":
            settings_dict[s.key] = s.value.lower() in ("true", "1", "yes") if s.value else False
        elif s.value_type == "json":
            settings_dict[s.key] = json.loads(s.value) if s.value else {}
        else:  # string, path
            settings_dict[s.key] = s.value or ""
    
    return settings_dict


async def get_user_setting(db: AsyncSession, user_id: str, key: str) -> Optional[UserSetting]:
    """Get a specific setting for a user"""
    result = await db.execute(
        select(UserSetting).where(
            and_(UserSetting.user_id == user_id, UserSetting.key == key)
        )
    )
    return result.scalar_one_or_none()


async def update_user_setting(
    db: AsyncSession,
    user_id: str,
    key: str,
    value: Any,
    value_type: str = "string"
) -> UserSetting:
    """
    Update or create a user setting.
    """
    # Try to get existing
    existing = await get_user_setting(db, user_id, key)
    
    # Convert value to string for storage
    if value_type == "json":
        value_str = json.dumps(value) if value else "{}"
    else:
        value_str = str(value) if value is not None else ""
    
    if existing:
        existing.value = value_str
        existing.value_type = value_type
        existing.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        new_setting = UserSetting(
            user_id=user_id,
            key=key,
            value=value_str,
            value_type=value_type
        )
        db.add(new_setting)
        await db.commit()
        await db.refresh(new_setting)
        return new_setting


async def delete_user_setting(db: AsyncSession, user_id: str, key: str) -> bool:
    """Delete a user setting"""
    result = await db.execute(
        delete(UserSetting).where(
            and_(UserSetting.user_id == user_id, UserSetting.key == key)
        )
    )
    await db.commit()
    return result.rowcount > 0


# ============================================================================
# Analysis CRUD
# ============================================================================

async def create_analysis(
    db: AsyncSession,
    analysis_id: str,
    request: Dict[str, Any],
    response: Dict[str, Any],
    user_id: Optional[str] = None
) -> Analysis:
    """Create a new analysis record"""
    analysis = Analysis(
        analysis_id=analysis_id,
        user_id=user_id,
        request=request,
        response=response,
        status=response.get("status", "refuse"),
        confidence=response.get("confidence", 0.0),
        root_cause=response.get("root_cause"),
        processing_time_ms=response.get("processing_time_ms", 0.0)
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis


async def get_analysis_by_id(db: AsyncSession, analysis_id: str) -> Optional[Analysis]:
    """Get analysis by analysis_id (e.g., 'analysis_1234567890')"""
    result = await db.execute(
        select(Analysis).where(Analysis.analysis_id == analysis_id)
    )
    return result.scalar_one_or_none()


async def get_analysis_by_db_id(db: AsyncSession, db_id: str) -> Optional[Analysis]:
    """Get analysis by database ID (UUID)"""
    result = await db.execute(select(Analysis).where(Analysis.id == db_id))
    return result.scalar_one_or_none()


async def get_user_analyses(
    db: AsyncSession,
    user_id: str,
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None
) -> List[Analysis]:
    """Get analyses for a user, optionally filtered by status"""
    query = select(Analysis).where(Analysis.user_id == user_id)
    
    if status:
        query = query.where(Analysis.status == status)
    
    query = query.order_by(desc(Analysis.created_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    return list(result.scalars().all())


async def delete_analysis(db: AsyncSession, analysis_id: str) -> bool:
    """Delete an analysis"""
    result = await db.execute(
        delete(Analysis).where(Analysis.analysis_id == analysis_id)
    )
    await db.commit()
    return result.rowcount > 0


# ============================================================================
# Audit Log CRUD
# ============================================================================

async def create_audit_log(
    db: AsyncSession,
    user_id: Optional[str],
    action: str,
    resource: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AuditLog:
    """Create an audit log entry"""
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        details=details or {},
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def get_audit_logs(
    db: AsyncSession,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[AuditLog]:
    """Get audit logs with optional filters"""
    query = select(AuditLog)
    
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action == action)
    
    query = query.order_by(desc(AuditLog.created_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    return list(result.scalars().all())
