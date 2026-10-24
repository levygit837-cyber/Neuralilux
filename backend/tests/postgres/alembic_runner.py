"""Roda o Alembic como subprocesso contra um banco de teste."""
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import URL

BACKEND_DIR = Path(__file__).resolve().parents[2]


def run_alembic(url: URL, *args: str) -> None:
    """Roda `alembic <args>` contra `url`, como o CI e o deploy fazem (o `env.py` lê `DATABASE_URL`)."""
    # ENVIRONMENT explícito: sem ele a app assume produção e recusa os segredos de exemplo (config.py).
    env = {**os.environ, "ENVIRONMENT": "development", "DATABASE_URL": url.render_as_string(hide_password=False)}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"alembic {' '.join(args)} falhou:\n{result.stdout}\n{result.stderr}"
