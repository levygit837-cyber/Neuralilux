"""
Tests for FallbackInferenceService - Vertex AI (primary) to Gemini (secondary).

Tests the new dynamic fallback implementation with retry logic.
"""
import pytest
import os
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

# Skip tests if neither API key is set
pytestmark = pytest.mark.skipif(
    not os.getenv("VERTEX_API_KEY") and not os.getenv("GEMINI_API_KEY"),
    reason="Neither VERTEX_API_KEY nor GEMINI_API_KEY set - skipping fallback tests",
)

from app.services.inference_service import (
    FallbackInferenceService,
    get_inference_service_with_fallback,
    InferenceServiceError,
)


class TestFallbackInferenceBasic:
    """Basic tests for FallbackInferenceService."""

    @pytest.mark.asyncio
    async def test_fallback_service_initialization(self):
        """Test that FallbackInferenceService initializes correctly."""
        service = FallbackInferenceService(agent_type="whatsapp_agent")
        
        assert service.agent_type == "whatsapp_agent"
        assert service.primary_service is not None
        assert service.secondary_service is not None
        assert service.max_retries == 3

    @pytest.mark.asyncio
    async def test_fallback_service_super_agent(self):
        """Test FallbackInferenceService for super_agent."""
        service = FallbackInferenceService(agent_type="super_agent")
        
        assert service.agent_type == "super_agent"
        assert service.primary_service is not None
        assert service.secondary_service is not None

    @pytest.mark.asyncio
    async def test_fallback_service_default(self):
        """Test FallbackInferenceService for default agent."""
        service = FallbackInferenceService(agent_type="default")
        
        assert service.agent_type == "default"
        assert service.primary_service is not None
        assert service.secondary_service is not None


class TestFallbackInferenceWithVertex:
    """Test inference with Vertex AI as primary provider."""

    @pytest.mark.skipif(
        not os.getenv("VERTEX_API_KEY"),
        reason="VERTEX_API_KEY not set - skipping Vertex tests",
    )
    @pytest.mark.asyncio
    async def test_chat_completion_vertex_primary(self):
        """Test chat completion using Vertex AI as primary."""
        service = FallbackInferenceService(agent_type="whatsapp_agent")
        
        messages = [{"role": "user", "content": "What is 2 + 2?"}]
        
        result = await service.chat_completion(messages)
        
        assert isinstance(result, dict)
        assert "content" in result
        assert len(result["content"]) > 0
        print(f"\n✅ Vertex AI primary response: {result['content'][:100]}...")

    @pytest.mark.skipif(
        not os.getenv("VERTEX_API_KEY"),
        reason="VERTEX_API_KEY not set - skipping Vertex tests",
    )
    @pytest.mark.asyncio
    async def test_chat_completion_with_system_prompt(self):
        """Test chat completion with system prompt."""
        service = FallbackInferenceService(agent_type="whatsapp_agent")
        
        messages = [{"role": "user", "content": "Hello!"}]
        system_prompt = "You are a helpful assistant."
        
        result = await service.chat_completion(messages, system_prompt=system_prompt)
        
        assert isinstance(result, dict)
        assert "content" in result
        assert len(result["content"]) > 0
        print(f"\n✅ Vertex AI with system prompt: {result['content'][:100]}...")

    @pytest.mark.skipif(
        not os.getenv("VERTEX_API_KEY"),
        reason="VERTEX_API_KEY not set - skipping Vertex tests",
    )
    @pytest.mark.asyncio
    async def test_get_inference_service_with_fallback_wrapper(self):
        """Test the wrapper function get_inference_service_with_fallback."""
        service = get_inference_service_with_fallback("whatsapp_agent")
        
        assert isinstance(service, FallbackInferenceService)
        assert service.agent_type == "whatsapp_agent"
        
        messages = [{"role": "user", "content": "Say 'test'"}]
        result = await service.chat_completion(messages)
        
        assert isinstance(result, dict)
        assert "content" in result
        print(f"\n✅ Wrapper function works: {result['content'][:100]}...")


class TestFallbackInferenceWithTools:
    """Test tool calling with fallback."""

    @pytest.mark.skipif(
        not os.getenv("VERTEX_API_KEY"),
        reason="VERTEX_API_KEY not set - skipping Vertex tests",
    )
    @pytest.mark.asyncio
    async def test_chat_completion_with_tools_vertex(self):
        """Test tool calling with Vertex AI."""
        service = FallbackInferenceService(agent_type="whatsapp_agent")
        
        tools = [
            {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                    },
                    "required": ["location"],
                },
            }
        ]
        
        messages = [{"role": "user", "content": "What's the weather in Tokyo?"}]
        
        result = await service.chat_completion_with_tools(messages, tools)
        
        assert isinstance(result, dict)
        assert "content" in result
        assert "tool_calls" in result
        print(f"\n✅ Vertex AI tool calling: {result.get('tool_calls', [])}")


class TestFallbackRetryLogic:
    """Test retry logic within fallback service."""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test that retries happen on primary provider failure."""
        service = FallbackInferenceService(agent_type="whatsapp_agent")
        
        # Mock primary service to fail twice then succeed
        original_call = service.primary_service.chat_completion
        call_count = [0]
        
        async def mock_chat_completion(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Simulated failure")
            return await original_call(*args, **kwargs)
        
        # Only run this test if we have a working primary service
        if os.getenv("VERTEX_API_KEY"):
            service.primary_service.chat_completion = mock_chat_completion
            
            messages = [{"role": "user", "content": "Test"}]
            result = await service.chat_completion(messages)
            
            assert call_count[0] == 3  # Should have retried 3 times
            assert isinstance(result, dict)
            print(f"\n✅ Retry logic works: {call_count[0]} attempts")


class TestFallbackToGemini:
    """Test fallback to Gemini when Vertex fails."""

    @pytest.mark.skipif(
        not os.getenv("GEMINI_API_KEY"),
        reason="GEMINI_API_KEY not set - skipping Gemini fallback tests",
    )
    @pytest.mark.asyncio
    async def test_fallback_to_gemini_on_vertex_failure(self):
        """Test that Gemini is used when Vertex fails."""
        service = FallbackInferenceService(agent_type="whatsapp_agent")
        
        # Mock primary service to always fail
        async def mock_vertex_failure(*args, **kwargs):
            raise Exception("Vertex AI unavailable")
        
        service.primary_service.chat_completion = mock_vertex_failure
        
        messages = [{"role": "user", "content": "What is 2 + 2?"}]
        
        result = await service.chat_completion(messages)
        
        assert isinstance(result, dict)
        assert "content" in result
        assert len(result["content"]) > 0
        print(f"\n✅ Fallback to Gemini works: {result['content'][:100]}...")


class TestFallbackErrorHandling:
    """Test error handling when both providers fail."""

    @pytest.mark.asyncio
    async def test_both_providers_fail(self):
        """Test that error is raised when both providers fail."""
        service = FallbackInferenceService(agent_type="whatsapp_agent")
        
        # Mock both services to fail
        async def mock_failure(*args, **kwargs):
            raise Exception("Provider unavailable")
        
        service.primary_service.chat_completion = mock_failure
        service.secondary_service.chat_completion = mock_failure
        
        messages = [{"role": "user", "content": "Test"}]
        
        with pytest.raises(InferenceServiceError) as exc_info:
            await service.chat_completion(messages)
        
        assert "All providers failed" in str(exc_info.value)
        print("\n✅ Error handling works: proper exception raised")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
