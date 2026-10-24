# Imagem única do backend: a mesma serve a API, o worker e a migração (o comando muda, veja docker-compose.example.yml).
#   API:       uvicorn app.main:socket_app --host 0.0.0.0 --port 8000   (CMD padrão)
#   worker:    python scripts/run_worker.py
#   migração:  alembic upgrade head
# Contexto de build: backend/

FROM python:3.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
COPY requirements.txt .
# Só wheels: se uma dependência passar a exigir compilação, o build falha aqui em vez de levar um toolchain para a imagem.
# Se isso acontecer, instale o toolchain (gcc etc.) neste estágio; o estágio final continua sem ele.
RUN /opt/venv/bin/pip install --only-binary=:all: -r requirements.txt


FROM python:3.12-slim-bookworm

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

USER app

EXPOSE 8000

# Só vale para o serviço da API; worker e migração desligam o healthcheck no compose (não escutam na porta 8000).
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

CMD ["uvicorn", "app.main:socket_app", "--host", "0.0.0.0", "--port", "8000"]
