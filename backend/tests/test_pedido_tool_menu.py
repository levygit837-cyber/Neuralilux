import importlib


pedido_tool_module = importlib.import_module("app.agents.tools.pedido_tool")
menu_service_module = importlib.import_module("app.services.menu_catalog_service")


def test_pedido_tool_adds_real_macedos_item_with_correct_price(db, monkeypatch):
    monkeypatch.setattr(pedido_tool_module, "SessionLocal", lambda: db)
    pedido_tool_module._pedidos_ativos.clear()
    pedido_tool_module.set_active_conversation("conv-macedos")
    menu_service_module.sync_macedos_menu_from_json(db, menu_service_module.DEFAULT_MENU_JSON_PATH)

    result = pedido_tool_module.pedido_tool.invoke(
        {
            "acao": "adicionar",
            "item_nome": "Creme de Cebola",
            "quantidade": 2,
            "observacao": "sem parmesão",
        }
    )

    pedido = pedido_tool_module.get_pedido_atual("conv-macedos")

    assert "Creme de Cebola" in result
    assert "R$ 150,00" in result
    assert "sem parmesão" in result
    assert len(pedido) == 1
    assert pedido[0]["nome"] == "Creme de Cebola"
    assert pedido[0]["preco_unitario"] == 75.0
    assert pedido[0]["quantidade"] == 2


def test_pedido_tool_uses_json_fallback_when_menu_not_synced(db, monkeypatch):
    monkeypatch.setattr(pedido_tool_module, "SessionLocal", lambda: db)
    pedido_tool_module._pedidos_ativos.clear()
    pedido_tool_module.set_active_conversation("conv-fallback")

    result = pedido_tool_module.pedido_tool.invoke(
        {
            "acao": "adicionar",
            "item_nome": "Filé à cubana",
            "quantidade": 1,
        }
    )

    pedido = pedido_tool_module.get_pedido_atual("conv-fallback")

    assert "Filé à cubana" in result
    assert "R$ 222,00" in result
    assert len(pedido) == 1
    assert pedido[0]["preco_unitario"] == 222.0


def test_pedido_tool_adds_unavailable_item_by_default(db, monkeypatch):
    """Testa que itens marcados como indisponíveis são adicionados por padrão (sem verificação de estoque)."""
    monkeypatch.setattr(pedido_tool_module, "SessionLocal", lambda: db)
    pedido_tool_module._pedidos_ativos.clear()
    pedido_tool_module.set_active_conversation("conv-indisponivel")
    menu_service_module.sync_macedos_menu_from_json(db, menu_service_module.DEFAULT_MENU_JSON_PATH)

    result = pedido_tool_module.pedido_tool.invoke(
        {
            "acao": "adicionar",
            "item_nome": "BERLIM DELICIOSA",
            "quantidade": 1,
        }
    )

    pedido = pedido_tool_module.get_pedido_atual("conv-indisponivel")

    # Item deve ser adicionado com sucesso, mesmo estando marcado como indisponível
    assert "BERLIM DELICIOSA" in result
    assert len(pedido) == 1
    assert pedido[0]["nome"] == "BERLIM DELICIOSA"
