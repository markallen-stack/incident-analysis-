"""
Audit log endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pydantic import BaseModel

from core.auth import get_current_user
from core.database.crud import get_audit_logs
from core.database.models import User, AuditLog
from core.database.session import get_db

router = APIRouter(prefix="/audit", tags=["Audit"])


class AuditLogEntry(BaseModel):
    """Audit log entry"""
    id: str
    action: str
    resource: Optional[str]
    details: Optional[dict]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    logs: List[AuditLogEntry]
    total: int
    limit: int
    offset: int


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    action: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List audit logs for the current user.
    Only admins can see all logs; regular users see only their own.
    """
    # Regular users can only see their own logs
    user_id = None if current_user.is_admin else current_user.id
    
    logs = await get_audit_logs(
        db=db,
        user_id=user_id,
        action=action,
        limit=limit,
        offset=offset
    )
    
    entries = [
        AuditLogEntry(
            id=log.id,
            action=log.action,
            resource=log.resource,
            details=log.details,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            created_at=log.created_at.isoformat()
        )
        for log in logs
    ]
    
    return AuditLogListResponse(
        logs=entries,
        total=len(entries),
        limit=limit,
        offset=offset
    )
