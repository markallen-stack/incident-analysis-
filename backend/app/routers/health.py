"""
Health check endpoints.
"""

from fastapi import APIRouter
from datetime import datetime
import logging
import sys
sys.path.insert(0, '/Users/eliteit/Documents/incident_rag/backend')

import config
from app.schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    Returns system status and available models.
    """
    models_available = {
        "openai": config.OPENAI_API_KEY is not None,
        "anthropic": config.ANTHROPIC_API_KEY is not None,
        "vision": config.VISION_MODEL is not None,
        "embedding": config.EMBEDDING_MODEL is not None,
    }
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0",
        models_available=models_available
    )


@router.get("/config")
async def get_config():
    """
    Get current system configuration.
    """
    return {
        "primary_llm": config.PRIMARY_LLM,
        "vision_model": config.VISION_MODEL,
        "embedding_model": config.EMBEDDING_MODEL,
        "confidence_threshold": config.CONFIDENCE_THRESHOLD,
        "min_evidence_sources": config.MIN_EVIDENCE_SOURCES,
        "max_hypotheses": config.MAX_HYPOTHESES,
        "debug_mode": config.DEBUG_MODE,
    }


@router.get("/ready")
async def readiness_check():
    """
    Readiness check - returns 200 when ready to accept requests.
    """
    # Check if critical paths exist
    vector_db_available = config.VECTOR_DB_PATH.exists()
    
    return {
        "ready": vector_db_available,
        "vector_db_available": vector_db_available,
        "timestamp": datetime.utcnow().isoformat()
    }
