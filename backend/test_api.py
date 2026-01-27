#!/usr/bin/env python3
"""
Test script for the FastAPI endpoints.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.main import app
from fastapi.testclient import TestClient
import json

client = TestClient(app)


def test_root():
    """Test root endpoint"""
    print("\n" + "="*60)
    print("Testing ROOT endpoint")
    print("="*60)
    response = client.get("/")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200


def test_health():
    """Test health endpoints"""
    print("\n" + "="*60)
    print("Testing HEALTH endpoints")
    print("="*60)
    
    # Health check
    response = client.get("/health/")
    print(f"\n✓ Health check: {response.status_code}")
    print(f"  {json.dumps(response.json(), indent=2, default=str)}")
    assert response.status_code == 200
    
    # Config
    response = client.get("/health/config")
    print(f"\n✓ Config: {response.status_code}")
    config = response.json()
    print(f"  Primary LLM: {config['primary_llm']}")
    print(f"  Vision Model: {config['vision_model']}")
    assert response.status_code == 200
    
    # Readiness
    response = client.get("/health/ready")
    print(f"\n✓ Readiness: {response.status_code}")
    print(f"  {response.json()}")
    assert response.status_code == 200


def test_image_formats():
    """Test image formats endpoint"""
    print("\n" + "="*60)
    print("Testing IMAGE formats endpoint")
    print("="*60)
    response = client.get("/api/v1/images/supported-formats")
    print(f"Status: {response.status_code}")
    print(f"Supported formats: {response.json()}")
    assert response.status_code == 200


def test_list_analyses():
    """Test list analyses endpoint"""
    print("\n" + "="*60)
    print("Testing LIST analyses endpoint")
    print("="*60)
    response = client.get("/api/v1/analysis/")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Total analyses: {data['total']}")
    assert response.status_code == 200


def test_incident_statistics():
    """Test incident statistics"""
    print("\n" + "="*60)
    print("Testing INCIDENT statistics endpoint")
    print("="*60)
    response = client.get("/api/v1/incidents/stats/summary")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200


def test_analysis_with_mock_data():
    """Test analysis with mock data"""
    print("\n" + "="*60)
    print("Testing ANALYSIS endpoint with mock data")
    print("="*60)
    
    payload = {
        "query": "API server crashed at 14:32 UTC",
        "dashboard_images": ["data/images/cpu-mem-cluster-panels.png"],
        "logs": [
            {"timestamp": "2024-01-15T14:30:00Z", "level": "ERROR", "message": "Database connection failed"},
            {"timestamp": "2024-01-15T14:31:00Z", "level": "ERROR", "message": "Request timeout"},
            {"timestamp": "2024-01-15T14:32:00Z", "level": "CRITICAL", "message": "Service crashed"}
        ],
        "time_window": "14:20-14:45"
    }
    
    response = client.post("/api/v1/analysis/", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\nRequest ID: {result['request_id']}")
        print(f"Status: {result['status']}")
        print(f"Decision: {result['decision']}")
        print(f"Confidence: {result['overall_confidence']:.2f}")
        print(f"Root Cause: {result['root_cause']}")
        print(f"Evidence Count: {len(result['evidence'])}")
        print(f"Timeline Events: {len(result['timeline'])}")
        print(f"Hypotheses: {len(result['hypotheses'])}")
        print(f"Recommendations: {result['recommendations']}")
        print("\nSample Evidence:")
        for i, ev in enumerate(result['evidence'][:2], 1):
            print(f"  {i}. [{ev['source']}] {ev['content']}")
            print(f"     Confidence: {ev['confidence']:.2f}")
    else:
        print(f"Error: {response.text}")
    
    assert response.status_code == 200


def main():
    """Run all tests"""
    print("\n" + "🧪 FASTAPI ENDPOINT TESTS ".center(60, "="))
    
    try:
        test_root()
        test_health()
        test_image_formats()
        test_list_analyses()
        test_incident_statistics()
        test_analysis_with_mock_data()
        
        print("\n" + "✅ ALL TESTS PASSED ".center(60, "="))
        print("\nAPI endpoints are working correctly!")
        print("\nAvailable endpoints:")
        print("  GET  /                           - API info")
        print("  GET  /health/                    - Health check")
        print("  GET  /health/config              - Configuration")
        print("  GET  /health/ready               - Readiness check")
        print("  POST /api/v1/analysis/           - Analyze incident")
        print("  GET  /api/v1/analysis/           - List analyses")
        print("  GET  /api/v1/analysis/{id}       - Get analysis result")
        print("  POST /api/v1/images/analyze      - Analyze single image")
        print("  POST /api/v1/images/batch        - Analyze multiple images")
        print("  GET  /api/v1/images/supported-formats - Get supported formats")
        print("  POST /api/v1/incidents/search    - Search incidents")
        print("  GET  /api/v1/incidents/historical - Get historical incidents")
        print("  GET  /api/v1/incidents/{id}      - Get incident details")
        print("  GET  /api/v1/incidents/stats/summary - Get statistics")
        print("\nRun the API server with:")
        print("  python run.py")
        print("  Or: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
