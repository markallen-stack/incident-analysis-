"""
Image analysis endpoints.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel
import logging
import sys
sys.path.insert(0, '/Users/eliteit/Documents/incident_rag/backend')

from core.agents.image_analyzer import analyze_dashboards

logger = logging.getLogger(__name__)
router = APIRouter()


class ImageAnalysisRequest(BaseModel):
    """Request to analyze an image"""
    image_data: str
    time_window: Optional[str] = None


@router.post("/analyze")
async def analyze_image(request: ImageAnalysisRequest):
    """
    Analyze a single dashboard image.
    
    Extracts:
    - Metric names and values
    - Anomalies and patterns
    - Temporal characteristics
    """
    try:
        logger.info(f"Analyzing image (size: {len(request.image_data)} bytes)")
        
        # Analyze the image
        evidence = analyze_dashboards(
            images=[request.image_data],
            time_window=request.time_window
        )
        
        # Convert to response format
        results = [
            {
                "source": ev.source,
                "content": ev.content,
                "timestamp": ev.timestamp,
                "confidence": ev.confidence,
                "metadata": ev.metadata
            }
            for ev in evidence
        ]
        
        logger.info(f"Image analysis complete. Found {len(results)} observations")
        return results
    
    except Exception as e:
        logger.error(f"Image analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Image analysis failed: {str(e)}"
        )


class BatchImageRequest(BaseModel):
    """Request to analyze multiple images"""
    images: list
    time_window: Optional[str] = None


@router.post("/batch")
async def analyze_multiple_images(request: BatchImageRequest):
    """
    Analyze multiple dashboard images in batch.
    """
    try:
        logger.info(f"Analyzing {len(request.images)} images in batch...")
        
        evidence = analyze_dashboards(
            images=request.images,
            time_window=request.time_window
        )
        
        # Group evidence by image
        by_image = {}
        for ev in evidence:
            img_path = ev.metadata.get("image_path", "unknown")
            if img_path not in by_image:
                by_image[img_path] = []
            by_image[img_path].append({
                "content": ev.content,
                "confidence": ev.confidence,
                "metadata": ev.metadata
            })
        
        logger.info(f"Batch analysis complete")
        return by_image
    
    except Exception as e:
        logger.error(f"Batch image analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Batch analysis failed: {str(e)}"
        )


@router.get("/supported-formats")
async def get_supported_formats():
    """
    Get list of supported image formats.
    """
    return {
        "formats": ["image/png", "image/jpeg", "image/jpg"],
        "max_size_mb": 20,
        "recommended_resolution": "1920x1080"
    }
