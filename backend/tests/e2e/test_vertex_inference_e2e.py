"""
End-to-End Tests for Vertex AI Inference Service with real API.

WARNING: These tests make actual API calls and consume quota.
Requires VERTEX_API_KEY environment variable to be set.

Run with: pytest tests/e2e/test_vertex_inference_e2e.py -v
"""

import pytest
import os
from typing import List, Dict, Any

# Skip all tests if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("VERTEX_API_KEY"),
    reason="VERTEX_API_KEY not set - skipping E2E tests",
)

from app.services.vertex_inference_service import (
    VertexInferenceService,
    VertexInferenceServiceError,
    InferenceResult,
    ToolCall,
)


@pytest.fixture
def vertex_service():
    """Create Vertex AI service instance for testing."""
    return VertexInferenceService(
        api_key=os.getenv("VERTEX_API_KEY"),
        model="gemini-3.1-flash-lite-preview",
        max_tokens=1024,
        temperature=0.7,
    )


class TestVertexInferenceBasic:
    """Basic inference tests without tools."""

    @pytest.mark.asyncio
    async def test_simple_completion(self, vertex_service):
        """Test basic text completion."""
        messages = [
            {"role": "user", "content": "What is the capital of France?"}
        ]

        result = await vertex_service.generate(messages)

        assert isinstance(result, InferenceResult)
        assert len(result.text) > 0
        assert "Paris" in result.text
        assert result.finish_reason is not None
        print(f"\n✅ Simple completion: {result.text[:100]}...")

    @pytest.mark.asyncio
    async def test_system_prompt(self, vertex_service):
        """Test completion with system prompt."""
        messages = [
            {"role": "user", "content": "Hello!"}
        ]
        system_prompt = "You are a helpful assistant specialized in geography."

        result = await vertex_service.generate(
            messages,
            system_prompt=system_prompt,
        )

        assert isinstance(result, InferenceResult)
        assert len(result.text) > 0
        print(f"\n✅ System prompt completion: {result.text[:100]}...")

    @pytest.mark.asyncio
    async def test_conversation_context(self, vertex_service):
        """Test multi-turn conversation."""
        messages = [
            {"role": "user", "content": "My name is Alice."},
            {"role": "assistant", "content": "Hello Alice! Nice to meet you."},
            {"role": "user", "content": "What's my name?"},
        ]

        result = await vertex_service.generate(messages)

        assert "Alice" in result.text
        print(f"\n✅ Context retention: {result.text[:100]}...")

    @pytest.mark.asyncio
    async def test_temperature_variation(self, vertex_service):
        """Test different temperature settings."""
        messages = [{"role": "user", "content": "Give me a random number between 1 and 100"}]

        # Low temperature (deterministic)
        result_low = await vertex_service.generate(messages, temperature=0.1)

        # High temperature (creative)
        result_high = await vertex_service.generate(messages, temperature=1.0)

        assert len(result_low.text) > 0
        assert len(result_high.text) > 0
        print(f"\n✅ Temperature variation works")


class TestVertexInferenceWithTools:
    """Tool calling tests with real function definitions."""

    @pytest.mark.asyncio
    async def test_single_tool_call(self, vertex_service):
        """Test calling a single tool."""
        tools = [
            {
                "name": "get_weather",
                "description": "Get the current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name, e.g., 'London' or 'New York'",
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "description": "Temperature unit",
                        },
                    },
                    "required": ["location"],
                },
            }
        ]

        messages = [
            {"role": "user", "content": "What's the weather in Tokyo?"}
        ]

        result = await vertex_service.generate(messages, tools=tools)

        assert isinstance(result, InferenceResult)
        assert len(result.tool_calls) >= 1
        assert result.tool_calls[0].name == "get_weather"
        assert "location" in result.tool_calls[0].args
        assert "tokyo" in result.tool_calls[0].args["location"].lower()
        print(f"\n✅ Tool call: {result.tool_calls[0].name}({result.tool_calls[0].args})")

    @pytest.mark.asyncio
    async def test_multiple_tool_options(self, vertex_service):
        """Test model choosing between multiple tools."""
        tools = [
            {
                "name": "add_item",
                "description": "Add an item to a list",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item": {"type": "string"},
                        "quantity": {"type": "integer"},
                    },
                    "required": ["item", "quantity"],
                },
            },
            {
                "name": "remove_item",
                "description": "Remove an item from a list",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item": {"type": "string"},
                    },
                    "required": ["item"],
                },
            },
        ]

        messages = [
            {"role": "user", "content": "Add 2 pizzas to my order"}
        ]

        result = await vertex_service.generate(messages, tools=tools)

        if result.tool_calls:
            assert result.tool_calls[0].name == "add_item"
            args = result.tool_calls[0].args
            assert args.get("item").lower() in ["pizza", "pizzas"]
            assert args.get("quantity") == 2
            print(f"\n✅ Tool selected: {result.tool_calls[0].name}({args})")

    @pytest.mark.asyncio
    async def test_complex_parameters(self, vertex_service):
        """Test tool with complex nested parameters."""
        tools = [
            {
                "name": "create_order",
                "description": "Create a new order with items and delivery address",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_name": {"type": "string"},
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "product_id": {"type": "string"},
                                    "quantity": {"type": "integer"},
                                    "price": {"type": "number"},
                                },
                            },
                        },
                        "delivery_address": {
                            "type": "object",
                            "properties": {
                                "street": {"type": "string"},
                                "city": {"type": "string"},
                                "zip": {"type": "string"},
                            },
                        },
                    },
                    "required": ["customer_name", "items"],
                },
            }
        ]

        messages = [
            {
                "role": "user",
                "content": "Create an order for John with 2 products (ABC123 at $10 each, XYZ789 at $25 each) delivered to 123 Main St, Boston, 02101"
            }
        ]

        result = await vertex_service.generate(messages, tools=tools)

        if result.tool_calls:
            assert result.tool_calls[0].name == "create_order"
            args = result.tool_calls[0].args
            assert "customer_name" in args
            assert "items" in args
            assert isinstance(args["items"], list)
            print(f"\n✅ Complex tool call: {args}")


class TestVertexInferenceStreaming:
    """Streaming response tests."""

    @pytest.mark.asyncio
    async def test_basic_streaming(self, vertex_service):
        """Test streaming text generation."""
        messages = [{"role": "user", "content": "Count from 1 to 5"}]

        chunks = []
        async for chunk in vertex_service.generate_stream(messages):
            chunks.append(chunk)

        full_text = "".join(chunks)
        assert len(full_text) > 0
        assert len(chunks) > 1  # Should receive multiple chunks
        print(f"\n✅ Streaming: Received {len(chunks)} chunks, total length {len(full_text)}")


class TestVertexInferenceErrorHandling:
    """Error handling and edge cases."""

    def test_invalid_api_key(self):
        """Test behavior with invalid API key."""
        with pytest.raises(VertexInferenceServiceError):
            service = VertexInferenceService(api_key="invalid_key")
            # The error might occur during init or first request

    @pytest.mark.asyncio
    async def test_empty_messages(self, vertex_service):
        """Test with empty message list."""
        with pytest.raises(VertexInferenceServiceError):
            await vertex_service.generate([])

    @pytest.mark.asyncio
    async def test_very_long_prompt(self, vertex_service):
        """Test with very long prompt approaching token limits."""
        long_text = "Hello. " * 1000  # ~6000 characters
        messages = [{"role": "user", "content": long_text}]

        result = await vertex_service.generate(messages, max_tokens=100)

        assert isinstance(result, InferenceResult)
        print(f"\n✅ Long prompt handled: response length {len(result.text)}")


class TestVertexInferenceWithBackendTools:
    """Integration tests with actual backend tool schemas."""

    @pytest.mark.asyncio
    async def test_cardapio_tool(self, vertex_service):
        """Test with cardapio_tool schema."""
        tools = [
            {
                "name": "cardapio_tool",
                "description": "Busca e consulta itens do cardápio do restaurante",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Termo de busca para o cardápio (ex: 'pizza', 'bebidas')",
                        },
                        "categoria": {
                            "type": "string",
                            "enum": ["pizzas", "bebidas", "sobremesas", "lanches"],
                            "description": "Categoria específica do cardápio",
                        },
                    },
                },
            }
        ]

        messages = [
            {"role": "user", "content": "Quero ver as pizzas do cardápio"}
        ]

        result = await vertex_service.generate(messages, tools=tools)

        if result.tool_calls:
            assert result.tool_calls[0].name == "cardapio_tool"
            args = result.tool_calls[0].args
            assert "query" in args or "categoria" in args
            print(f"\n✅ Cardapio tool: {args}")

    @pytest.mark.asyncio
    async def test_pedido_tool(self, vertex_service):
        """Test with pedido_tool schema."""
        tools = [
            {
                "name": "pedido_tool",
                "description": "Gerencia pedidos - adiciona, remove ou consulta itens",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["add", "remove", "view", "clear"],
                            "description": "Ação a realizar no pedido",
                        },
                        "item": {
                            "type": "string",
                            "description": "Nome do item (para add/remove)",
                        },
                        "quantity": {
                            "type": "integer",
                            "description": "Quantidade do item",
                        },
                    },
                    "required": ["action"],
                },
            }
        ]

        messages = [
            {"role": "user", "content": "Adiciona 2 pizzas de calabresa ao meu pedido"}
        ]

        result = await vertex_service.generate(messages, tools=tools)

        if result.tool_calls:
            assert result.tool_calls[0].name == "pedido_tool"
            args = result.tool_calls[0].args
            assert args.get("action") == "add"
            assert "item" in args
            print(f"\n✅ Pedido tool: {args}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
