"""Falha se algum `.py` de `backend/app` passar de 400 linhas (migrações do Alembic ficam fora).

Uso (a partir de `backend/`): `python scripts/check_max_lines.py`
"""
import sys
from pathlib import Path

LIMITE = 400
RAIZ = Path(__file__).resolve().parent.parent / "app"


def main() -> int:
    estourados = []
    for arquivo in sorted(RAIZ.rglob("*.py")):
        if "alembic" in arquivo.relative_to(RAIZ).parts:
            continue
        with arquivo.open(encoding="utf-8") as f:
            linhas = sum(1 for _ in f)
        if linhas > LIMITE:
            estourados.append((arquivo.relative_to(RAIZ.parent), linhas))

    for caminho, linhas in estourados:
        print(f"{caminho}: {linhas} linhas (limite {LIMITE})")
    if estourados:
        print(f"{len(estourados)} arquivo(s) acima de {LIMITE} linhas: divida por assunto.")
        return 1
    print(f"OK: nenhum .py de app/ acima de {LIMITE} linhas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
