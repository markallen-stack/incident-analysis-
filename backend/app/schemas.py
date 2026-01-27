"""
Pydantic schemas for API request/response validation.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum


class AnalysisDecision(str, Enum):
    """Decision outcome from analysis"""
    ANSWER = "answer"
    REFUSE = "refuse"
    REQUEST_MORE_DATA = "request_more_data"


class EvidenceSchema(BaseModel):
    """Single piece of evidence"""
    source: str
    content: str
    timestamp: str
    confidence: float
    metadata: Dict = Field(default_factory=dict)


class HypothesisSchema(BaseModel):
    """Root cause hypothesis"""
    id: str
    root_cause: str
    plausibility: float
    supporting_evidence: List[str]
    required_evidence: List[str]
    would_refute: List[str]


class TimelineEventSchema(BaseModel):
    """Event in the incident timeline"""
    time: str
    event: str
    source: str
    confidence: float


class AnalysisRequest(BaseModel):
    """Request to analyze an incident"""
    query: str = Field(..., description="Natural language description of the incident")
    dashboard_images: List[str] = Field(
        default_factory=list,
        description="List of base64 encoded images or file paths"
    )
    logs: List[Dict] = Field(
        default_factory=list,
        description="Raw logs from the system"
    )
    timestamp: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp of the incident"
    )
    time_window: Optional[str] = Field(
        default=None,
        description="Time window for analysis (HH:MM-HH:MM)"
    )


class AnalysisResponse(BaseModel):
    """Response from incident analysis"""
    request_id: str
    status: str
    decision: AnalysisDecision
    overall_confidence: float
    root_cause: Optional[str]
    evidence: List[EvidenceSchema]
    timeline: List[TimelineEventSchema]
    hypotheses: List[HypothesisSchema]
    recommendations: List[str]
    created_at: datetime
    completed_at: Optional[datetime] = None


class ImageAnalysisRequest(BaseModel):
    """Request to analyze a single image"""
    image_data: str = Field(..., description="Base64 encoded image or file path")
    time_window: Optional[str] = Field(
        default=None,
        description="Time window context (HH:MM-HH:MM)"
    )


class ImageAnalysisResponse(BaseModel):
    """Response from image analysis"""
    image_path: str
    metrics_observed: List[Dict]
    visual_anomalies: List[str]
    confidence: float


class IncidentQueryRequest(BaseModel):
    """Request to query historical incidents"""
    query: str = Field(..., description="Search query for incidents")
    limit: int = Field(default=10, description="Maximum results to return")
    min_confidence: float = Field(default=0.7, description="Minimum confidence threshold")


class IncidentQueryResponse(BaseModel):
    """Response from incident query"""
    total_results: int
    incidents: List[Dict]
    search_query: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str
    models_available: Dict[str, bool]
