from unittest.mock import AsyncMock

import pytest

from app.services.socket_service import chat_socket_service


@pytest.mark.asyncio
async def test_emit_realtime_event_normalizes_thinking_payload_for_frontend():
    original_emit = chat_socket_service.server.emit
    chat_socket_service.server.emit = AsyncMock()

    try:
        await chat_socket_service.emit_realtime_event(
            {
                "type": "thinking",
                "instance_name": "company-123",
                "payload": {
                    "conversation_id": "session-abc",
                    "event": "thinking_token",
                    "data": {"token": "A"},
                },
            }
        )
    finally:
        emit_mock = chat_socket_service.server.emit
        chat_socket_service.server.emit = original_emit

    assert emit_mock.await_count == 3

    first_payload = emit_mock.await_args_list[0].args[1]
    assert first_payload["conversationId"] == "session-abc"
    assert first_payload["event"] == "thinking_token"
    assert first_payload["data"] == {"token": "A"}


@pytest.mark.asyncio
async def test_emit_realtime_event_normalizes_response_payload_for_frontend():
    original_emit = chat_socket_service.server.emit
    chat_socket_service.server.emit = AsyncMock()

    try:
        await chat_socket_service.emit_realtime_event(
            {
                "type": "thinking",
                "instance_name": "company-123",
                "payload": {
                    "conversation_id": "session-abc",
                    "event": "response_token",
                    "data": {"token": "B"},
                },
            }
        )
    finally:
        emit_mock = chat_socket_service.server.emit
        chat_socket_service.server.emit = original_emit

    assert emit_mock.await_count == 3

    first_payload = emit_mock.await_args_list[0].args[1]
    assert first_payload["conversationId"] == "session-abc"
    assert first_payload["event"] == "response_token"
    assert first_payload["data"] == {"token": "B"}
