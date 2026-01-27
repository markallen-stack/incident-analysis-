# mcp_servers/rag_server.py
from mcp.server import Server
from mcp.server.models import InitializationOptions
import asyncio
from typing import Dict, Any
import json
import os

# Simple in-memory RAG for demo (use vector DB in production)
PAST_INCIDENTS = [
    {
        "id": "INC-001",
        "description": "Database connection pool exhaustion",
        "symptoms": ["High latency", "Connection errors", "Increased CPU"],
        "root_cause": "Connection pool size too small for traffic spike",
        "resolution": "Increased connection pool from 50 to 200",
        "service": "payment-service",
        "timestamp": "2024-01-15T14:30:00Z"
    },
    {
        "id": "INC-002",
        "description": "Memory leak in user service",
        "symptoms": ["OOM kills", "Restart loops", "Growing RSS"],
        "root_cause": "Unbounded cache growth",
        "resolution": "Added LRU cache with size limit",
        "service": "user-service",
        "timestamp": "2024-01-18T09:15:00Z"
    }
]

server = Server("incident-rag")

@server.list_tools()
async def handle_list_tools():
    return [
        {
            "name": "search_incidents",
            "description": "Search past incidents by symptoms, service, or description",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "service": {"type": "string"},
                    "limit": {"type": "integer", "default": 5}
                }
            }
        },
        {
            "name": "get_incident_details",
            "description": "Get detailed information about a specific incident",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "incident_id": {"type": "string"}
                },
                "required": ["incident_id"]
            }
        },
        {
            "name": "find_similar_incidents",
            "description": "Find incidents similar to current symptoms",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "symptoms": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "service": {"type": "string"}
                },
                "required": ["symptoms"]
            }
        }
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]):
    if name == "search_incidents":
        query = arguments.get("query", "").lower()
        service = arguments.get("service", "").lower()
        limit = arguments.get("limit", 5)
        
        results = []
        for incident in PAST_INCIDENTS:
            matches = True
            
            if query and query not in json.dumps(incident).lower():
                matches = False
            if service and service not in incident.get("service", "").lower():
                matches = False
            
            if matches:
                results.append(incident)
                if len(results) >= limit:
                    break
        
        return format_incidents(results)
    
    elif name == "get_incident_details":
        incident_id = arguments["incident_id"]
        for incident in PAST_INCIDENTS:
            if incident["id"] == incident_id:
                return json.dumps(incident, indent=2)
        return f"Incident {incident_id} not found"
    
    elif name == "find_similar_incidents":
        symptoms = [s.lower() for s in arguments["symptoms"]]
        service = arguments.get("service", "").lower()
        
        scored = []
        for incident in PAST_INCIDENTS:
            if service and service not in incident.get("service", "").lower():
                continue
            
            # Simple similarity scoring
            incident_symptoms = [s.lower() for s in incident.get("symptoms", [])]
            matches = len(set(symptoms) & set(incident_symptoms))
            score = matches / max(len(symptoms), 1)
            
            if score > 0:
                scored.append((score, incident))
        
        # Sort by similarity
        scored.sort(reverse=True)
        return format_incidents([inc for _, inc in scored[:3]])

def format_incidents(incidents: list) -> str:
    if not incidents:
        return "No incidents found"
    
    formatted = []
    for inc in incidents:
        formatted.append(
            f"ID: {inc['id']}\n"
            f"Service: {inc.get('service', 'N/A')}\n"
            f"Description: {inc['description']}\n"
            f"Symptoms: {', '.join(inc.get('symptoms', []))}\n"
            f"Root Cause: {inc.get('root_cause', 'N/A')}\n"
            f"Resolution: {inc.get('resolution', 'N/A')}\n"
        )
    return "\n---\n".join(formatted)