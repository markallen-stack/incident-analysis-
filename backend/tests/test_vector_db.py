
"""
Unit tests for vector database functionality.

Run with: pytest tests/test_vector_db.py -v
"""

import pytest
import json
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vector_db.query import search_logs, search_incidents, search_runbooks


@pytest.fixture(scope="module")
def sample_incidents_data():
    """Load sample incidents data for testing"""
    import config
    
    if not config.INCIDENTS_JSON.exists():
        pytest.skip("incidents.json not found")
    
    with open(config.INCIDENTS_JSON) as f:
        return json.load(f)


@pytest.mark.integration
def test_log_search_basic():
    """Test basic log search functionality"""
    results = search_logs("error memory", top_k=5)
    
    # Should return results (or empty list if index not created)
    assert isinstance(results, list)
    
    if results:
        # Verify result structure
        assert 'message' in results[0]
        assert 'similarity' in results[0]
        assert 0 <= results[0]['similarity'] <= 1


@pytest.mark.integration
def test_log_search_with_filters():
    """Test log search with service and level filters"""
    results = search_logs(
        "connection error",
        top_k=10,
        service_filter=["api-gateway"],
        level_filter=["ERROR", "CRITICAL"]
    )
    
    assert isinstance(results, list)
    
    # If results exist, verify filters were applied
    for result in results:
        if 'service' in result:
            assert result['service'] in ["api-gateway"]
        if 'level' in result:
            assert result['level'] in ["ERROR", "CRITICAL"]


@pytest.mark.integration
def test_incident_search():
    """Test historical incident search"""
    results = search_incidents("memory leak deployment", top_k=3)
    
    assert isinstance(results, list)
    
    if results:
        # Verify result structure
        assert 'similarity' in results[0]
        # Results should be sorted by similarity (highest first)
        if len(results) > 1:
            assert results[0]['similarity'] >= results[1]['similarity']


@pytest.mark.integration
def test_incident_search_similarity_threshold():
    """Test that incident search respects similarity threshold"""
    # Search with high similarity threshold
    results_high = search_incidents("random query xyz", min_similarity=0.9)
    
    # Search with low similarity threshold
    results_low = search_incidents("random query xyz", min_similarity=0.3)
    
    # High threshold should return fewer or equal results
    assert len(results_high) <= len(results_low)


@pytest.mark.integration
def test_runbook_search():
    """Test runbook search"""
    results = search_runbooks("troubleshooting high cpu", top_k=3)
    
    assert isinstance(results, list)
    
    if results:
        # Verify result structure
        assert 'content' in results[0] or 'title' in results[0]
        assert 'similarity' in results[0]


@pytest.mark.integration
def test_search_with_empty_query():
    """Test that search handles empty queries gracefully"""
    results = search_logs("", top_k=5)
    
    # Should return results or empty list, not crash
    assert isinstance(results, list)


@pytest.mark.integration
def test_search_ordering():
    """Test that results are ordered by similarity"""
    results = search_incidents("outage api errors", top_k=5)
    
    if len(results) > 1:
        # Verify descending similarity order
        for i in range(len(results) - 1):
            assert results[i]['similarity'] >= results[i + 1]['similarity']


@pytest.mark.integration
def test_log_search_time_window():
    """Test log search with time window filtering"""
    results = search_logs(
        "error",
        top_k=10,
        time_window=("2024-01-15T14:00:00Z", "2024-01-15T15:00:00Z")
    )
    
    assert isinstance(results, list)
    
    # Verify timestamps are within window
    for result in results:
        if 'timestamp' in result:
            ts = result['timestamp']
            assert "2024-01-15T14:" in ts or "2024-01-15T15:" in ts


@pytest.mark.unit
def test_search_functions_exist():
    """Test that all search functions are importable"""
    from vector_db.query import search_logs, search_incidents, search_runbooks
    
    assert callable(search_logs)
    assert callable(search_incidents)
    assert callable(search_runbooks)


@pytest.mark.unit
def test_vector_searcher_class():
    """Test VectorSearcher class instantiation"""
    from vector_db.query import VectorSearcher
    
    searcher = VectorSearcher()
    assert searcher is not None
    assert hasattr(searcher, 'search_logs')
    assert hasattr(searcher, 'search_incidents')
    assert hasattr(searcher, 'search_runbooks')


# Performance tests
@pytest.mark.slow
def test_search_performance():
    """Test that searches complete in reasonable time"""
    import time
    
    start = time.time()
    results = search_logs("memory error cpu spike", top_k=20)
    duration = time.time() - start
    
    # Should complete in under 1 second
    assert duration < 1.0, f"Search took {duration:.2f}s, expected < 1.0s"


@pytest.mark.slow
def test_batch_search_performance():
    """Test multiple searches complete quickly"""
    import time
    
    queries = [
        "memory leak",
        "cpu spike",
        "connection timeout",
        "database error",
        "deployment failure"
    ]
    
    start = time.time()
    for query in queries:
        search_logs(query, top_k=5)
    duration = time.time() - start
    
    # All searches should complete in under 2 seconds
    assert duration < 2.0, f"Batch search took {duration:.2f}s, expected < 2.0s"


# Edge cases
@pytest.mark.unit
def test_search_with_special_characters():
    """Test search handles special characters"""
    special_queries = [
        "error: connection failed",
        "HTTP/500 internal server",
        "memory.usage > 90%",
        "api.gateway[error]"
    ]
    
    for query in special_queries:
        results = search_logs(query, top_k=5)
        assert isinstance(results, list)


@pytest.mark.unit
def test_search_with_very_long_query():
    """Test search handles very long queries"""
    long_query = " ".join(["error"] * 100)
    
    results = search_logs(long_query, top_k=5)
    assert isinstance(results, list)


@pytest.mark.unit
def test_top_k_limits():
    """Test that top_k parameter is respected"""
    for k in [1, 5, 10, 20]:
        results = search_logs("error", top_k=k)
        assert len(results) <= k


# Integration with other components
@pytest.mark.integration
def test_search_results_compatible_with_evidence():
    """Test that search results can be converted to Evidence objects"""
    from agents.verifier import Evidence
    
    results = search_logs("memory error", top_k=5)
    
    # Should be able to create Evidence from results
    for result in results:
        evidence = Evidence(
            source="log",
            content=result.get('message', ''),
            timestamp=result.get('timestamp', ''),
            confidence=result.get('similarity', 0.0),
            metadata=result
        )
        assert evidence is not None


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])