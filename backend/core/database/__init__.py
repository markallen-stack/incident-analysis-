"""
Database package for Incident RAG.
Provides SQLAlchemy models and session management for PostgreSQL.
"""

from .models import User, UserSetting, Analysis, AuditLog
from .session import get_db, init_db, engine, Base
from .crud import (
    get_user_by_email,
    create_user,
    get_user_settings,
    update_user_setting,
    get_user_setting,
    create_analysis,
    get_analysis_by_id,
    get_user_analyses,
    create_audit_log,
    get_audit_logs,
)
from .settings import (
    get_user_settings_for_api,
    update_user_settings_from_api,
)

__all__ = [
    "User",
    "UserSetting",
    "Analysis",
    "AuditLog",
    "get_db",
    "init_db",
    "engine",
    "Base",
    "get_user_by_email",
    "create_user",
    "get_user_settings",
    "update_user_setting",
    "get_user_setting",
    "create_analysis",
    "get_analysis_by_id",
    "get_user_analyses",
    "create_audit_log",
    "get_audit_logs",
    "get_user_settings_for_api",
    "update_user_settings_from_api",
]
