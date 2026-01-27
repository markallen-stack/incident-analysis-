#!/bin/bash
# Start the Incident Analysis API

echo "🚀 Starting Incident Analysis API..."

# Check if in correct directory
if [ ! -f "config.py" ]; then
    echo "❌ Error: Must run from project root (incident_rag directory)"
    exit 1
fi

# Check if API directory exists
if [ ! -d "api" ]; then
    echo "📁 Creating api directory..."
    mkdir -p api
    touch api/__init__.py
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: Virtual environment not activated"
    echo "   Run: source venv/bin/activate"
    echo ""
fi

# Install FastAPI dependencies if needed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "📦 Installing FastAPI dependencies..."
    pip install fastapi uvicorn python-multipart
fi

# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Start the API
echo ""
echo "✅ Starting API server..."
echo "   URL: http://localhost:8000"
echo "   Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000