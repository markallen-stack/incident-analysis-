"""
FastAPI REST API for Incident Analysis System

Provides HTTP endpoints for analyzing incidents using the multi-agent system.

Usage:
    # Start server
    uvicorn api.main:app --reload
    
    # Use client
    from api.client import IncidentAnalysisClient
    client = IncidentAnalysisClient()
    result = client.analyze_incident(...)
"""

from app.client import IncidentAnalysisClient

__all__ = ['IncidentAnalysisClient']
__version__ = '1.0.0'