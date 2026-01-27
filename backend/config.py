"""
Configuration management for the Incident Analysis system.
Loads from: 1) settings.json (UI overrides), 2) environment / .env, 3) defaults.
"""

import os
import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from dotenv import load_dotenv

load_dotenv()

# Base paths (required before _load_settings)
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
VECTOR_DB_DIR = BASE_DIR / "vector_db"
EVAL_DIR = BASE_DIR / "evaluation"

_SETTINGS_FILE = DATA_DIR / "settings.json"


def _load_settings() -> Dict[str, Any]:
    """Load UI overrides from data/settings.json. Overrides take precedence over .env."""
    if not _SETTINGS_FILE.exists():
        return {}
    try:
        with open(_SETTINGS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


_overrides = _load_settings()


def _get(key: str, default: Any, cast: type = str) -> Any:
    raw = _overrides.get(key)
    if raw is None:
        raw = os.getenv(key, default)
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        if default is None:
            return None
        raw = default
    if cast == bool:
        return str(raw).lower() in ("true", "1", "yes")
    if cast == Path:
        return Path(str(raw)) if raw else None
    return cast(raw)


# ---------------------------------------------------------------------------
# Schema for Settings API: key -> { type, default, label, description, secret, category }
# ---------------------------------------------------------------------------
SETTINGS_SCHEMA: List[Dict[str, Any]] = [
    # API Keys
    {"key": "ANTHROPIC_API_KEY", "type": "string", "default": "", "label": "Anthropic API Key", "description": "sk-ant-... (optional if OpenAI is set)", "secret": True, "category": "api_keys"},
    {"key": "OPENAI_API_KEY", "type": "string", "default": "", "label": "OpenAI API Key", "description": "sk-... (optional if Anthropic is set)", "secret": True, "category": "api_keys"},
    # Models
    {"key": "PRIMARY_LLM", "type": "string", "default": "claude-sonnet-4-20250514", "label": "Primary LLM", "description": "Model for planner, hypothesis, etc.", "secret": False, "category": "models"},
    {"key": "VISION_MODEL", "type": "string", "default": "gpt-4o", "label": "Vision Model", "description": "Model for dashboard image analysis", "secret": False, "category": "models"},
    {"key": "EMBEDDING_MODEL", "type": "string", "default": "BAAI/bge-large-en-v1.5", "label": "Embedding Model", "description": "For vector search; requires index rebuild if changed", "secret": False, "category": "models"},
    # Thresholds
    {"key": "CONFIDENCE_THRESHOLD", "type": "float", "default": "0.7", "label": "Confidence Threshold", "description": "Minimum confidence to answer (0–1)", "secret": False, "category": "thresholds"},
    {"key": "MIN_EVIDENCE_SOURCES", "type": "int", "default": "2", "label": "Min Evidence Sources", "description": "Required independent sources for verification", "secret": False, "category": "thresholds"},
    {"key": "MAX_HYPOTHESES", "type": "int", "default": "5", "label": "Max Hypotheses", "description": "Maximum root cause hypotheses to generate", "secret": False, "category": "thresholds"},
    # Observability
    {"key": "PROMETHEUS_URL", "type": "string", "default": "http://localhost:9090", "label": "Prometheus URL", "description": "Prometheus API base URL", "secret": False, "category": "observability"},
    {"key": "GRAFANA_URL", "type": "string", "default": "http://localhost:3000", "label": "Grafana URL", "description": "Grafana API base URL", "secret": False, "category": "observability"},
    {"key": "GRAFANA_API_KEY", "type": "string", "default": "", "label": "Grafana API Key", "description": "Bearer token for Grafana API", "secret": True, "category": "observability"},
    # Performance
    {"key": "MAX_CONCURRENT_AGENTS", "type": "int", "default": "3", "label": "Max Concurrent Agents", "description": "Parallel evidence collectors", "secret": False, "category": "performance"},
    {"key": "REQUEST_TIMEOUT", "type": "int", "default": "30", "label": "Request Timeout (s)", "description": "Timeout for external calls", "secret": False, "category": "performance"},
    {"key": "BATCH_SIZE", "type": "int", "default": "32", "label": "Batch Size", "description": "Embedding batch size", "secret": False, "category": "performance"},
    # Logging
    {"key": "LOG_LEVEL", "type": "string", "default": "INFO", "label": "Log Level", "description": "DEBUG, INFO, WARNING, ERROR", "secret": False, "category": "logging"},
    {"key": "LOG_FILE", "type": "string", "default": "logs/incident_rag.log", "label": "Log File", "description": "Path to log file", "secret": False, "category": "logging"},
    {"key": "DEBUG_MODE", "type": "bool", "default": "false", "label": "Debug Mode", "description": "Enable debug logging", "secret": False, "category": "logging"},
    {"key": "SAVE_INTERMEDIATE_STATES", "type": "bool", "default": "false", "label": "Save Intermediate States", "description": "Persist graph state for debugging", "secret": False, "category": "logging"},
    # Vector DB
    {"key": "VECTOR_DB_PATH", "type": "path", "default": "", "label": "Vector DB Path", "description": "Directory for FAISS indexes", "secret": False, "category": "paths"},
    {"key": "LOG_INDEX_NAME", "type": "string", "default": "logs.faiss", "label": "Log Index Name", "description": "Filename for log index", "secret": False, "category": "paths"},
    {"key": "INCIDENT_INDEX_NAME", "type": "string", "default": "incidents.faiss", "label": "Incident Index Name", "description": "Filename for incident index", "secret": False, "category": "paths"},
    {"key": "RUNBOOK_INDEX_NAME", "type": "string", "default": "runbooks.faiss", "label": "Runbook Index Name", "description": "Filename for runbook index", "secret": False, "category": "paths"},
]

# Default for VECTOR_DB_PATH when not set
_default_vector_db_path = str(VECTOR_DB_DIR / "indexes")

# ---------------------------------------------------------------------------
# Resolved configuration (overrides > env > defaults)
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY", "", str)
OPENAI_API_KEY = _get("OPENAI_API_KEY", "", str)

PRIMARY_LLM = _get("PRIMARY_LLM", "claude-sonnet-4-20250514", str)
VISION_MODEL = _get("VISION_MODEL", "gpt-4o", str)
EMBEDDING_MODEL = _get("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5", str)

CONFIDENCE_THRESHOLD = _get("CONFIDENCE_THRESHOLD", "0.7", float)
MIN_EVIDENCE_SOURCES = _get("MIN_EVIDENCE_SOURCES", "2", int)
MAX_HYPOTHESES = _get("MAX_HYPOTHESES", "5", int)

MAX_CONCURRENT_AGENTS = _get("MAX_CONCURRENT_AGENTS", "3", int)
REQUEST_TIMEOUT = _get("REQUEST_TIMEOUT", "30", int)
BATCH_SIZE = _get("BATCH_SIZE", "32", int)

LOG_LEVEL = _get("LOG_LEVEL", "INFO", str)
LOG_FILE = _get("LOG_FILE", "logs/incident_rag.log", str)
DEBUG_MODE = _get("DEBUG_MODE", "false", bool)
SAVE_INTERMEDIATE_STATES = _get("SAVE_INTERMEDIATE_STATES", "false", bool)

PROMETHEUS_URL = _get("PROMETHEUS_URL", "http://localhost:9090", str)
GRAFANA_URL = _get("GRAFANA_URL", "http://localhost:3000", str)
GRAFANA_API_KEY = _get("GRAFANA_API_KEY", "", str)

# Vector DB: path and index names
_raw_vector_path = _get("VECTOR_DB_PATH", _default_vector_db_path, str)
VECTOR_DB_PATH = Path(_raw_vector_path) if _raw_vector_path else Path(_default_vector_db_path)
LOG_INDEX_NAME = _get("LOG_INDEX_NAME", "logs.faiss", str)
INCIDENT_INDEX_NAME = _get("INCIDENT_INDEX_NAME", "incidents.faiss", str)
RUNBOOK_INDEX_NAME = _get("RUNBOOK_INDEX_NAME", "runbooks.faiss", str)

LOG_INDEX_PATH = VECTOR_DB_PATH / LOG_INDEX_NAME
INCIDENT_INDEX_PATH = VECTOR_DB_PATH / INCIDENT_INDEX_NAME
RUNBOOK_INDEX_PATH = VECTOR_DB_PATH / RUNBOOK_INDEX_NAME


PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "your-pinecone-api-key-here")

# Pinecone Embedding Model (for inference API)
# Options: "multilingual-e5-large" (1024d), "multilingual-e5-small" (384d)
PINECONE_EMBEDDING_MODEL = os.getenv("PINECONE_EMBEDDING_MODEL", "multilingual-e5-large")

# Pinecone Index Names
PINECONE_LOG_INDEX = os.getenv("PINECONE_LOG_INDEX", "incident-logs")
PINECONE_INCIDENT_INDEX = os.getenv("PINECONE_INCIDENT_INDEX", "incident-history")
PINECONE_RUNBOOK_INDEX = os.getenv("PINECONE_RUNBOOK_INDEX", "incident-runbooks")

# Pinecone Cloud & Region (for serverless)
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")  # or "gcp", "azure"
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")  # e.g., "us-west-2", "eu-west-1"

# Embedding Model (keep your existing one)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "32"))


# Data paths (derived, not in settings UI)
INCIDENTS_JSON = DATA_DIR / "incidents.json"
DASHBOARDS_DIR = DATA_DIR / "dashboards"
LOGS_DIR = DATA_DIR / "logs"
HISTORICAL_INCIDENTS_DIR = DATA_DIR / "historical_incidents"
RUNBOOKS_DIR = DATA_DIR / "runbooks"

# Ensure directories exist
VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)
DASHBOARDS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
HISTORICAL_INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)
RUNBOOKS_DIR.mkdir(parents=True, exist_ok=True)
Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Settings API: get_settings, update_settings
# ---------------------------------------------------------------------------
def _cast_value(key: str, value: Any, meta: Dict) -> Any:
    t = meta.get("type", "string")
    if t == "int":
        return int(value) if value not in (None, "") else int(meta.get("default", 0))
    if t == "float":
        return float(value) if value not in (None, "") else float(meta.get("default", 0))
    if t == "bool":
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes") if value not in (None, "") else False
    if t == "path":
        if value not in (None, "") and str(value).strip():
            return Path(str(value))
        return Path(VECTOR_DB_DIR / "indexes")
    return str(value) if value is not None else str(meta.get("default", ""))


def get_settings() -> Dict[str, Any]:
    """Return current settings for the UI. Secrets are masked as ********."""
    mod = sys.modules[__name__]
    out: Dict[str, Any] = {"schema": SETTINGS_SCHEMA, "values": {}}
    for s in SETTINGS_SCHEMA:
        k = s["key"]
        v = getattr(mod, k, s.get("default"))
        if isinstance(v, Path):
            v = str(v)
        if s.get("secret") and v:
            v = "********"
        out["values"][k] = v
    return out


def update_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply settings from the UI: update _overrides, setattr on this module,
    recompute derived paths, and save to settings.json.
    """
    mod = sys.modules[__name__]
    key_to_meta = {s["key"]: s for s in SETTINGS_SCHEMA}
    for k, v in data.items():
        if k not in key_to_meta:
            continue
        meta = key_to_meta[k]
        if meta.get("secret") and (v in (None, "", "********")):
            continue
        casted = _cast_value(k, v, meta)
        _overrides[k] = casted
        setattr(mod, k, casted)

    # Recompute derived paths
    vdp = getattr(mod, "VECTOR_DB_PATH", VECTOR_DB_PATH)
    setattr(mod, "LOG_INDEX_PATH", vdp / getattr(mod, "LOG_INDEX_NAME", LOG_INDEX_NAME))
    setattr(mod, "INCIDENT_INDEX_PATH", vdp / getattr(mod, "INCIDENT_INDEX_NAME", INCIDENT_INDEX_NAME))
    setattr(mod, "RUNBOOK_INDEX_PATH", vdp / getattr(mod, "RUNBOOK_INDEX_NAME", RUNBOOK_INDEX_NAME))

    # Persist
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    to_save: Dict[str, Any] = {}
    for key in _overrides:
        v = _overrides[key]
        to_save[key] = str(v) if isinstance(v, Path) else v
    with open(_SETTINGS_FILE, "w") as f:
        json.dump(to_save, f, indent=2)

    return get_settings()


def get_config_summary() -> str:
    """Returns a formatted summary of current configuration."""
    return f"""
Configuration Summary:
=====================
Primary LLM: {PRIMARY_LLM}
Vision Model: {VISION_MODEL}
Embedding Model: {EMBEDDING_MODEL}

Confidence Threshold: {CONFIDENCE_THRESHOLD}
Min Evidence Sources: {MIN_EVIDENCE_SOURCES}
Max Hypotheses: {MAX_HYPOTHESES}

Vector DB Path: {VECTOR_DB_PATH}
Debug Mode: {DEBUG_MODE}
"""


if __name__ == "__main__":
    print(get_config_summary())
