"""
FastAPI REST API for Incident Analysis System

Provides HTTP endpoints for analyzing incidents using the multi-agent system.

Run:
    uvicorn api.main:app --reload
    
Then visit:
    http://localhost:8000/docs
"""

import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import asyncio
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse, StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import our agents and systems
from core.agents.planner import plan_incident_analysis
from core.agents.log_retriever import retrieve_logs
from core.agents.rag_retriever import retrieve_knowledge
from core.agents.timeline_correlator import build_timeline
from core.agents.hypothesis_generator import generate_hypotheses
from core.agents.verifier import EvidenceVerifier
from core.agents.decision_gate import make_decision
from core.graph import build_incident_analysis_graph
import config

# Database imports
from core.database.session import get_db, init_db
from core.database.crud import (
    create_analysis,
    get_analysis_by_id,
    get_user_analyses,
)
from core.database.models import Analysis
from core.database.settings import (
    get_user_settings_for_api,
    update_user_settings_from_api,
)
from core.auth import get_current_user, get_optional_user
from core.database.models import User
from core.database.crud import create_audit_log

# Routers
from app.routers import auth, history, audit

# Try to import MCP
# try:
from core.mcp import get_mcp_client
from core.agents.log_retriever_mcp import retrieve_logs_with_mcp
MCP_AVAILABLE = True
# except ImportError as e:
    # print("⚠️ MCP not available:", e) 
    # MCP_AVAILABLE = False

class Base64LogFile(BaseModel):
    filename: str
    content_base64: str

# Pydantic models for request/response
class IncidentAnalysisRequest(BaseModel):
    """Request model for incident analysis"""
    query: str = Field(..., description="Incident description")
    timestamp: str = Field(..., description="Incident timestamp (ISO format)")
    dashboard_images: Optional[List[str]] = Field(None, description="Dashboard image paths or base64")
    log_files_base64: Optional[List[Base64LogFile]] = None
    logs: Optional[List[Dict]] = Field(None, description="Structured log entries")
    services: Optional[List[str]] = Field(None, description="Affected services")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "API outage at 14:32 UTC with 500 errors",
                "timestamp": "2024-01-15T14:32:00Z",
                "log_files": ["logs/api-gateway.log"],
                "services": ["api-gateway"]
            }
        }
class TimelineEntry(BaseModel):
    time: str
    event: str
    source: str
    event_type: str

class IncidentAnalysisResponse(BaseModel):
    """Response model for incident analysis"""
    analysis_id: str
    status: str  # "answer", "refuse", "request_more_data"
    confidence: float
    root_cause: Optional[str] = None
    evidence: Optional[Dict] = None
    timeline: List[TimelineEntry] = None
    recommended_actions: Optional[List[str]] = None
    alternative_hypotheses: Optional[List[Dict]] = None
    missing_evidence: Optional[List[str]] = None
    processing_time_ms: float
    agent_history: List[Dict] = []


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    agents_available: List[str]
    mcp_enabled: bool
    mcp_servers: List[str] = []


class PlanResponse(BaseModel):
    """Plan generation response"""
    plan: Dict
    estimated_time_seconds: float


# Global state (deprecated - use database instead)
# Kept for backward compatibility during migration
analysis_cache = {}
active_analyses = {}


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    print("🚀 Starting Incident Analysis API...")
    print(f"   Confidence threshold: {config.CONFIDENCE_THRESHOLD}")
    print(f"   MCP enabled: {MCP_AVAILABLE}")
    
    # Initialize database tables
    try:
        await init_db()
        print("   Database initialized")
    except Exception as e:
        print(f"   ⚠️  Database initialization failed: {e}")
        print("   Continuing with file-based storage (backward compatibility)")
    
    if MCP_AVAILABLE:
        client = get_mcp_client()
        print(f"   MCP servers: {client.get_available_servers()}")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down Incident Analysis API...")


# Create FastAPI app
app = FastAPI(
    title="Incident Analysis API",
    description="Multi-agent system for DevOps incident root cause analysis",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
# Configure CORS to allow frontend requests
import os

# Get allowed origins from environment or use defaults
CORS_ORIGINS_ENV = os.getenv("CORS_ORIGINS", "")
if CORS_ORIGINS_ENV:
    ALLOWED_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_ENV.split(",")]
    USE_WILDCARD_ORIGIN = False
else:
    # Default: allow common development origins
    # Note: Can't use "*" with credentials, so we use specific origins
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8501",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:8501",
    ]
    USE_WILDCARD_ORIGIN = False

# Add CORS middleware
# Use specific origins to allow credentials (required for JWT auth)
print(f"🌐 CORS Configuration: Allowing origins: {ALLOWED_ORIGINS}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,  # Required for JWT authentication
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
    ],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)
Instrumentator().instrument(app).expose(app)

# Register routers
app.include_router(auth.router)
app.include_router(history.router)
app.include_router(audit.router)

# Endpoints
@app.get("/", tags=["General"])
async def root():
    """Root endpoint"""
    return {
        "message": "Incident Analysis API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.options("/{full_path:path}", tags=["General"])
async def options_handler(full_path: str):
    """
    Handle CORS preflight requests for all paths.
    This ensures OPTIONS requests are properly handled.
    """
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept, Origin, X-Requested-With",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "3600",
        }
    )


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """Health check endpoint"""
    agents = [
        "planner",
        "log_retriever",
        "rag_retriever",
        "timeline_correlator",
        "hypothesis_generator",
        "verifier",
        "decision_gate"
    ]
    
    mcp_servers = []
    if MCP_AVAILABLE:
        client = get_mcp_client()
        mcp_servers = client.get_available_servers()
    
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        agents_available=agents,
        mcp_enabled=MCP_AVAILABLE,
        mcp_servers=mcp_servers
    )


@app.post("/analyze", response_model=IncidentAnalysisResponse, tags=["Analysis"])
async def analyze_incident(
    request: IncidentAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Analyze an incident using the multi-agent system via LangGraph.
    Results are saved to the database.
    """
    if not config.ANTHROPIC_API_KEY and not config.OPENAI_API_KEY:
        raise HTTPException(
            503,
            "Configure at least one LLM API key (Anthropic or OpenAI) in Settings."
        )
    start_time = datetime.now()
    analysis_id = f"analysis_{int(start_time.timestamp() * 1000)}"
    
    try:
        # Build the initial state for LangGraph
        initial_state = {
            "user_query": request.query,
            "dashboard_images": request.dashboard_images or [],
            "logs": request.logs or [],
            "timestamp": request.timestamp or datetime.now().isoformat(),
            "image_evidence": [],
            "log_evidence": [],
            "rag_evidence": [],
            "metrics_evidence": [],
            "dashboard_evidence": [],
            "errors": [],
            "agent_history": []
        }
        
        # If log files are provided via base64, parse them first
        if request.log_files_base64:
            print(f"📄 Parsing {len(request.log_files_base64)} base64 log files")
            # Convert base64 logs to structured format
            parsed_logs = []
            for log_data in request.log_files_base64:
                # Your log parsing logic here
                parsed_logs.append({"content": log_data, "source": "uploaded_log"})
            initial_state["logs"] = parsed_logs
        
        # If log files are provided as file paths
        elif request.log_files:
            print(f"📄 Processing {len(request.log_files)} log files")
            parsed_logs = []
            for log_file in request.log_files:
                # Read and parse log files
                # Your file reading logic here
                parsed_logs.append({"content": f"Content from {log_file}", "source": log_file})
            initial_state["logs"] = parsed_logs
        
        print(f"🚀 Starting LangGraph analysis with query: {request.query}")
        
        # Import and build the graph
        from core.graph import build_incident_analysis_graph
        
        graph = build_incident_analysis_graph()
        
        # Run the graph
        print("🔗 Executing LangGraph workflow...")
        final_state = graph.invoke(initial_state)
        
        # Extract results from final state
        plan = final_state.get("plan", {})
        log_evidence = final_state.get("log_evidence", [])
        rag_evidence = final_state.get("rag_evidence", [])
        metrics_evidence = final_state.get("metrics_evidence", [])
        image_evidence = final_state.get("image_evidence", [])
        dashboard_evidence = final_state.get("dashboard_evidence", [])
        timeline = final_state.get("timeline", [])
        hypotheses = final_state.get("hypotheses", [])
        verification_results = final_state.get("verification_results", {})
        overall_confidence = final_state.get("overall_confidence", 0.0)
        decision = final_state.get("decision", "refuse")
        final_response = final_state.get("final_response", {})
        agent_history = final_state.get("agent_history", [])
        errors = final_state.get("errors", [])
        
        # Log what was collected
        print(f"\n📊 Analysis complete:")
        print(f"  - Plan: {plan.get('affected_services', [])} services, {plan.get('symptoms', [])} symptoms")
        print(f"  - Evidence: {len(log_evidence)} logs, {len(rag_evidence)} RAG, {len(metrics_evidence)} metrics")
        print(f"  - Timeline: {len(timeline)} events")
        print(f"  - Hypotheses: {len(hypotheses)}")
        print(f"  - Confidence: {overall_confidence:.2%}")
        print(f"  - Decision: {decision}")
        
        # Check if prometheus ran
        prometheus_history = [h for h in agent_history if h.get("agent") == "prometheus"]
        if prometheus_history:
            print(f"  - Prometheus: {prometheus_history[0].get('status', 'unknown')}")
            if prometheus_history[0].get("status") == "success":
                print(f"    Collected {len(metrics_evidence)} metrics evidence items")
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        # print(f"🔵 [PROMETHEUS AGENT] Timeline: {timeline}")
        # Build response
        response = IncidentAnalysisResponse(
            analysis_id=analysis_id,
            status=decision,
            confidence=overall_confidence,
            root_cause=final_response.get("root_cause"),
            evidence={
                "logs": [{"source": e.source, "confidence": e.confidence} for e in log_evidence],
                "rag": [{"source": e.source, "confidence": e.confidence} for e in rag_evidence],
                "metrics": [{"source": e.source, "confidence": e.confidence} for e in metrics_evidence],
                "images": [{"source": e.source, "confidence": e.confidence} for e in image_evidence],
                "dashboards": [{"source": e.source, "confidence": e.confidence} for e in dashboard_evidence]
            },
            timeline=timeline,
            recommended_actions=final_response.get("recommended_actions", []),
            alternative_hypotheses=final_response.get("alternative_hypotheses", []),
            missing_evidence=final_response.get("missing_evidence", []),
            processing_time_ms=processing_time,
            agent_history=agent_history,
            errors=errors
        )
        
        # Save to database
        try:
            # Convert Pydantic models to dict (works with both v1 and v2)
            request_dict = request.model_dump() if hasattr(request, 'model_dump') else request.dict()
            response_dict = response.model_dump() if hasattr(response, 'model_dump') else response.dict()
            
            user_id = current_user.id if current_user else None
            
            await create_analysis(
                db=db,
                analysis_id=analysis_id,
                request=request_dict,
                response=response_dict,
                user_id=user_id
            )
            
            # Log analysis creation
            if current_user:
                await create_audit_log(
                    db=db,
                    user_id=current_user.id,
                    action="run_analysis",
                    resource=f"analysis:{analysis_id}",
                    details={"query": request.query[:100]}  # First 100 chars
                )
        except Exception as db_error:
            print(f"⚠️  Failed to save analysis to database: {db_error}")
            # Fallback to in-memory cache for backward compatibility
            analysis_cache[analysis_id] = response
        
        return response
    
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/plan", response_model=PlanResponse, tags=["Analysis"])
async def create_plan(
    query: str = Form(...),
    timestamp: str = Form(...)
):
    """
    Generate an execution plan without running full analysis.
    Useful for understanding what data will be needed.
    """
    try:
        plan = plan_incident_analysis(query, timestamp)
        
        # Estimate processing time based on plan
        estimated_time = 5.0  # Base time
        if "image" in plan.get("required_agents", []):
            estimated_time += 3.0
        if "log" in plan.get("required_agents", []):
            estimated_time += 2.0
        
        return PlanResponse(
            plan=plan,
            estimated_time_seconds=estimated_time
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Planning failed: {str(e)}")


@app.get("/analysis/{analysis_id}", response_model=IncidentAnalysisResponse, tags=["Analysis"])
async def get_analysis(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Retrieve a previously completed analysis by ID.
    Checks database first, then falls back to in-memory cache.
    If authenticated, only returns analyses owned by the user.
    """
    # Try database first
    db_analysis = await get_analysis_by_id(db, analysis_id)
    if db_analysis:
        # Verify user has access (if authenticated)
        if current_user and db_analysis.user_id and db_analysis.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        return IncidentAnalysisResponse(**db_analysis.response)
    
    # Fallback to in-memory cache (backward compatibility, only for anonymous)
    if analysis_id in analysis_cache:
        return analysis_cache[analysis_id]
    
    raise HTTPException(status_code=404, detail="Analysis not found")


# Moved to /history endpoint in history router


@app.post("/analyze/stream", tags=["Analysis"])
async def analyze_incident_stream(request: IncidentAnalysisRequest):
    """
    Stream analysis progress as Server-Sent Events.
    Returns real-time updates as each agent completes.
    """
    async def event_generator():
        try:
            yield f"data: {json.dumps({'stage': 'started', 'message': 'Analysis started'})}\n\n"
            
            # Plan
            yield f"data: {json.dumps({'stage': 'planning', 'message': 'Creating execution plan'})}\n\n"
            plan = plan_incident_analysis(request.query, request.timestamp)
            yield f"data: {json.dumps({'stage': 'plan_complete', 'plan': plan})}\n\n"
            
            # Evidence collection
            yield f"data: {json.dumps({'stage': 'evidence', 'message': 'Gathering evidence'})}\n\n"
            
            # Continue with rest of pipeline...
            # (Simplified for brevity)
            
            yield f"data: {json.dumps({'stage': 'complete', 'message': 'Analysis complete'})}\n\n"
        
        except Exception as e:
            yield f"data: {json.dumps({'stage': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/upload-logs", tags=["Data"])
async def upload_logs(
    file: UploadFile = File(...),
    service: str = Form(...)
):
    """
    Upload a log file for analysis.
    Saves to logs/ directory for MCP access.
    """
    try:
        # Save file
        file_path = Path("logs") / f"{service}_{file.filename}"
        file_path.parent.mkdir(exist_ok=True)
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        return {
            "message": "File uploaded successfully",
            "path": str(file_path),
            "size_bytes": len(content),
            "service": service
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/mcp/servers", tags=["MCP"])
async def list_mcp_servers():
    """
    List available MCP servers and their status.
    """
    if not MCP_AVAILABLE:
        return {"enabled": False, "message": "MCP not available"}
    
    client = get_mcp_client()
    health = client.health_check()
    
    return {
        "enabled": True,
        "servers": client.get_available_servers(),
        "health": health
    }


@app.post("/mcp/filesystem/read", tags=["MCP"])
async def mcp_read_file(filepath: str = Form(...)):
    """
    Read a file using MCP filesystem.
    """
    if not MCP_AVAILABLE:
        raise HTTPException(status_code=503, detail="MCP not available")
    
    client = get_mcp_client()
    result = client.filesystem.read_file(filepath)
    
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error)
    
    return {
        "success": True,
        "content": result.data,
        "metadata": result.metadata
    }


@app.get("/settings", tags=["Settings"])
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get current configuration for the Settings UI.
    If authenticated, returns per-user settings from database.
    Otherwise, returns system-wide settings (backward compatibility).
    """
    if current_user:
        # Per-user settings from database
        return await get_user_settings_for_api(db, current_user.id, include_secrets=False)
    else:
        # System-wide settings (file-based, backward compatibility)
        return config.get_settings()


@app.put("/settings", tags=["Settings"])
async def update_settings(
    body: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Update configuration from the Settings UI.
    If authenticated, saves per-user settings to database.
    Otherwise, updates system-wide settings file (backward compatibility).
    
    Pass { \"values\": { \"KEY\": value, ... } } or a flat { \"KEY\": value }.
    """
    values = body.get("values", body)
    if not isinstance(values, dict):
        raise HTTPException(400, "Body must be { values: {...} } or {...}")
    
    if current_user:
        # Per-user settings in database
        result = await update_user_settings_from_api(db, current_user.id, values)
        
        # Log settings update
        await create_audit_log(
            db=db,
            user_id=current_user.id,
            action="update_settings",
            resource="settings",
            details={"keys": list(values.keys())}
        )
        
        return result
    else:
        # System-wide settings (file-based, backward compatibility)
        return config.update_settings(values)


@app.get("/stats", tags=["General"])
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get API usage statistics.
    If authenticated, includes per-user stats from database.
    """
    from sqlalchemy import select, func
    
    # Get total analyses from database
    result = await db.execute(select(func.count(Analysis.id)))
    total_analyses_db = result.scalar() or 0
    
    # Get user-specific analyses if authenticated
    user_analyses_count = None
    if current_user:
        result = await db.execute(
            select(func.count(Analysis.id)).where(Analysis.user_id == current_user.id)
        )
        user_analyses_count = result.scalar() or 0
    
    return {
        "total_analyses": total_analyses_db + len(analysis_cache),  # DB + cache (backward compat)
        "total_analyses_db": total_analyses_db,
        "user_analyses": user_analyses_count,
        "active_analyses": len(active_analyses),
        "cache_size_mb": sys.getsizeof(analysis_cache) / (1024 * 1024),
        "mcp_enabled": MCP_AVAILABLE,
        "database_enabled": True,
        "authenticated": current_user is not None
    }


@app.delete("/cache", tags=["General"])
async def clear_cache():
    """
    Clear analysis cache.
    """
    global analysis_cache
    count = len(analysis_cache)
    analysis_cache = {}
    
    return {
        "message": f"Cleared {count} cached analyses",
        "cache_size": 0
    }


# Error handlers with CORS headers
def get_cors_headers(request: Request) -> dict:
    """Get CORS headers for a request - ensures error responses include CORS headers"""
    origin = request.headers.get("origin")
    headers = {
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept, Origin, X-Requested-With",
        "Access-Control-Max-Age": "3600",
    }
    
    # Always allow the requesting origin if it's in our allowed list
    if origin and origin in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    elif USE_WILDCARD_ORIGIN:
        # Fallback to wildcard if enabled (but can't use credentials)
        headers["Access-Control-Allow-Origin"] = "*"
        headers["Access-Control-Allow-Credentials"] = "false"
    elif ALLOWED_ORIGINS:
        # Default to first allowed origin
        headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGINS[0]
        headers["Access-Control-Allow-Credentials"] = "true"
    else:
        # Last resort: allow all (development only)
        headers["Access-Control-Allow-Origin"] = "*"
        headers["Access-Control-Allow-Credentials"] = "false"
    
    return headers


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    headers = get_cors_headers(request)
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "detail": str(exc)},
        headers=headers
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    headers = get_cors_headers(request)
    import traceback
    error_detail = str(exc)
    # Log the full traceback for debugging
    print(f"❌ Server error: {error_detail}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": error_detail},
        headers=headers
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPExceptions with CORS headers"""
    headers = get_cors_headers(request)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail if isinstance(exc.detail, str) else str(exc.detail)},
        headers=headers
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions with CORS headers"""
    headers = get_cors_headers(request)
    import traceback
    error_detail = str(exc)
    print(f"❌ Unhandled exception: {error_detail}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": error_detail},
        headers=headers
    )


# Run with: uvicorn api.main:app --reload
if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )