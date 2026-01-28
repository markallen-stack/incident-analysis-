"""
Custom CORS middleware for better control and debugging.
"""

from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import os
from typing import List


def get_cors_config():
    """
    Get CORS configuration from environment or use defaults.
    """
    # Get allowed origins from environment
    cors_origins_env = os.getenv("CORS_ORIGINS", "")
    
    if cors_origins_env:
        # Use specific origins from environment
        allowed_origins = [origin.strip() for origin in cors_origins_env.split(",")]
    else:
        # Default: allow common development origins
        allowed_origins = [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:8501",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:8501",
            "https://frontend-production-45bf.up.railway.app"
        ]
    
    # In development, also allow all origins if CORS_ORIGINS is not set
    if not cors_origins_env and os.getenv("ENV", "development") == "development":
        allowed_origins = ["*"]
    
    return {
        "allow_origins": allowed_origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": [
            "Content-Type",
            "Authorization",
            "Accept",
            "Origin",
            "X-Requested-With",
            "Access-Control-Request-Method",
            "Access-Control-Request-Headers",
        ],
        "expose_headers": ["*"],
        "max_age": 3600,
    }


class DebugCORSMiddleware(BaseHTTPMiddleware):
    """
    Debug CORS middleware that logs CORS-related requests.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Handle preflight OPTIONS requests
        if request.method == "OPTIONS":
            origin = request.headers.get("origin")
            response = Response()
            
            cors_config = get_cors_config()
            allowed_origins = cors_config["allow_origins"]
            
            # Check if origin is allowed
            if origin and (origin in allowed_origins or "*" in allowed_origins):
                response.headers["Access-Control-Allow-Origin"] = origin if "*" not in allowed_origins else "*"
                response.headers["Access-Control-Allow-Methods"] = ", ".join(cors_config["allow_methods"])
                response.headers["Access-Control-Allow-Headers"] = ", ".join(cors_config["allow_headers"])
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Max-Age"] = str(cors_config["max_age"])
            
            return response
        
        # For regular requests, add CORS headers
        response = await call_next(request)
        origin = request.headers.get("origin")
        
        if origin:
            cors_config = get_cors_config()
            allowed_origins = cors_config["allow_origins"]
            
            if origin in allowed_origins or "*" in allowed_origins:
                response.headers["Access-Control-Allow-Origin"] = origin if "*" not in allowed_origins else "*"
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Expose-Headers"] = ", ".join(cors_config["expose_headers"])
        
        return response
