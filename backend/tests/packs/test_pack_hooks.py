"""Ganchos opcionais do Pack: nome errado falha no registro, nome certo dispara."""

from datetime import datetime, timezone

import pytest

from app.agent.pack_hooks import InvalidPackHookError, run_reply_delivered, run_session_start, validate_pack_hooks
from app.packs import registry
from app.packs.catalog_orders.pack import CatalogOrdersPack


class _Base:
    name = "teste"

    def tools(self):
        return []

    def system_prompt_section(self, ctx) -> str:
        return ""

    def turn_context(self, ctx) -> str:
        return ""


class PackWithTypo(_Base):
    def on_reply_deliverd(self, db, conversation, turn_id, at) -> None:  # "deliverd": nunca dispararia
        raise AssertionError("não deveria ser chamado")


class PackWithUnknownHook(_Base):
    def on_turn_start(self, db, conversation) -> None: ...


class PackWithHooks(_Base):
    def __init__(self):
        self.calls = []

    def on_session_start(self, db, conversation) -> None:
        self.calls.append(("session", conversation))

    def on_reply_delivered(self, db, conversation, turn_id, at) -> None:
        self.calls.append(("reply", turn_id))


def test_hook_with_a_wrong_name_fails_at_pack_registration(monkeypatch):
    monkeypatch.setattr(registry, "PACKS_BY_BUSINESS_TYPE", {})

    with pytest.raises(InvalidPackHookError, match="on_reply_deliverd"):
        registry.register_pack("oficina", PackWithTypo)

    assert "oficina" not in registry.PACKS_BY_BUSINESS_TYPE


def test_error_lists_the_valid_hook_names():
    with pytest.raises(InvalidPackHookError, match="on_reply_delivered, on_session_start"):
        validate_pack_hooks(PackWithUnknownHook())


def test_pack_with_valid_hooks_and_pack_without_hooks_register(monkeypatch):
    monkeypatch.setattr(registry, "PACKS_BY_BUSINESS_TYPE", {})

    registry.register_pack("com-ganchos", PackWithHooks)
    registry.register_pack("sem-ganchos", _Base)

    assert set(registry.PACKS_BY_BUSINESS_TYPE) == {"com-ganchos", "sem-ganchos"}


def test_shipped_packs_pass_the_validation():
    validate_pack_hooks(CatalogOrdersPack())
    for factory in registry.PACKS_BY_BUSINESS_TYPE.values():
        validate_pack_hooks(factory())


def test_hooks_are_dispatched_only_to_packs_that_implement_them():
    with_hooks, without = PackWithHooks(), _Base()
    at = datetime(2026, 10, 19, 23, 0, tzinfo=timezone.utc)

    run_session_start([without, with_hooks], db=None, conversation="conv")
    run_reply_delivered([without, with_hooks], None, "conv", "turn-1", at)

    assert with_hooks.calls == [("session", "conv"), ("reply", "turn-1")]
