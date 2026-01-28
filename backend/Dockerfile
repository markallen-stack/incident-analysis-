# Multi-stage build for Incident RAG

# Stage 1: Base image with dependencies
FROM python:3.11-slim as base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Development image
FROM base as development

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

CMD ["python", "-m", "pytest"]

# Stage 3: Production image
FROM base as production

# Copy application code (API, core logic, database layer)
COPY app/ ./app/
COPY core/mcp ./core/mcp/
COPY core/agents/ ./core/agents/
COPY core/prompts/ ./core/prompts/
COPY core/mcp_servers/ ./core/mcp_servers/
COPY core/vector_db/ ./core/vector_db/
COPY core/auth.py ./core/
COPY core/database/ ./core/database/
COPY core/graph.py ./core/
COPY core/claude_client.py ./core/
COPY analyze.py .
COPY config.py .

# Copy data and models (if needed)
COPY data/ ./data/
# COPY /core/vector_db/indexes/ ./core/vector_db/indexes/

# Create non-root user
RUN useradd -m -u 1000 incident-user && \
    chown -R incident-user:incident-user /app

USER incident-user

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import config; print('healthy')" || exit 1

# Default command - run FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]