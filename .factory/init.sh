#!/bin/bash
# Mission init script — idempotent environment setup
# Run at start of each worker session

set -euo pipefail

PROJECT_ROOT="/home/levybonito/Projetos/Neuralilux"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo "=== Mission Init ==="

# 1. Verify backend venv exists and has dependencies
if [ -f "$BACKEND_DIR/venv/bin/python" ]; then
    echo "✓ Backend venv exists (Python $("$BACKEND_DIR/venv/bin/python" --version 2>&1))"
else
    echo "Creating backend venv..."
    python3.11 -m venv "$BACKEND_DIR/venv"
    "$BACKEND_DIR/venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt"
fi

# 2. Verify Docker services are running
echo "--- Checking Docker services ---"
for container in neuralilux-redis neuralilux-postgres neuralilux-rabbitmq neuralilux-evolution; do
    if docker ps --format '{{.Names}}' | grep -q "^$container$"; then
        echo "✓ $container running"
    else
        echo "⚠ $container not running — starting..."
        cd "$PROJECT_ROOT" && docker compose up -d
        break
    fi
done

# 3. Verify LM Studio accessible
echo "--- Checking LM Studio ---"
if curl -sf http://localhost:1234/v1/models > /dev/null 2>&1; then
    echo "✓ LM Studio accessible at localhost:1234"
else
    echo "⚠ LM Studio not accessible at localhost:1234 — inference tests may fail"
fi

# 4. Verify frontend deps
if [ -d "$FRONTEND_DIR/node_modules" ]; then
    echo "✓ Frontend node_modules exist"
else
    echo "Installing frontend dependencies..."
    cd "$FRONTEND_DIR" && npm install
fi

echo "=== Init complete ==="
