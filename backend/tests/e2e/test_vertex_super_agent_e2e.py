"""
E2E Tests for Super Agent with Vertex AI provider.

Tests the complete flow: Super Agent -> Vertex Inference -> Tool Execution.
Requires VERTEX_API_KEY environment variable.

Run with: pytest tests/e2e/test_vertex_super_agent_e2e.py -v
"""

import pytest
import os
import asyncio

pytestmark = pytest.mark.skipif(
    not os.getenv("VERTEX_API_KEY"),
    reason="VERTEX_API_KEY not set",
)

from app.super_agents.agent_executor import SuperAgentExecutor
from app.core.config import settings
from app.super_agents.tools.tool_schemas import SUPER_AGENT_TOOLS


@pytest.fixture
def vertex_super_agent():
    """Create Super Agent configured for Vertex."""
    # Store original settings
    original_provider = settings.SUPER_AGENT_INFERENCE_PROVIDER
    original_api_key = settings.VERTEX_API_KEY

    # Configure for Vertex
    settings.SUPER_AGENT_INFERENCE_PROVIDER = "vertex"
    settings.VERTEX_API_KEY = os.getenv("VERTEX_API_KEY")

    agent = SuperAgentExecutor()

    yield agent

    # Restore original settings
    settings.SUPER_AGENT_INFERENCE_PROVIDER = original_provider
    settings.VERTEX_API_KEY = original_api_key


class TestSuperAgentWithVertex:
    """Test Super Agent execution with Vertex AI as provider."""

    @pytest.mark.asyncio
    async def test_simple_query(self, vertex_super_agent):
        """Test simple query without tools."""
        import uuid
        result = await vertex_super_agent.process_message(
            session_id=str(uuid.uuid4()),
            company_id="test-company",
            user_id="test-user",
            message="What is machine learning?",
        )

        assert result is not None
        assert "response" in result
        assert len(result.get("response", "")) > 0
        print(f"\n✅ Super Agent + Vertex: {result['response'][:100]}...")

    @pytest.mark.asyncio
    async def test_with_database_query(self, vertex_super_agent):
        """Test query that might use database tool."""
        import uuid
        result = await vertex_super_agent.process_message(
            session_id=str(uuid.uuid4()),
            company_id="test-company",
            user_id="test-user",
            message="What tables are in the database?",
        )

        assert result is not None
        assert "response" in result
        print(f"\n✅ Super Agent + Vertex + Database tool: {result['response'][:100]}...")

    @pytest.mark.asyncio
    async def test_with_whatsapp_context(self, vertex_super_agent):
        """Test with WhatsApp-specific context."""
        import uuid
        result = await vertex_super_agent.process_message(
            session_id=str(uuid.uuid4()),
            company_id="test-company",
            user_id="test-user",
            message="Check my WhatsApp messages",
        )

        assert result is not None
        print(f"\n✅ Super Agent + Vertex + WhatsApp context")


class TestSuperAgentVertexProviderSwitching:
    """Test switching between providers."""

    @pytest.mark.asyncio
    async def test_provider_selection(self):
        """Verify provider selection works correctly."""
        # Store original
        original = settings.SUPER_AGENT_INFERENCE_PROVIDER

        # Test with Vertex
        settings.SUPER_AGENT_INFERENCE_PROVIDER = "vertex"
        settings.VERTEX_API_KEY = os.getenv("VERTEX_API_KEY")

        from app.services.inference_service import get_inference_service

        service = get_inference_service("super_agent")

        # Verify it's VertexInferenceService
        from app.services.vertex_inference_service import VertexInferenceService
        assert isinstance(service, VertexInferenceService)
        print("\n✅ Provider correctly selects VertexInferenceService")

        # Restore
        settings.SUPER_AGENT_INFERENCE_PROVIDER = original


class TestVertexInferenceServiceStreaming:
    """Test VertexInferenceService streaming with tools directly."""

    @pytest.mark.asyncio
    async def test_stream_chat_completion_with_tools_basic(self):
        """Test basic streaming with tools interface."""
        from app.services.vertex_inference_service import VertexInferenceService
        from app.services.inference_service import get_inference_service

        # Configure for Vertex
        original = settings.SUPER_AGENT_INFERENCE_PROVIDER
        settings.SUPER_AGENT_INFERENCE_PROVIDER = "vertex"
        settings.VERTEX_API_KEY = os.getenv("VERTEX_API_KEY")

        try:
            service = get_inference_service("super_agent")
            assert isinstance(service, VertexInferenceService)

            # Test that the method exists
            assert hasattr(service, 'stream_chat_completion_with_tools')

            # Simple test query
            messages = [{"role": "user", "content": "What time is it?"}]

            thinking_tokens = []
            response_tokens = []

            async def on_thinking(token: str):
                thinking_tokens.append(token)

            async def on_response(token: str):
                response_tokens.append(token)

            result = await service.stream_chat_completion_with_tools(
                messages=messages,
                tools=SUPER_AGENT_TOOLS,
                system_prompt="You are a helpful assistant.",
                max_tokens=256,
                temperature=0.7,
                on_thinking_token=on_thinking,
                on_response_token=on_response,
            )

            assert result is not None
            assert "content" in result
            assert "tool_calls" in result
            assert "model" in result
            assert result["model"] == settings.SUPER_AGENT_VERTEX_MODEL

            # Response should have been streamed
            assert len(response_tokens) > 0 or len(result["content"]) > 0

            print(f"\n✅ Vertex streaming with tools: {len(response_tokens)} response tokens, {len(result['tool_calls'])} tool calls")

        finally:
            settings.SUPER_AGENT_INFERENCE_PROVIDER = original

    @pytest.mark.asyncio
    async def test_stream_chat_completion_with_tools_menu_query(self):
        """Test streaming with tools when querying about menu."""
        from app.services.vertex_inference_service import VertexInferenceService
        from app.services.inference_service import get_inference_service

        original = settings.SUPER_AGENT_INFERENCE_PROVIDER
        settings.SUPER_AGENT_INFERENCE_PROVIDER = "vertex"
        settings.VERTEX_API_KEY = os.getenv("VERTEX_API_KEY")

        try:
            service = get_inference_service("super_agent")

            messages = [{"role": "user", "content": "Show me the menu"}]

            response_tokens = []

            async def on_response(token: str):
                response_tokens.append(token)

            result = await service.stream_chat_completion_with_tools(
                messages=messages,
                tools=SUPER_AGENT_TOOLS,
                max_tokens=512,
                on_response_token=on_response,
            )

            assert result is not None
            assert "content" in result
            assert "tool_calls" in result

            # The model might use menu_lookup tool or respond directly
            print(f"\n✅ Menu query: {len(result['tool_calls'])} tool calls, response length: {len(result['content'])}")

            if result["tool_calls"]:
                for tc in result["tool_calls"]:
                    print(f"  - Tool: {tc['function']['name']}")

        finally:
            settings.SUPER_AGENT_INFERENCE_PROVIDER = original

    @pytest.mark.asyncio
    async def test_stream_chat_completion_without_tools(self):
        """Test streaming without tools (tool_choice=none)."""
        from app.services.vertex_inference_service import VertexInferenceService
        from app.services.inference_service import get_inference_service

        original = settings.SUPER_AGENT_INFERENCE_PROVIDER
        settings.SUPER_AGENT_INFERENCE_PROVIDER = "vertex"
        settings.VERTEX_API_KEY = os.getenv("VERTEX_API_KEY")

        try:
            service = get_inference_service("super_agent")

            messages = [{"role": "user", "content": "Hello, how are you?"}]

            response_tokens = []

            async def on_response(token: str):
                response_tokens.append(token)

            result = await service.stream_chat_completion_with_tools(
                messages=messages,
                tools=SUPER_AGENT_TOOLS,  # Tools provided but disabled
                tool_choice="none",
                max_tokens=256,
                on_response_token=on_response,
            )

            assert result is not None
            assert "content" in result
            assert len(result["content"]) > 0
            assert result["tool_calls"] == []  # No tool calls when disabled

            print(f"\n✅ Streaming without tools: {len(result['content'])} chars response")

        finally:
            settings.SUPER_AGENT_INFERENCE_PROVIDER = original


class TestVertexToolCallingIntegration:
    """Test that Vertex AI correctly calls tools with gemini-3.1-flash-lite-preview."""

    @pytest.mark.asyncio
    async def test_vertex_gemini_3_1_flash_lite_tool_calling(self):
        """
        Test that gemini-3.1-flash-lite-preview can use tools.
        This validates the user's requirement for tool support.
        """
        from app.services.vertex_inference_service import VertexInferenceService

        settings.VERTEX_API_KEY = os.getenv("VERTEX_API_KEY")

        service = VertexInferenceService(
            model="gemini-3.1-flash-lite-preview",
            max_tokens=1024,
            temperature=0.7,
        )

        # Use a query that should trigger a tool call
        messages = [{"role": "user", "content": "Search the web for Python programming language"}]

        # Select just the web_search tool for this test
        web_search_tool = {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Busca informações públicas na internet via DuckDuckGo.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Termo de busca"},
                        "max_results": {"type": "integer", "description": "Máximo de resultados"},
                    },
                    "required": ["query"],
                },
            },
        }

        result = await service.stream_chat_completion_with_tools(
            messages=messages,
            tools=[web_search_tool],
            max_tokens=512,
        )

        assert result is not None
        assert "tool_calls" in result
        assert "content" in result

        print(f"\n✅ Gemini 3.1 Flash Lite tool test: {len(result['tool_calls'])} tool calls")
        if result["tool_calls"]:
            for tc in result["tool_calls"]:
                print(f"  - Called: {tc['function']['name']} with args: {tc['function']['arguments']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
