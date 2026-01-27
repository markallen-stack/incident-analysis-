#!/usr/bin/env python3
"""
Pinecone Vector Database Query Utilities (with Pinecone Inference)

Provides functions for searching Pinecone indexes:
- search_logs(): Search application logs
- search_incidents(): Search historical incidents  
- search_runbooks(): Search documentation

Usage:
    from vector_db.query import search_logs, search_incidents
    
    results = search_logs("OutOfMemoryError", top_k=10)
    incidents = search_incidents("memory leak deployment", top_k=5)
"""

from pathlib import Path
from typing import List, Dict, Optional, Tuple
import sys

from pinecone import Pinecone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


class VectorSearcher:
    """
    Handles vector similarity search across all Pinecone indexes using inference API.
    """
    
    def __init__(self, use_local_embeddings: bool = False):
        """
        Initialize the searcher.
        
        Args:
            use_local_embeddings: If True, use local sentence-transformers instead of Pinecone inference
        """
        self.use_local_embeddings = use_local_embeddings
        
        # Initialize Pinecone
        self.pc = Pinecone(api_key=config.PINECONE_API_KEY)
        
        # Set up embedding model
        if use_local_embeddings:
            from sentence_transformers import SentenceTransformer
            self.model_name = config.EMBEDDING_MODEL
            self.encoder = SentenceTransformer(self.model_name)
        else:
            # Use Pinecone's inference API
            self.model_name = config.PINECONE_EMBEDDING_MODEL or "multilingual-e5-large"
            self.encoder = None
        
        # Index names
        self.log_index_name = config.PINECONE_LOG_INDEX or "incident-logs"
        self.incident_index_name = config.PINECONE_INCIDENT_INDEX or "incident-history"
        self.runbook_index_name = config.PINECONE_RUNBOOK_INDEX or "incident-runbooks"
        
        # Cache for loaded indexes
        self._log_index = None
        self._incident_index = None
        self._runbook_index = None
    
    def _embed_query(self, query: str) -> List[float]:
        """
        Embed a query using either Pinecone inference or local model.
        
        Args:
            query: Query text to embed
            
        Returns:
            Embedding vector
        """
        if self.use_local_embeddings:
            # Use local model
            embedding = self.encoder.encode([query], convert_to_numpy=True)[0]
            return embedding.tolist()
        else:
            # Use Pinecone inference API
            response = self.pc.inference.embed(
                model=self.model_name,
                inputs=[query],
                parameters={"input_type": "query"}  # Important: use "query" for search queries
            )
            return response[0].values
    
    def search_logs(
        self,
        query: str,
        top_k: int = 20,
        time_window: Optional[Tuple[str, str]] = None,
        service_filter: Optional[List[str]] = None,
        level_filter: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Search application logs.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            time_window: Optional (start_time, end_time) tuple for filtering
            service_filter: Optional list of services to filter by
            level_filter: Optional list of log levels (ERROR, WARN, INFO)
        
        Returns:
            List of log entries with similarity scores
        """
        # Load index
        index = self._get_log_index()
        
        if index is None:
            return []
        
        # Create query embedding
        query_vector = self._embed_query(query)
        
        # Build filter
        filter_dict = {}
        if service_filter:
            filter_dict["service"] = {"$in": service_filter}
        if level_filter:
            filter_dict["level"] = {"$in": level_filter}
        
        # Search Pinecone
        try:
            results = index.query(
                vector=query_vector,
                top_k=top_k * 2 if time_window else top_k,
                include_metadata=True,
                filter=filter_dict if filter_dict else None
            )
        except Exception as e:
            print(f"⚠️  Error querying log index: {e}")
            return []
        
        # Format results
        formatted_results = []
        for match in results['matches']:
            log = match['metadata'].copy()
            log['similarity'] = float(match['score'])
            
            # Apply time filter (client-side)
            if time_window:
                timestamp = log.get('timestamp', '')
                if not (time_window[0] <= timestamp <= time_window[1]):
                    continue
            
            formatted_results.append(log)
            
            if len(formatted_results) >= top_k:
                break
        
        return formatted_results
    
    def search_incidents(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.6,
        service_filter: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Search historical incidents.
        
        Args:
            query: Search query (symptoms, root cause, etc.)
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold (0-1)
            service_filter: Optional list of services to filter by
        
        Returns:
            List of incident records with similarity scores
        """
        # Load index
        index = self._get_incident_index()
        
        if index is None:
            return []
        
        # Create query embedding
        query_vector = self._embed_query(query)
        
        # Search Pinecone
        try:
            results = index.query(
                vector=query_vector,
                top_k=top_k * 2,
                include_metadata=True
            )
        except Exception as e:
            print(f"⚠️  Error querying incident index: {e}")
            return []
        
        # Filter and format results
        formatted_results = []
        for match in results['matches']:
            similarity = float(match['score'])
            
            # Skip low similarity matches
            if similarity < min_similarity:
                continue
            
            incident = match['metadata'].copy()
            incident['similarity'] = similarity
            
            # Apply service filter
            if service_filter:
                incident_services = incident.get('services', '').split(',')
                if not any(s.strip() in service_filter for s in incident_services if s.strip()):
                    continue
            
            formatted_results.append(incident)
            
            if len(formatted_results) >= top_k:
                break
        
        return formatted_results
    
    def search_runbooks(
        self,
        query: str,
        top_k: int = 3,
        min_similarity: float = 0.5
    ) -> List[Dict]:
        """
        Search runbooks and documentation.
        
        Args:
            query: Search query (problem description, service name, etc.)
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold (0-1)
        
        Returns:
            List of runbook sections with similarity scores
        """
        # Load index
        index = self._get_runbook_index()
        
        if index is None:
            return []
        
        # Create query embedding
        query_vector = self._embed_query(query)
        
        # Search Pinecone
        try:
            results = index.query(
                vector=query_vector,
                top_k=top_k * 2,
                include_metadata=True
            )
        except Exception as e:
            print(f"⚠️  Error querying runbook index: {e}")
            return []
        
        # Filter and format results
        formatted_results = []
        for match in results['matches']:
            similarity = float(match['score'])
            
            # Skip low similarity matches
            if similarity < min_similarity:
                continue
            
            runbook = match['metadata'].copy()
            runbook['similarity'] = similarity
            formatted_results.append(runbook)
            
            if len(formatted_results) >= top_k:
                break
        
        return formatted_results
    
    def _get_log_index(self):
        """Get log index (cached)"""
        if self._log_index is None:
            try:
                self._log_index = self.pc.Index(self.log_index_name)
            except Exception as e:
                print(f"⚠️  Log index not found: {e}")
                print(f"   Run: python vector_db/setup.py")
                return None
        
        return self._log_index
    
    def _get_incident_index(self):
        """Get incident index (cached)"""
        if self._incident_index is None:
            try:
                self._incident_index = self.pc.Index(self.incident_index_name)
            except Exception as e:
                print(f"⚠️  Incident index not found: {e}")
                print(f"   Run: python vector_db/setup.py")
                return None
        
        return self._incident_index
    
    def _get_runbook_index(self):
        """Get runbook index (cached)"""
        if self._runbook_index is None:
            try:
                self._runbook_index = self.pc.Index(self.runbook_index_name)
            except Exception as e:
                print(f"⚠️  Runbook index not found: {e}")
                print(f"   Run: python vector_db/setup.py")
                return None
        
        return self._runbook_index


# Global searcher instance (singleton pattern)
_searcher = None

def get_searcher(use_local_embeddings: bool = False) -> VectorSearcher:
    """Get or create the global searcher instance"""
    global _searcher
    if _searcher is None:
        _searcher = VectorSearcher(use_local_embeddings=use_local_embeddings)
    return _searcher


# Convenience functions for direct use
def search_logs(
    query: str,
    top_k: int = 20,
    time_window: Optional[Tuple[str, str]] = None,
    service_filter: Optional[List[str]] = None,
    level_filter: Optional[List[str]] = None
) -> List[Dict]:
    """Search application logs. See VectorSearcher.search_logs for details."""
    return get_searcher().search_logs(query, top_k, time_window, service_filter, level_filter)


def search_incidents(
    query: str,
    top_k: int = 5,
    min_similarity: float = 0.6,
    service_filter: Optional[List[str]] = None
) -> List[Dict]:
    """Search historical incidents. See VectorSearcher.search_incidents for details."""
    return get_searcher().search_incidents(query, top_k, min_similarity, service_filter)


def search_runbooks(
    query: str,
    top_k: int = 3,
    min_similarity: float = 0.5
) -> List[Dict]:
    """Search runbooks. See VectorSearcher.search_runbooks for details."""
    return get_searcher().search_runbooks(query, top_k, min_similarity)


# CLI for testing
def main():
    """Test the vector search functionality"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Pinecone vector search with inference")
    parser.add_argument('query', help='Search query')
    parser.add_argument(
        '--type',
        choices=['logs', 'incidents', 'runbooks'],
        default='logs',
        help='Index to search'
    )
    parser.add_argument('--top-k', type=int, default=5, help='Number of results')
    parser.add_argument(
        '--local-embeddings',
        action='store_true',
        help='Use local embeddings instead of Pinecone inference'
    )
    
    args = parser.parse_args()
    
    print(f"\nSearching {args.type} for: '{args.query}'")
    print("="*60)
    
    # Create searcher with specified embedding mode
    searcher = get_searcher(use_local_embeddings=args.local_embeddings)
    
    if args.type == 'logs':
        results = searcher.search_logs(args.query, top_k=args.top_k)
    elif args.type == 'incidents':
        results = searcher.search_incidents(args.query, top_k=args.top_k)
    else:
        results = searcher.search_runbooks(args.query, top_k=args.top_k)
    
    if not results:
        print("No results found.")
        print("\nMake sure indexes are created: python vector_db/setup.py")
        return
    
    for i, result in enumerate(results, 1):
        print(f"\n{i}. Similarity: {result.get('similarity', 0):.3f}")
        
        if args.type == 'logs':
            print(f"   Service: {result.get('service', 'N/A')}")
            print(f"   Level: {result.get('level', 'N/A')}")
            print(f"   Message: {result.get('message', 'N/A')[:100]}...")
        
        elif args.type == 'incidents':
            print(f"   ID: {result.get('incident_id', result.get('id', 'N/A'))}")
            print(f"   Root Cause: {result.get('root_cause', 'N/A')[:100]}...")
        
        else:  # runbooks
            print(f"   Title: {result.get('title', 'N/A')}")
            print(f"   Content: {result.get('content', 'N/A')[:150]}...")
    
    print("\n" + "="*60)
    print(f"Found {len(results)} results")


if __name__ == "__main__":
    main()