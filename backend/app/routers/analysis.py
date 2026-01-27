"""
Incident analysis endpoints.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional
from datetime import datetime
import logging
import sys
import uuid
sys.path.insert(0, '/Users/eliteit/Documents/incident_rag/backend')

from app.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisDecision,
    EvidenceSchema,
    HypothesisSchema,
    TimelineEventSchema,
)
from core.agents.image_analyzer import analyze_dashboards
from core.agents.log_retriever import retrieve_logs
from core.agents.hypothesis_generator import generate_hypotheses
from core.agents.verifier import EvidenceVerifier, VerificationResult, Verdict

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory store for analysis results (replace with database in production)
analysis_results = {}


@router.post("/", response_model=AnalysisResponse)
async def analyze_incident(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks
):
    """
    Analyze an incident using the RAG system.
    
    This endpoint:
    1. Extracts metrics from dashboard images
    2. Correlates logs with timeline
    3. Generates root cause hypotheses
    4. Verifies hypotheses against evidence
    5. Returns conclusions
    """
    try:
        request_id = str(uuid.uuid4())
        logger.info(f"Starting analysis {request_id} for query: {request.query}")
        
        # Step 1: Analyze dashboard images
        image_evidence = []
        if request.dashboard_images:
            logger.info(f"Analyzing {len(request.dashboard_images)} dashboard images...")
            image_evidence = analyze_dashboards(
                images=request.dashboard_images,
                time_window=request.time_window
            )
            logger.info(f"Extracted {len(image_evidence)} observations from images")
        
        # Step 2: Retrieve and correlate logs
        log_evidence = []
        timeline = []
        if request.logs:
            logger.info(f"Processing {len(request.logs)} log entries...")
            # Extract unique services from logs
            services = list(set(log.get("service", "unknown") for log in request.logs))
            log_evidence = retrieve_logs(
                logs=request.logs,
                time_window={"start": request.time_window.split("-")[0] if request.time_window else None, 
                             "end": request.time_window.split("-")[1] if request.time_window else None},
                services=services
            )
            
            # Create simple timeline from logs
            timeline = [
                {
                    "time": log.get("timestamp", "unknown"),
                    "event": log.get("message", ""),
                    "source": "log",
                    "confidence": 0.8 if log.get("level") == "ERROR" else 0.6
                }
                for log in request.logs
            ]
            
            logger.info(f"Extracted {len(log_evidence)} log observations")
            logger.info(f"Built timeline with {len(timeline)} events")
        
        # Step 3: Generate hypotheses
        all_evidence = image_evidence + log_evidence
        hypotheses = []
        if all_evidence or timeline:
            logger.info(f"Generating hypotheses from {len(all_evidence)} evidence items...")
            
            # Create correlations from timeline with proper format
            correlations = [
                {
                    "pattern": f"{timeline[i].get('event', '')} → {timeline[i+1].get('event', '')}",
                    "strength": 0.7,
                    "temporal_distance": "minutes",
                    "confidence": 0.7
                }
                for i in range(len(timeline) - 1) if len(timeline) > 1
            ]
            
            # Group evidence by source type
            evidence_by_source = {"image": [], "log": [], "historical": [], "runbook": []}
            for ev in all_evidence:
                source_type = ev.source if ev.source in evidence_by_source else "log"
                evidence_by_source[source_type].append(ev)
            
            hypotheses = generate_hypotheses(
                timeline=timeline,
                correlations=correlations,
                all_evidence=evidence_by_source
            )
            logger.info(f"Generated {len(hypotheses)} hypotheses")
        
        # Step 4: Verify hypotheses
        verified_results = []
        best_hypothesis = None
        overall_confidence = 0.0
        
        if hypotheses:
            logger.info(f"Verifying {len(hypotheses)} hypotheses...")
            verifier = EvidenceVerifier()
            
            # Group evidence by source type
            evidence_by_source = {"image": [], "log": [], "historical": [], "runbook": []}
            for ev in all_evidence:
                source_type = ev.source if ev.source in evidence_by_source else "log"
                evidence_by_source[source_type].append(ev)
            
            # Verify hypotheses
            verified_dict, overall_confidence = verifier.verify_hypotheses(
                hypotheses=hypotheses,
                evidence=evidence_by_source,
                timeline=timeline
            )
            
            verified_results = [
                {
                    "hypothesis_id": result.hypothesis_id,
                    "verdict": result.verdict.value if hasattr(result.verdict, 'value') else str(result.verdict),
                    "confidence": result.confidence,
                    "evidence_summary": result.evidence_summary,
                    "independent_sources": result.independent_sources,
                    "contradictions": result.contradictions
                }
                for result in verified_dict.values()
            ]
            
            # Find best supported hypothesis
            for hyp_id, result in verified_dict.items():
                if hasattr(result, 'confidence') and result.confidence > overall_confidence:
                    overall_confidence = result.confidence
                    best_hypothesis = hyp_id
            
            logger.info(f"Verification complete. Best confidence: {overall_confidence:.2f}")
        
        # Determine decision
        decision = AnalysisDecision.REFUSE
        root_cause = None
        recommendations = []
        
        if overall_confidence >= 0.8 and best_hypothesis:
            decision = AnalysisDecision.ANSWER
            root_cause = f"Hypothesis {best_hypothesis}"
            recommendations = ["Monitor affected components", "Review error logs"]
        elif overall_confidence >= 0.5:
            decision = AnalysisDecision.REQUEST_MORE_DATA
            recommendations = ["Collect additional logs", "Provide more dashboard data"]
        else:
            recommendations = ["Unable to determine root cause with high confidence"]
        
        # Convert evidence to schema
        evidence_schemas = [
            EvidenceSchema(
                source=ev.source,
                content=ev.content,
                timestamp=ev.timestamp,
                confidence=ev.confidence,
                metadata=ev.metadata
            )
            for ev in all_evidence
        ]
        
        # Convert timeline to schema
        timeline_schemas = [
            TimelineEventSchema(
                time=event.get("time", "unknown"),
                event=event.get("event", ""),
                source=event.get("source", "log"),
                confidence=event.get("confidence", 0.7)
            )
            for event in timeline
        ]
        
        # Convert hypotheses to schema
        hypotheses_schemas = [
            HypothesisSchema(
                id=h.id,
                root_cause=h.root_cause,
                plausibility=h.plausibility,
                supporting_evidence=h.supporting_evidence,
                required_evidence=h.required_evidence,
                would_refute=h.would_refute
            )
            for h in hypotheses
        ]
        
        # Create response
        response = AnalysisResponse(
            request_id=request_id,
            status="completed",
            decision=decision,
            overall_confidence=overall_confidence,
            root_cause=root_cause,
            evidence=evidence_schemas,
            timeline=timeline_schemas,
            hypotheses=hypotheses_schemas,
            recommendations=recommendations,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        
        # Store result
        analysis_results[request_id] = response
        logger.info(f"Analysis {request_id} completed successfully")
        
        return response
    
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@router.get("/{request_id}", response_model=AnalysisResponse)
async def get_analysis_result(request_id: str):
    """
    Retrieve a previous analysis result.
    """
    if request_id not in analysis_results:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis {request_id} not found"
        )
    
    return analysis_results[request_id]


@router.get("/")
async def list_analyses():
    """
    List all completed analyses.
    """
    return {
        "total": len(analysis_results),
        "analyses": [
            {
                "request_id": aid,
                "created_at": result.created_at,
                "decision": result.decision,
                "confidence": result.overall_confidence
            }
            for aid, result in analysis_results.items()
        ]
    }
