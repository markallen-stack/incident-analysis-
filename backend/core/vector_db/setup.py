#!/usr/bin/env python3
"""
Pinecone Vector Database Setup Script (with Pinecone Inference)

Creates Pinecone indexes with built-in embeddings for:
1. Application logs
2. Historical incidents
3. Runbooks and documentation

Usage:
    python vector_db/setup.py
    python vector_db/setup.py --rebuild  # Force rebuild all indexes
"""
from pathlib import Path
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
import sys
import time

from pinecone import Pinecone, ServerlessSpec
from tqdm import tqdm

# Add parent directory to path for imports
upstream_dir = Path(__file__).resolve().parents[2]
sys.path.append(str(upstream_dir))
import config


class VectorDBSetup:
    """
    Creates and manages Pinecone vector indexes with inference API.
    """
    
    def __init__(self, use_local_embeddings: bool = False):
        """
        Initialize the setup manager.
        
        Args:
            use_local_embeddings: Deprecated. Pinecone-only deployment does not support local embeddings.
        """
        if use_local_embeddings:
            raise ValueError("Local embeddings are not supported (Pinecone-only mode).")
        self.use_local_embeddings = False
        
        # Initialize Pinecone
        self.pc = Pinecone(api_key=config.PINECONE_API_KEY)
        
        # Use Pinecone's inference API
        self.model_name = config.PINECONE_EMBEDDING_MODEL or "multilingual-e5-large"
        print(f"Using Pinecone inference with model: {self.model_name}")
        self.encoder = None
        self.dimension = self._get_model_dimension(self.model_name)
        self.metric = "cosine"
        
        print(f"Embedding dimension: {self.dimension}")
        
        # Index names
        self.log_index_name = config.PINECONE_LOG_INDEX or "incident-logs"
        self.incident_index_name = config.PINECONE_INCIDENT_INDEX or "incident-history"
        self.runbook_index_name = config.PINECONE_RUNBOOK_INDEX or "incident-runbooks"
    
    def _get_model_dimension(self, model_name: str) -> int:
        """Get embedding dimension for Pinecone inference models"""
        dimensions = {
            "multilingual-e5-large": 1024,
            "multilingual-e5-small": 384,
        }
        return dimensions.get(model_name, 1024)
    
    def _create_index_if_not_exists(self, index_name: str):
        """Create Pinecone index if it doesn't exist"""
        existing_indexes = [idx.name for idx in self.pc.list_indexes()]
        
        if index_name not in existing_indexes:
            print(f"Creating new Pinecone index: {index_name}")
            
            spec_params = {
                "cloud": config.PINECONE_CLOUD or "aws",
                "region": config.PINECONE_REGION or "us-east-1"
            }
            
            self.pc.create_index(
                name=index_name,
                dimension=self.dimension,
                metric=self.metric,
                spec=ServerlessSpec(**spec_params)
            )
            
            # Wait for index to be ready
            while not self.pc.describe_index(index_name).status['ready']:
                time.sleep(1)
            print(f"✅ Index {index_name} created and ready")
        else:
            print(f"✓ Index {index_name} already exists")
    
    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed texts using either Pinecone inference or local model.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        # Use Pinecone inference API (batch embed)
        embeddings = []
        batch_size = 96  # Pinecone inference batch limit

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self.pc.inference.embed(
                model=self.model_name,
                inputs=batch,
                parameters={"input_type": "passage"}
            )
            embeddings.extend([item.values for item in response])
        return embeddings
    
    def create_log_index(self, force_rebuild: bool = False) -> Tuple[int, str]:
        """
        Creates Pinecone index for application logs.
        
        Args:
            force_rebuild: If True, rebuild even if index exists
            
        Returns:
            (num_documents, index_name)
        """
        print("\n" + "="*60)
        print("Creating Log Index")
        print("="*60)
        
        # Create index
        self._create_index_if_not_exists(self.log_index_name)
        index = self.pc.Index(self.log_index_name)
        
        # Check if we need to rebuild
        stats = index.describe_index_stats()
        if stats['total_vector_count'] > 0 and not force_rebuild:
            print(f"✓ Log index already populated with {stats['total_vector_count']} vectors")
            return stats['total_vector_count'], self.log_index_name
        
        # Delete all vectors if rebuilding
        if force_rebuild and stats['total_vector_count'] > 0:
            print("Deleting existing vectors...")
            index.delete(delete_all=True)
            time.sleep(2)  # Wait for deletion
        
        # Load logs
        logs = self._load_logs_from_incidents()
        
        if not logs:
            print("⚠️  No logs found. Index remains empty.")
            return 0, self.log_index_name
        
        print(f"Found {len(logs)} log entries")
        
        # Create embeddings and upsert in batches
        print("Creating embeddings and uploading to Pinecone...")
        batch_size = 96
        
        for i in tqdm(range(0, len(logs), batch_size), desc="Processing batches"):
            batch = logs[i:i + batch_size]
            
            # Create embeddings for batch
            texts = [self._format_log_text(log) for log in batch]
            embeddings = self._embed_texts(texts)
            
            # Prepare vectors for upsert
            vectors = []
            for j, (log, embedding) in enumerate(zip(batch, embeddings)):
                vector_id = f"log_{i+j}"
                vectors.append({
                    "id": vector_id,
                    "values": embedding,
                    "metadata": {
                        "service": log.get("service", ""),
                        "level": log.get("level", ""),
                        "message": log.get("message", "")[:1000],
                        "timestamp": log.get("timestamp", ""),
                        "incident_id": log.get("incident_id", ""),
                        "incident_name": log.get("incident_name", ""),
                        "stack_trace": log.get("stack_trace", "")[:500]
                    }
                })
            
            # Upsert to Pinecone
            index.upsert(vectors=vectors)
        
        # Verify
        time.sleep(2)  # Wait for indexing
        stats = index.describe_index_stats()
        print(f"✅ Created log index: {stats['total_vector_count']} vectors")
        
        return stats['total_vector_count'], self.log_index_name
    
    def create_incident_index(self, force_rebuild: bool = False) -> Tuple[int, str]:
        """
        Creates Pinecone index for historical incidents.
        
        Args:
            force_rebuild: If True, rebuild even if index exists
            
        Returns:
            (num_documents, index_name)
        """
        print("\n" + "="*60)
        print("Creating Incident Index")
        print("="*60)
        
        # Create index
        self._create_index_if_not_exists(self.incident_index_name)
        index = self.pc.Index(self.incident_index_name)
        
        # Check if we need to rebuild
        stats = index.describe_index_stats()
        if stats['total_vector_count'] > 0 and not force_rebuild:
            print(f"✓ Incident index already populated with {stats['total_vector_count']} vectors")
            return stats['total_vector_count'], self.incident_index_name
        
        # Delete all vectors if rebuilding
        if force_rebuild and stats['total_vector_count'] > 0:
            print("Deleting existing vectors...")
            index.delete(delete_all=True)
            time.sleep(2)
        
        # Load incidents
        incidents = self._load_historical_incidents()
        
        if not incidents:
            print("⚠️  No incidents found. Index remains empty.")
            return 0, self.incident_index_name
        
        print(f"Found {len(incidents)} historical incidents")
        
        # Create embeddings and upsert in batches
        print("Creating embeddings and uploading to Pinecone...")
        batch_size = 96
        
        for i in tqdm(range(0, len(incidents), batch_size), desc="Processing batches"):
            batch = incidents[i:i + batch_size]
            
            # Create embeddings for batch
            texts = [self._format_incident_text(inc) for inc in batch]
            embeddings = self._embed_texts(texts)
            
            # Prepare vectors for upsert
            vectors = []
            for j, (incident, embedding) in enumerate(zip(batch, embeddings)):
                vector_id = f"incident_{i+j}"
                services = incident.get("services", [])
                if isinstance(services, str):
                    services = [services]
                
                vectors.append({
                    "id": vector_id,
                    "values": embedding,
                    "metadata": {
                        "incident_id": str(incident.get("id", "")),
                        "name": incident.get("name", "")[:1000],
                        "root_cause": incident.get("root_cause", "")[:1000],
                        "symptoms": incident.get("symptoms", "")[:1000],
                        "services": ",".join(services),
                        "resolution": incident.get("resolution", "")[:1000],
                        "timestamp": incident.get("timestamp", "")
                    }
                })
            
            # Upsert to Pinecone
            index.upsert(vectors=vectors)
        
        # Verify
        time.sleep(2)
        stats = index.describe_index_stats()
        print(f"✅ Created incident index: {stats['total_vector_count']} vectors")
        
        return stats['total_vector_count'], self.incident_index_name
    
    def create_runbook_index(self, force_rebuild: bool = False) -> Tuple[int, str]:
        """
        Creates Pinecone index for runbooks and documentation.
        
        Args:
            force_rebuild: If True, rebuild even if index exists
            
        Returns:
            (num_documents, index_name)
        """
        print("\n" + "="*60)
        print("Creating Runbook Index")
        print("="*60)
        
        # Create index
        self._create_index_if_not_exists(self.runbook_index_name)
        index = self.pc.Index(self.runbook_index_name)
        
        # Check if we need to rebuild
        stats = index.describe_index_stats()
        if stats['total_vector_count'] > 0 and not force_rebuild:
            print(f"✓ Runbook index already populated with {stats['total_vector_count']} vectors")
            return stats['total_vector_count'], self.runbook_index_name
        
        # Delete all vectors if rebuilding
        if force_rebuild and stats['total_vector_count'] > 0:
            print("Deleting existing vectors...")
            index.delete(delete_all=True)
            time.sleep(2)
        
        # Load runbooks
        runbooks = self._load_runbooks()
        
        if not runbooks:
            print("⚠️  No runbooks found. Index remains empty.")
            return 0, self.runbook_index_name
        
        print(f"Found {len(runbooks)} runbook sections")
        
        # Create embeddings and upsert in batches
        print("Creating embeddings and uploading to Pinecone...")
        batch_size = 96
        
        for i in tqdm(range(0, len(runbooks), batch_size), desc="Processing batches"):
            batch = runbooks[i:i + batch_size]
            
            # Create embeddings for batch
            texts = [rb['content'] for rb in batch]
            embeddings = self._embed_texts(texts)
            
            # Prepare vectors for upsert
            vectors = []
            for j, (runbook, embedding) in enumerate(zip(batch, embeddings)):
                vector_id = f"runbook_{i+j}"
                vectors.append({
                    "id": vector_id,
                    "values": embedding,
                    "metadata": {
                        "title": runbook.get("title", "")[:1000],
                        "section": runbook.get("section", "")[:1000],
                        "content": runbook.get("content", "")[:1000],
                        "source": runbook.get("source", "")
                    }
                })
            
            # Upsert to Pinecone
            index.upsert(vectors=vectors)
        
        # Verify
        time.sleep(2)
        stats = index.describe_index_stats()
        print(f"✅ Created runbook index: {stats['total_vector_count']} vectors")
        
        return stats['total_vector_count'], self.runbook_index_name
    
    def _load_logs_from_incidents(self) -> List[Dict]:
        """Load all logs from incidents.json"""
        all_logs = []
        
        try:
            with open(config.INCIDENTS_JSON) as f:
                data = json.load(f)
            
            for incident in data.get('incidents', []):
                logs = incident.get('logs', [])
                for log in logs:
                    log['incident_id'] = incident['id']
                    log['incident_name'] = incident['name']
                    all_logs.append(log)
            
        except FileNotFoundError:
            print(f"⚠️  {config.INCIDENTS_JSON} not found")
        except json.JSONDecodeError as e:
            print(f"⚠️  Error parsing {config.INCIDENTS_JSON}: {e}")
        
        return all_logs
    
    def _load_historical_incidents(self) -> List[Dict]:
        """Load historical incidents from data sources"""
        incidents = []
        
        try:
            with open(config.INCIDENTS_JSON) as f:
                data = json.load(f)
            
            for incident in data.get('incidents', []):
                hist_incident = {
                    'id': incident['id'],
                    'name': incident['name'],
                    'root_cause': incident.get('expected_root_cause', ''),
                    'symptoms': incident.get('user_query', ''),
                    'services': [],
                    'resolution': '',
                    'timestamp': incident.get('timestamp', '')
                }
                
                for hist in incident.get('historical_incidents', []):
                    incidents.append(hist)
                
                if hist_incident['root_cause']:
                    incidents.append(hist_incident)
        
        except FileNotFoundError:
            print(f"⚠️  {config.INCIDENTS_JSON} not found")
        except json.JSONDecodeError as e:
            print(f"⚠️  Error parsing incidents: {e}")
        
        hist_dir = config.HISTORICAL_INCIDENTS_DIR
        if hist_dir.exists():
            for json_file in hist_dir.glob("*.json"):
                try:
                    with open(json_file) as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            incidents.extend(data)
                        elif isinstance(data, dict):
                            incidents.append(data)
                except Exception as e:
                    print(f"⚠️  Error loading {json_file}: {e}")
        
        return incidents
    
    def _load_runbooks(self) -> List[Dict]:
        """Load runbooks from data/runbooks directory"""
        runbooks = []
        
        runbooks_dir = config.RUNBOOKS_DIR
        
        try:
            with open(config.INCIDENTS_JSON) as f:
                data = json.load(f)
            
            for incident in data.get('incidents', []):
                for runbook in incident.get('runbooks', []):
                    for section in runbook.get('relevant_sections', []):
                        runbooks.append({
                            'title': runbook['title'],
                            'section': section,
                            'content': f"{runbook['title']}: {section}",
                            'source': 'incidents.json'
                        })
        except Exception as e:
            print(f"⚠️  Error loading runbooks from incidents: {e}")
        
        if runbooks_dir.exists():
            for md_file in runbooks_dir.glob("*.md"):
                try:
                    with open(md_file) as f:
                        content = f.read()
                        sections = content.split('\n##')
                        for section in sections:
                            if section.strip():
                                lines = section.strip().split('\n')
                                title = lines[0].strip('#').strip()
                                body = '\n'.join(lines[1:]).strip()
                                
                                if body:
                                    runbooks.append({
                                        'title': title,
                                        'content': f"{title}\n{body}",
                                        'source': md_file.name
                                    })
                
                except Exception as e:
                    print(f"⚠️  Error loading {md_file}: {e}")
        
        return runbooks
    
    def _format_log_text(self, log: Dict) -> str:
        """Format log entry for embedding"""
        parts = []
        if log.get('service'):
            parts.append(f"Service: {log['service']}")
        if log.get('level'):
            parts.append(f"Level: {log['level']}")
        if log.get('message'):
            parts.append(f"Message: {log['message']}")
        if log.get('stack_trace'):
            parts.append(f"Stack: {log['stack_trace'][:200]}")
        return ' | '.join(parts)
    
    def _format_incident_text(self, incident: Dict) -> str:
        """Format incident for embedding"""
        parts = []
        if incident.get('root_cause'):
            parts.append(f"Root cause: {incident['root_cause']}")
        if incident.get('symptoms'):
            parts.append(f"Symptoms: {incident['symptoms']}")
        if incident.get('services'):
            services = incident['services'] if isinstance(incident['services'], list) else [incident['services']]
            parts.append(f"Services: {', '.join(services)}")
        if incident.get('resolution'):
            parts.append(f"Resolution: {incident['resolution']}")
        return ' | '.join(parts)
    
    def verify_indexes(self):
        """Verify all indexes are created and accessible"""
        print("\n" + "="*60)
        print("Verifying Indexes")
        print("="*60)
        
        indexes = [
            ("Logs", self.log_index_name),
            ("Incidents", self.incident_index_name),
            ("Runbooks", self.runbook_index_name)
        ]
        
        all_ok = True
        for name, index_name in indexes:
            try:
                index = self.pc.Index(index_name)
                stats = index.describe_index_stats()
                count = stats['total_vector_count']
                print(f"✅ {name}: {count} vectors in {index_name}")
            except Exception as e:
                print(f"❌ {name}: Error - {e}")
                all_ok = False
        
        return all_ok


def main():
    """Main setup function"""
    parser = argparse.ArgumentParser(
        description="Create Pinecone vector indexes with inference API"
    )
    parser.add_argument(
        '--rebuild',
        action='store_true',
        help='Force rebuild of all indexes'
    )
    # Pinecone-only: local embeddings removed to keep production slim
    
    args = parser.parse_args()
    
    print("="*60)
    print("Pinecone Vector Database Setup")
    print("="*60)
    print("Embedding mode: Pinecone Inference API")
    print("="*60)
    
    try:
        setup = VectorDBSetup(use_local_embeddings=False)
        
        log_count, log_name = setup.create_log_index(force_rebuild=args.rebuild)
        incident_count, incident_name = setup.create_incident_index(force_rebuild=args.rebuild)
        runbook_count, runbook_name = setup.create_runbook_index(force_rebuild=args.rebuild)
        
        all_ok = setup.verify_indexes()
        
        print("\n" + "="*60)
        print("Setup Complete")
        print("="*60)
        print(f"Total vectors created:")
        print(f"  • Logs: {log_count}")
        print(f"  • Incidents: {incident_count}")
        print(f"  • Runbooks: {runbook_count}")
        print(f"  • Total: {log_count + incident_count + runbook_count}")
        print("="*60)
        
        if all_ok:
            print("\n✅ All indexes created successfully!")
            print("\nNext steps:")
            print("1. Run evaluation: python evaluation/run_eval.py")
            print("2. Analyze incident: python analyze.py --help")
            return 0
        else:
            print("\n⚠️  Some indexes missing. Check errors above.")
            return 1
    
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())