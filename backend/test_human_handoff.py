"""
Test script to validate Human-in-the-Loop handoff triggers.
Tests various scenarios to ensure agents call humans appropriately.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Palavras-chave que devem forçar handoff para humano (problemas de pedido/empresa)
HUMAN_HANDOFF_KEYWORDS = [
    "gerente", "supervisor", "diretor", "dono", "proprietário",
    "falar com dono", "falar com gerente", "falar com supervisor",
    "problema com pedido", "pedido errado", "pedido não chegou",
    "reclamação grave", "insatisfação", "muito insatisfeito",
    "cancelei tudo", "quero meu dinheiro de volta", "reembolso",
    "advogado", "procon", "denunciar", "processar",
    "atendimento ruim", "péssimo atendimento",
    "nunca mais compro", "jamais compro",
    "empresa", "negócio", "propriedade", "dono da empresa"
]


def _should_trigger_human_handoff(message: str, intent: str, flow_stage: str) -> tuple[bool, str]:
    """
    Verifica se deve forçar handoff para humano baseado em palavras-chave e contexto.

    Returns:
        (should_handoff, reason)
    """
    message_lower = message.lower().strip()

    # Verificar palavras-chave de handoff
    for keyword in HUMAN_HANDOFF_KEYWORDS:
        if keyword in message_lower:
            return True, f"Palavra-chave de handoff detectada: '{keyword}'"

    # Verificar contextos específicos de pedido que requerem humano
    if intent == "suporte":
        return True, "Intenção de suporte detectada - requer intervenção humana"

    if intent == "status_pedido" and flow_stage == "pedido_finalizado":
        # Se cliente está perguntando sobre pedido finalizado, pode ser problema
        for problem_keyword in ["não chegou", "atraso", "errado", "problema"]:
            if problem_keyword in message_lower:
                return True, f"Problema com pedido finalizado: '{problem_keyword}'"

    return False, ""


# Test scenarios with expected behavior
TEST_SCENARIOS = [
    {
        "name": "Pedido normal - deve continuar com agente",
        "message": "Quero pedir uma pizza margherita",
        "expected_handoff": False,
        "expected_reason": None
    },
    {
        "name": "Cliente pede para falar com gerente - deve acionar handoff",
        "message": "Quero falar com o gerente da empresa",
        "expected_handoff": True,
        "expected_reason": "Palavra-chave de handoff detectada"
    },
    {
        "name": "Reclamação grave - deve acionar handoff",
        "message": "Estou muito insatisfeito, quero falar com o dono da empresa",
        "expected_handoff": True,
        "expected_reason": "Palavra-chave de handoff detectada"
    },
    {
        "name": "Problema com pedido não entregue - deve acionar handoff",
        "message": "Meu pedido não chegou, já passou 2 horas",
        "expected_handoff": True,
        "expected_reason": "Palavra-chave de handoff detectada"
    },
    {
        "name": "Cliente pede reembolso - deve acionar handoff",
        "message": "Quero meu dinheiro de volta, cancelei tudo",
        "expected_handoff": True,
        "expected_reason": "Palavra-chave de handoff detectada"
    },
    {
        "name": "Ameaça de processo - deve acionar handoff",
        "message": "Vou processar a empresa se não resolverem isso",
        "expected_handoff": True,
        "expected_reason": "Palavra-chave de handoff detectada"
    },
    {
        "name": "Consulta cardápio normal - deve continuar com agente",
        "message": "Me mostra o cardápio de pizzas",
        "expected_handoff": False,
        "expected_reason": None
    },
    {
        "name": "Cliente menciona PROCON - deve acionar handoff",
        "message": "Vou fazer uma reclamação no PROCON",
        "expected_handoff": True,
        "expected_reason": "Palavra-chave de handoff detectada"
    },
    {
        "name": "Atendimento ruim - deve acionar handoff",
        "message": "O atendimento está péssimo, quero falar com supervisor",
        "expected_handoff": True,
        "expected_reason": "Palavra-chave de handoff detectada"
    },
    {
        "name": "Status de pedido normal - deve continuar com agente",
        "message": "Como está meu pedido?",
        "expected_handoff": False,
        "expected_reason": None
    }
]


async def test_handoff_trigger():
    """Test handoff trigger logic directly."""
    print("\n" + "="*80)
    print("TESTANDO GATILHOS DE HUMAN-IN-THE-LOOP")
    print("="*80 + "\n")

    passed = 0
    failed = 0

    for scenario in TEST_SCENARIOS:
        should_handoff, reason = _should_trigger_human_handoff(
            scenario["message"],
            intent="pedido",  # Default intent for testing
            flow_stage="saudacao"
        )

        expected = scenario["expected_handoff"]
        success = (should_handoff == expected)

        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {scenario['name']}")
        print(f"  Mensagem: {scenario['message']}")
        print(f"  Esperado: handoff={expected}, razão='{scenario['expected_reason']}'")
        print(f"  Obtido: handoff={should_handoff}, razão='{reason}'")

        if success:
            passed += 1
        else:
            failed += 1
            print(f"  ⚠️  MISMATCH!")

        print()

    print("="*80)
    print(f"RESULTADOS: {passed} passaram, {failed} falharam de {len(TEST_SCENARIOS)} testes")
    print("="*80 + "\n")

    return failed == 0


async def main():
    """Run all tests."""
    print("\n🧪 INICIANDO TESTES DE HUMAN-IN-THE-LOOP\n")

    # Test trigger logic
    trigger_test_passed = await test_handoff_trigger()

    if trigger_test_passed:
        print("\n✅ Todos os testes de gatilho passaram!")
        return 0
    else:
        print("\n❌ Alguns testes de gatilho falharam")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
