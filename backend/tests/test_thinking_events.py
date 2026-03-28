"""
Tests for thinking_token events emitted during streaming inference.

Validates:
- VAL-BE-008: Eventos thinking_token chegam ao frontend via socket.io
- VAL-BE-009: thinking_end event includes summary do reasoning
- VAL-BE-010: LM Studio indisponível — fallback gracioso sem crash
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Any, Dict, List, AsyncGenerator, Tuple
import json


# Create a mock stream generator for testing
async def mock_stream_generator(
    thinking_content: str = "Raciocinando...",
    response_content: str = "Resposta aqui."
) -> AsyncGenerator[Tuple[str, str], None]:
    """Generate mock streaming tokens."""
    for char in thinking_content:
        yield ("thinking", char)
    for char in response_content:
        yield ("response", char)


@pytest.mark.asyncio
async def test_generate_response_node_calls_streaming_method():
    """VAL-BE-008: generate_response_node must call astream_chat_completion_with_thinking() instead of chat_completion()"""
    from app.agents.graph.nodes import generate_response_node
    from app.services.inference_service import inference_service

    # Track calls
    stream_calls = []
    
    async def mock_stream(*args, **kwargs):
        stream_calls.append((args, kwargs))
        for char in "Hi":
            yield ("response", char)

    # Patch the streaming method and realtime bus
    with patch.object(inference_service, "astream_chat_completion_with_thinking", mock_stream):
        with patch("app.agents.graph.nodes.realtime_event_bus") as mock_bus:
            mock_bus.publish = AsyncMock()
            
            # Create a minimal state for testing
            state = {
                "current_message": "Olá, como vai?",
                "intent": "outro",
                "conversation_id": "test-conv-123",
                "instance_name": "test-instance",
                "cardapio_context": None,
                "pedido_atual": [],
                "_history_text": "",
            }

            # Patch the _is_nemotron_model to return False so we use the main flow
            with patch("app.agents.graph.nodes._is_nemotron_model", return_value=False):
                result = await generate_response_node(state)

    # Verify the streaming method was called
    assert len(stream_calls) > 0, "astream_chat_completion_with_thinking should have been called"


@pytest.mark.asyncio
async def test_thinking_tokens_published_during_stream():
    """VAL-BE-008: For each ('thinking', token), publish a thinking_token event"""
    from app.agents.graph.nodes import generate_response_node
    from app.services.inference_service import inference_service

    # Track the publish calls
    published_events: List[Dict[str, Any]] = []

    async def capture_publish(event: Dict[str, Any]) -> None:
        published_events.append(event)

    # Create mock stream with known thinking tokens
    async def mock_stream_with_thinking(*args, **kwargs):
        tokens = ["O", "l", "á", "!"]
        for token in tokens:
            yield ("thinking", token)
        yield ("response", "H")
        yield ("response", "i")

    with patch.object(inference_service, "astream_chat_completion_with_thinking", mock_stream_with_thinking):
        with patch("app.agents.graph.nodes.realtime_event_bus") as mock_bus:
            mock_bus.publish = capture_publish
            
            state = {
                "current_message": "Test message",
                "intent": "outro",
                "conversation_id": "test-conv-456",
                "instance_name": "test-instance",
                "cardapio_context": None,
                "pedido_atual": [],
                "_history_text": "",
            }

            with patch("app.agents.graph.nodes._is_nemotron_model", return_value=False):
                await generate_response_node(state)

    # Find thinking_token events
    thinking_token_events = [
        e for e in published_events
        if e.get("type") == "thinking" and e.get("payload", {}).get("event") == "thinking_token"
    ]

    # Should have 4 thinking_token events (one for each thinking token)
    assert len(thinking_token_events) == 4

    # Verify event structure
    for event in thinking_token_events:
        assert event["type"] == "thinking"
        assert "payload" in event
        assert event["payload"]["event"] == "thinking_token"
        assert "data" in event["payload"]
        assert "token" in event["payload"]["data"]


@pytest.mark.asyncio
async def test_thinking_end_includes_summary():
    """VAL-BE-009: thinking_end event includes data.summary = first 120 chars of thinking_content"""
    from app.agents.graph.nodes import generate_response_node
    from app.services.inference_service import inference_service

    published_events: List[Dict[str, Any]] = []

    async def capture_publish(event: Dict[str, Any]) -> None:
        published_events.append(event)

    # Create a longer thinking content to test summary truncation
    thinking_content = "A" * 150  # 150 chars of thinking

    async def mock_stream_with_long_thinking(*args, **kwargs):
        for char in thinking_content:
            yield ("thinking", char)
        yield ("response", "R")
        yield ("response", "e")
        yield ("response", "s")
        yield ("response", "p")

    with patch.object(inference_service, "astream_chat_completion_with_thinking", mock_stream_with_long_thinking):
        with patch("app.agents.graph.nodes.realtime_event_bus") as mock_bus:
            mock_bus.publish = capture_publish
            
            state = {
                "current_message": "Test message",
                "intent": "outro",
                "conversation_id": "test-conv-789",
                "instance_name": "test-instance",
                "cardapio_context": None,
                "pedido_atual": [],
                "_history_text": "",
            }

            with patch("app.agents.graph.nodes._is_nemotron_model", return_value=False):
                await generate_response_node(state)

    # Find thinking_end event
    thinking_end_events = [
        e for e in published_events
        if e.get("type") == "thinking" and e.get("payload", {}).get("event") == "thinking_end"
    ]

    assert len(thinking_end_events) == 1
    thinking_end = thinking_end_events[0]

    # Verify summary is present and truncated to 120 chars
    summary = thinking_end["payload"]["data"]["summary"]
    assert summary is not None
    assert len(summary) <= 120
    assert summary == "A" * 120  # First 120 chars


@pytest.mark.asyncio
async def test_final_response_is_response_tokens_only():
    """VAL-BE-005: Final LLM response stored in state is the accumulated response tokens (no thinking content)"""
    from app.agents.graph.nodes import generate_response_node
    from app.services.inference_service import inference_service

    async def mock_stream_with_mixed(*args, **kwargs):
        # Thinking content
        for char in "<think>Secret reasoning</think>":
            yield ("thinking", char)
        # Response content
        for char in "Hello, user!":
            yield ("response", char)

    state = {
        "current_message": "Hi",
        "intent": "outro",
        "conversation_id": "test-conv-101",
        "cardapio_context": None,
        "pedido_atual": [],
        "_history_text": "",
    }

    with patch.object(inference_service, "astream_chat_completion_with_thinking", mock_stream_with_mixed):
        with patch("app.agents.graph.nodes.realtime_event_bus") as mock_bus:
            mock_bus.publish = AsyncMock()
            with patch("app.agents.graph.nodes._is_nemotron_model", return_value=False):
                result = await generate_response_node(state)

    # Verify the final response contains only the response tokens, not thinking content
    assert "response" in result
    assert result["response"] == "Hello, user!"
    assert "Secret reasoning" not in result["response"]
    assert "<think>" not in result["response"]
    assert "</think>" not in result["response"]


@pytest.mark.asyncio
async def test_lm_studio_error_fallback():
    """VAL-BE-010: If LM Studio errors during streaming: thinking_end emitted with summary='Erro ao gerar resposta', no crash"""
    from app.agents.graph.nodes import generate_response_node
    from app.services.inference_service import inference_service

    published_events: List[Dict[str, Any]] = []

    async def capture_publish(event: Dict[str, Any]) -> None:
        published_events.append(event)

    # Simulate an error during streaming
    async def mock_stream_error(*args, **kwargs):
        yield ("thinking", "S")
        yield ("thinking", "t")
        yield ("thinking", "a")
        raise Exception("LM Studio connection failed")

    state = {
        "current_message": "Test",
        "intent": "outro",
        "conversation_id": "test-conv-error",
        "cardapio_context": None,
        "pedido_atual": [],
        "_history_text": "",
    }

    with patch.object(inference_service, "astream_chat_completion_with_thinking", mock_stream_error):
        with patch("app.agents.graph.nodes.realtime_event_bus") as mock_bus:
            mock_bus.publish = capture_publish
            with patch("app.agents.graph.nodes._is_nemotron_model", return_value=False):
                # Should not raise exception
                result = await generate_response_node(state)

    # Verify we got an error response
    assert "response" in result
    assert "error" in result

    # Verify thinking_end was emitted with error summary
    thinking_end_events = [
        e for e in published_events
        if e.get("type") == "thinking" and e.get("payload", {}).get("event") == "thinking_end"
    ]

    assert len(thinking_end_events) == 1
    summary = thinking_end_events[0]["payload"]["data"]["summary"]
    assert "Erro" in summary or "error" in summary.lower()


@pytest.mark.asyncio
async def test_super_agents_generate_response_node_calls_streaming():
    """VAL-BE-008: super_agents/graph/nodes.py also uses streaming (for consistency)"""
    from app.super_agents.graph.nodes import generate_response_node
    from app.services.inference_service import inference_service

    published_events: List[Dict[str, Any]] = []

    async def capture_publish(event: Dict[str, Any]) -> None:
        published_events.append(event)

    async def mock_stream(*args, **kwargs):
        # Yield thinking tokens first
        for char in "Thinking... ":
            yield ("thinking", char)
        # Then response tokens
        for char in "Test response":
            yield ("response", char)

    # Create a minimal SuperAgentState
    state = {
        "current_message": "Analyze the data",
        "session_id": "test-session-123",
        "company_id": "test-company-456",
        "messages": [],
        "intent": "analysis",
        "thinking_content": "",
    }

    with patch.object(inference_service, "astream_chat_completion_with_thinking", mock_stream):
        with patch("app.super_agents.graph.nodes.realtime_event_bus") as mock_bus:
            mock_bus.publish = capture_publish
            result = await generate_response_node(state)

    # Verify we have thinking_token events
    thinking_token_events = [
        e for e in published_events
        if e.get("type") == "thinking" and e.get("payload", {}).get("event") == "thinking_token"
    ]
    assert len(thinking_token_events) > 0

    # Verify thinking_end with summary
    thinking_end_events = [
        e for e in published_events
        if e.get("type") == "thinking" and e.get("payload", {}).get("event") == "thinking_end"
    ]
    assert len(thinking_end_events) == 1
    assert "summary" in thinking_end_events[0]["payload"]["data"]


@pytest.mark.asyncio
async def test_super_agents_persist_full_thinking_content():
    """Assistant history must keep the full model thinking content, not only the summary."""
    from app.super_agents.graph.nodes import generate_response_node
    from app.services.inference_service import inference_service

    async def mock_stream(*args, **kwargs):
        for char in "Pensamento completo do modelo":
            yield ("thinking", char)
        for char in "Resposta final":
            yield ("response", char)

    state = {
        "current_message": "Explique o sistema",
        "session_id": "test-session-thinking-content",
        "company_id": "test-company-thinking-content",
        "messages": [],
        "intent": "analysis",
        "thinking_content": "Contexto anterior",
    }

    with patch.object(inference_service, "astream_chat_completion_with_thinking", mock_stream):
        with patch("app.super_agents.graph.nodes.realtime_event_bus") as mock_bus:
            mock_bus.publish = AsyncMock()
            result = await generate_response_node(state)

    assert result["thinking_content"] == "Pensamento completo do modelo"


@pytest.mark.asyncio
async def test_super_agents_use_thinking_as_response_when_model_has_no_separate_output():
    """If the model streams only thinking tokens, the final chat response should reuse that content."""
    from app.super_agents.graph.nodes import generate_response_node
    from app.services.inference_service import inference_service

    async def mock_stream(*args, **kwargs):
        for char in "Resposta sem separação explícita":
            yield ("thinking", char)

    state = {
        "current_message": "Mostre o status",
        "session_id": "test-session-fallback-response",
        "company_id": "test-company-fallback-response",
        "messages": [],
        "intent": "analysis",
        "thinking_content": "",
    }

    with patch.object(inference_service, "astream_chat_completion_with_thinking", mock_stream):
        with patch("app.super_agents.graph.nodes.realtime_event_bus") as mock_bus:
            mock_bus.publish = AsyncMock()
            result = await generate_response_node(state)

    assert result["response"] == "Resposta sem separação explícita"


@pytest.mark.asyncio
async def test_thinking_start_event_emitted():
    """Verify that thinking_start event is emitted at the beginning"""
    from app.agents.graph.nodes import generate_response_node
    from app.services.inference_service import inference_service

    published_events: List[Dict[str, Any]] = []

    async def capture_publish(event: Dict[str, Any]) -> None:
        published_events.append(event)

    async def mock_stream(*args, **kwargs):
        yield ("thinking", "S")
        yield ("response", "R")

    state = {
        "current_message": "Hello",
        "intent": "outro",
        "conversation_id": "test-conv-start",
        "cardapio_context": None,
        "pedido_atual": [],
        "_history_text": "",
    }

    with patch.object(inference_service, "astream_chat_completion_with_thinking", mock_stream):
        with patch("app.agents.graph.nodes.realtime_event_bus") as mock_bus:
            mock_bus.publish = capture_publish
            with patch("app.agents.graph.nodes._is_nemotron_model", return_value=False):
                await generate_response_node(state)

    # Find thinking_start event
    thinking_start_events = [
        e for e in published_events
        if e.get("type") == "thinking" and e.get("payload", {}).get("event") == "thinking_start"
    ]

    assert len(thinking_start_events) == 1
    assert thinking_start_events[0]["payload"]["conversation_id"] == "test-conv-start"


@pytest.mark.asyncio
async def test_event_schema_correct():
    """Verify the realtime event bus publish() call uses the correct schema"""
    from app.agents.graph.nodes import generate_response_node
    from app.services.inference_service import inference_service

    published_events: List[Dict[str, Any]] = []

    async def capture_publish(event: Dict[str, Any]) -> None:
        published_events.append(event)

    async def mock_stream_single(*args, **kwargs):
        yield ("thinking", "X")
        yield ("response", "Y")

    state = {
        "current_message": "Test",
        "intent": "outro",
        "conversation_id": "test-conv-schema",
        "cardapio_context": None,
        "pedido_atual": [],
        "_history_text": "",
    }

    with patch.object(inference_service, "astream_chat_completion_with_thinking", mock_stream_single):
        with patch("app.agents.graph.nodes.realtime_event_bus") as mock_bus:
            mock_bus.publish = capture_publish
            with patch("app.agents.graph.nodes._is_nemotron_model", return_value=False):
                await generate_response_node(state)

    # Check thinking_token event schema
    thinking_token_event = next(
        e for e in published_events
        if e.get("payload", {}).get("event") == "thinking_token"
    )

    # Expected schema per feature description:
    # {type: 'thinking', instance: ..., conversationId: ..., event: 'thinking_token', data: {token: '...'}}
    assert thinking_token_event["type"] == "thinking"
    assert "conversationId" in thinking_token_event or "conversation_id" in thinking_token_event["payload"]
    assert thinking_token_event["payload"]["event"] == "thinking_token"
    assert "data" in thinking_token_event["payload"]
    assert "token" in thinking_token_event["payload"]["data"]
