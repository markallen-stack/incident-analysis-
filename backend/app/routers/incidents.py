"""
Incident query and historical data endpoints.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
import logging
import json
import sys
sys.path.insert(0, '/Users/eliteit/Documents/incident_rag/backend')

import config
from app.schemas import IncidentQueryRequest, IncidentQueryResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/search", response_model=IncidentQueryResponse)
async def search_incidents_endpoint(request: IncidentQueryRequest):
    """
    Search for historical incidents similar to the current one.
    
    Uses semantic search over the FAISS vector database to find
    relevant past incidents and their resolutions.
    """
    try:
        logger.info(f"Searching incidents for: {request.query}")
        
        # Try to import and use the search function if available
        try:
            from core.vector_db.query import search_incidents
            results = search_incidents(
                query=request.query,
                limit=request.limit,
                min_confidence=request.min_confidence
            )
        except ImportError:
            # Fallback: return empty results or mock data
            logger.warning("Vector DB search not available, using mock results")
            results = []
        
        logger.info(f"Found {len(results)} relevant incidents")
        
        return IncidentQueryResponse(
            total_results=len(results),
            incidents=results,
            search_query=request.query
        )
    
    except Exception as e:
        logger.error(f"Incident search failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/historical")
async def get_historical_incidents():
    """
    Get list of historical incidents from the database.
    """
    try:
        incidents_file = config.HISTORICAL_INCIDENTS_DIR / "incidents_db.json"
        
        if not incidents_file.exists():
            return {
                "total": 0,
                "incidents": []
            }
        
        with open(incidents_file) as f:
            data = json.load(f)
        
        incidents = data.get("incidents", [])
        logger.info(f"Retrieved {len(incidents)} historical incidents")
        
        return {
            "total": len(incidents),
            "incidents": incidents
        }
    
    except Exception as e:
        logger.error(f"Failed to retrieve historical incidents: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve incidents: {str(e)}"
        )


@router.get("/{incident_id}")
async def get_incident_details(incident_id: str):
    """
    Get details of a specific incident.
    """
    try:
        incidents_file = config.HISTORICAL_INCIDENTS_DIR / "incidents_db.json"
        
        if not incidents_file.exists():
            raise HTTPException(status_code=404, detail="Incident not found")
        
        with open(incidents_file) as f:
            data = json.load(f)
        
        incidents = data.get("incidents", [])
        
        # Find matching incident
        for incident in incidents:
            if incident.get("id") == incident_id:
                return incident
        
        raise HTTPException(status_code=404, detail="Incident not found")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve incident {incident_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve incident: {str(e)}"
        )


@router.get("/stats/summary")
async def get_incident_statistics():
    """
    Get statistics about historical incidents.
    """
    try:
        incidents_file = config.HISTORICAL_INCIDENTS_DIR / "incidents_db.json"
        
        if not incidents_file.exists():
            return {
                "total_incidents": 0,
                "by_severity": {},
                "by_component": {}
            }
        
        try:
            with open(incidents_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, ValueError):
            # File is empty or invalid JSON
            return {
                "total_incidents": 0,
                "by_severity": {},
                "by_component": {}
            }
        
        incidents = data.get("incidents", []) if isinstance(data, dict) else []
        
        # Calculate statistics
        by_severity = {}
        by_component = {}
        
        for incident in incidents:
            severity = incident.get("severity", "unknown")
            component = incident.get("component", "unknown")
            
            by_severity[severity] = by_severity.get(severity, 0) + 1
            by_component[component] = by_component.get(component, 0) + 1
        
        return {
            "total_incidents": len(incidents),
            "by_severity": by_severity,
            "by_component": by_component
        }
    
    except Exception as e:
        logger.error(f"Failed to get statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statistics: {str(e)}"
        )
