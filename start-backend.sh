#!/bin/bash
# Script para iniciar o backend no host (dev). O modelo vem de um Gateway cadastrado no banco.

set -euo pipefail

echo "🚀 Iniciando Neuralilux Backend no host..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"

cd "$BACKEND_DIR"

if [ -d "venv" ]; then
    VENV_DIR="venv"
elif [ -d ".venv" ]; then
    VENV_DIR=".venv"
else
    VENV_DIR="venv"
fi

requirements_hash_file="$VENV_DIR/.requirements.sha256"

supports_backend_python() {
    "$1" -c 'import sys; raise SystemExit(0 if (sys.version_info.major, sys.version_info.minor) in {(3, 11), (3, 12)} else 1)'
}

select_python() {
    local candidate=""

    if [ -n "${BACKEND_PYTHON:-}" ] && command -v "${BACKEND_PYTHON}" >/dev/null 2>&1; then
        candidate="$(command -v "${BACKEND_PYTHON}")"
        if supports_backend_python "$candidate"; then
            echo "$candidate"
            return 0
        fi
    fi

    for candidate_name in python3.12 python3.11 python3; do
        if ! command -v "$candidate_name" >/dev/null 2>&1; then
            continue
        fi

        candidate="$(command -v "$candidate_name")"
        if supports_backend_python "$candidate"; then
            echo "$candidate"
            return 0
        fi
    done

    return 1
}

if ! PYTHON_BIN="$(select_python)"; then
    echo "❌ Nenhuma instalação compatível de Python foi encontrada."
    echo "   Use Python 3.11 ou 3.12 e, se preciso, exporte BACKEND_PYTHON=/caminho/do/python."
    exit 1
fi

PYTHON_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')"
echo "🐍 Python selecionado: $PYTHON_BIN ($PYTHON_VERSION)"

if [ -x "$VENV_DIR/bin/python" ]; then
    if ! supports_backend_python "$VENV_DIR/bin/python"; then
        CURRENT_VENV_VERSION="$("$VENV_DIR/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')"
        echo "⚠️  Ambiente virtual atual usa Python $CURRENT_VENV_VERSION, que não é compatível com este backend."
        echo "🧹 Recriando ambiente virtual em $VENV_DIR..."
        rm -rf "$VENV_DIR"
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Criando ambiente virtual em $VENV_DIR..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

echo "📦 Ativando ambiente virtual..."
source "$VENV_DIR/bin/activate"

# O hash cobre os dois arquivos: requirements-dev.txt inclui requirements.txt via `-r`.
current_requirements_hash="$( (command -v sha256sum >/dev/null && cat requirements.txt requirements-dev.txt | sha256sum || cat requirements.txt requirements-dev.txt | shasum -a 256) | awk '{print $1}')"
stored_requirements_hash="$(cat "$requirements_hash_file" 2>/dev/null || true)"

dependency_check_failed=0
if ! python - <<'PY' >/dev/null 2>&1
import importlib.util
import sys

required_modules = ["fastapi", "socketio", "sqlalchemy", "redis", "aio_pika"]
missing = [name for name in required_modules if importlib.util.find_spec(name) is None]
sys.exit(1 if missing else 0)
PY
then
    dependency_check_failed=1
fi

if [ "$current_requirements_hash" != "$stored_requirements_hash" ] || [ "$dependency_check_failed" -eq 1 ]; then
    echo "📥 Sincronizando dependências do backend..."
    pip install -r requirements-dev.txt
    printf '%s\n' "$current_requirements_hash" > "$requirements_hash_file"
fi

# Configurar variáveis de ambiente
export DATABASE_URL="postgresql+psycopg://neuralilux:neuralilux_password@localhost:5434/neuralilux"
export REDIS_URL="redis://:redis_password@localhost:6380/0"
export ENVIRONMENT="development"
export DEBUG="true"

echo "✅ Variáveis de ambiente configuradas:"
echo "   - DATABASE_URL: $DATABASE_URL"
echo "   - REDIS_URL: $REDIS_URL"
echo "   - Gateways de inferência: Configurações > Gateways (ou /api/v1/gateways)"

# Iniciar o backend
echo "🚀 Iniciando servidor FastAPI..."
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
