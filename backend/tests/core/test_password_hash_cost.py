"""O custo do bcrypt só é reduzido nos testes; em produção o hash continua com o custo padrão."""
import subprocess
import sys

from app.core.security import get_password_hash, verify_password


def test_production_hash_uses_default_cost_12():
    # Processo novo: não herda o custo reduzido que o conftest raiz aplica nesta suíte.
    code = "from app.core.security import get_password_hash; print(get_password_hash('senha'))"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert result.stdout.strip().startswith("$2b$12$")


def test_hash_in_tests_still_verifies():
    hashed = get_password_hash("senha")
    assert verify_password("senha", hashed)
    assert not verify_password("outra", hashed)
