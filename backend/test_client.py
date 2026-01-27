from app.client import IncidentAnalysisClient

client = IncidentAnalysisClient("http://localhost:8000")

# Analyze
result = client.analyze_incident(
    query="API outage at 14:32",
    timestamp="2024-01-15T14:32:00Z",
    log_files=["logs/api-gateway.log"]
)

print(f"Confidence: {result['confidence']:.2f}")
print(f"Root cause: {result.get('root_cause', 'Insufficient evidence')}")