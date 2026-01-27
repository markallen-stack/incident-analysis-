"""
Analysis history endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pydantic import BaseModel

from core.auth import get_current_user
from core.database.crud import (
    get_user_analyses,
    get_analysis_by_id,
    delete_analysis,
    create_audit_log,
)
from core.database.models import User, Analysis
from core.database.session import get_db

router = APIRouter(prefix="/history", tags=["History"])


class AnalysisSummary(BaseModel):
    """Summary of an analysis for listing"""
    id: str
    analysis_id: str
    status: str
    confidence: float
    root_cause: Optional[str]
    processing_time_ms: float
    created_at: str

    class Config:
        from_attributes = True


class AnalysisListResponse(BaseModel):
    analyses: List[AnalysisSummary]
    total: int
    limit: int
    offset: int


@router.get("", response_model=AnalysisListResponse)
async def list_analyses(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List analyses for the current user.
    Supports pagination and status filtering.
    """
    analyses = await get_user_analyses(
        db=db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        status=status
    )
    
    summaries = [
        AnalysisSummary(
            id=analysis.id,
            analysis_id=analysis.analysis_id,
            status=analysis.status,
            confidence=analysis.confidence,
            root_cause=analysis.root_cause,
            processing_time_ms=analysis.processing_time_ms,
            created_at=analysis.created_at.isoformat()
        )
        for analysis in analyses
    ]
    
    return AnalysisListResponse(
        analyses=summaries,
        total=len(summaries),
        limit=limit,
        offset=offset
    )


@router.get("/{analysis_id}", response_model=dict)
async def get_analysis_detail(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get full details of a specific analysis.
    Only returns analyses owned by the current user.
    """
    analysis = await get_analysis_by_id(db, analysis_id)
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Verify ownership
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Log access
    await create_audit_log(
        db=db,
        user_id=current_user.id,
        action="view_analysis",
        resource=f"analysis:{analysis_id}",
        details={"analysis_id": analysis_id}
    )
    
    return {
        "id": analysis.id,
        "analysis_id": analysis.analysis_id,
        "status": analysis.status,
        "confidence": analysis.confidence,
        "root_cause": analysis.root_cause,
        "processing_time_ms": analysis.processing_time_ms,
        "created_at": analysis.created_at.isoformat(),
        "request": analysis.request,
        "response": analysis.response,
    }


@router.delete("/{analysis_id}", status_code=204)
async def delete_analysis_endpoint(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete an analysis.
    Only allows deletion of analyses owned by the current user.
    """
    analysis = await get_analysis_by_id(db, analysis_id)
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Verify ownership
    if analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Delete
    deleted = await delete_analysis(db, analysis_id)
    
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete analysis")
    
    # Log deletion
    await create_audit_log(
        db=db,
        user_id=current_user.id,
        action="delete_analysis",
        resource=f"analysis:{analysis_id}",
        details={"analysis_id": analysis_id}
    )
    
    return None
