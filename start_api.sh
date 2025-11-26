#!/bin/bash

# Start Need Scanner FastAPI server
# Usage: ./start_api.sh [port]

PORT=${1:-8000}

echo "🚀 Starting Need Scanner API on port $PORT..."
echo ""
echo "📖 Documentation available at:"
echo "   - Swagger UI: http://localhost:$PORT/docs"
echo "   - ReDoc:      http://localhost:$PORT/redoc"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Activate virtual environment if it exists
if [ -d "env" ]; then
    source env/bin/activate
fi

# Start uvicorn
uvicorn need_scanner.api:app --reload --host 0.0.0.0 --port $PORT
