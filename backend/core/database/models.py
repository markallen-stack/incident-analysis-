"""
SQLAlchemy models for Incident RAG database.
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid

Base = declarative_base()


class User(Base):
    """User account model"""
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    settings = relationship("UserSetting", back_populates="user", cascade="all, delete-orphan")
    analyses = relationship("Analysis", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"


class UserSetting(Base):
    """Per-user configuration settings"""
    __tablename__ = "user_settings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String, nullable=False, index=True)
    value = Column(Text, nullable=True)  # Store as JSON string or plain text
    value_type = Column(String, nullable=False, default="string")  # string, int, float, bool, path, json
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="settings")

    # Unique constraint: one setting key per user
    __table_args__ = (
        Index("ix_user_settings_user_key", "user_id", "key", unique=True),
    )

    def __repr__(self):
        return f"<UserSetting(user_id={self.user_id}, key={self.key}, value={self.value})>"


class Analysis(Base):
    """Incident analysis results"""
    __tablename__ = "analyses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id = Column(String, unique=True, index=True, nullable=False)  # e.g., "analysis_1234567890"
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)  # Nullable for anonymous
    request = Column(JSON, nullable=False)  # IncidentAnalysisRequest as JSON
    response = Column(JSON, nullable=False)  # IncidentAnalysisResponse as JSON
    status = Column(String, nullable=False, index=True)  # "answer", "refuse", "request_more_data"
    confidence = Column(Float, nullable=False, index=True)
    root_cause = Column(Text, nullable=True)
    processing_time_ms = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="analyses")

    # Indexes for common queries
    __table_args__ = (
        Index("ix_analyses_user_created", "user_id", "created_at"),
        Index("ix_analyses_status_confidence", "status", "confidence"),
    )

    def __repr__(self):
        return f"<Analysis(id={self.id}, analysis_id={self.analysis_id}, user_id={self.user_id}, status={self.status})>"


class AuditLog(Base):
    """Audit trail for user actions"""
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String, nullable=False, index=True)  # "login", "run_analysis", "update_settings", etc.
    resource = Column(String, nullable=True)  # "analysis:123", "settings", etc.
    details = Column(JSON, nullable=True)  # Additional context
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    # Indexes
    __table_args__ = (
        Index("ix_audit_logs_user_action", "user_id", "action", "created_at"),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, user_id={self.user_id}, action={self.action})>"
