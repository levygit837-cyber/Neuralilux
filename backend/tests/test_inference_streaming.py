"""
Unit tests for async streaming inference with thinking support.
Tests the astream_chat_completion_with_thinking() method.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
import json
from typing import List, Dict, Any, Tuple, AsyncGenerator

from app.services.inference_service import (
    InferenceService,
    InferenceServiceError,
    InferenceTimeoutError,
)


# =====================================================================
# HELPERS
# =====================================================================

async def async_collect(generator: AsyncGenerator) -> List[Tuple[str, str]]:
    """Collect all items from async generator into a list."""
    results = []
    async for item in generator:
        results.append(item)
    return results


class MockAsyncIterator:
    """Mock async iterator for httpx streaming response."""
    def __init__(self, chunks: List[bytes]):
        self.chunks = chunks
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.chunks):
            raise StopAsyncIteration
        chunk = self.chunks[self.index]
        self.index += 1
        return chunk


# =====================================================================
# TESTS: STREAM CONFIGURATION
# =====================================================================

class TestStreamConfiguration:
    """Test that streaming is properly configured."""

    @pytest.mark.asyncio
    async def test_stream_uses_stream_true_in_payload(self):
        """Test that astream method sends stream=True in payload - VAL-BE-001."""
        service = InferenceService()
        
        captured_payload = {}
        
        # Create a proper async mock that works with context managers
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_text = MagicMock(return_value=MockAsyncIterator([b"data: [DONE]\n\n"]))
        
        # Mock the async context manager protocol for the response
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        # Create a stream method that returns the response (which is an async context manager)
        def mock_stream(*args, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return mock_response
        
        # Create async client mock with stream method
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = mock_stream
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            gen = service.astream_chat_completion_with_thinking([{"role": "user", "content": "hi"}])
            try:
                await anext(gen)
            except StopAsyncIteration:
                pass
        
        # The streaming endpoint is POST to /v1/chat/completions with stream=True
        assert captured_payload.get("stream") is True, f"Payload must have stream=True, got: {captured_payload}"


# =====================================================================
# TESTS: THINK TAG DETECTION
# =====================================================================

class TestThinkTagDetection:
    """Test detection of <think> blocks."""

    @pytest.mark.asyncio
    async def test_normal_think_block(self):
        """Test normal <think> block detection - VAL-BE-003."""
        service = InferenceService()
        
        # Simulate chunks: <think>reasoning</think>response
        chunks = [
            b'data: {"choices":[{"delta":{"content":"<think>"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"Let me think"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"</think>"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"Final answer"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]
        
        mock_response = MagicMock()
        mock_response.aiter_text = MagicMock(return_value=MockAsyncIterator(chunks))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_response.status_code = 200
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = lambda *args, **kwargs: mock_response
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await async_collect(
                service.astream_chat_completion_with_thinking([{"role": "user", "content": "test"}])
            )
        
        # Content inside <think> should be thinking tokens
        thinking_tokens = [r for r in results if r[0] == "thinking"]
        response_tokens = [r for r in results if r[0] == "response"]
        
        assert len(thinking_tokens) > 0, f"Should have thinking tokens, got: {results}"
        assert len(response_tokens) > 0, f"Should have response tokens after </think>, got: {results}"

    @pytest.mark.asyncio
    async def test_response_after_think(self):
        """Test that content after </think> is collected as response - VAL-BE-004/VAL-BE-005."""
        service = InferenceService()
        
        chunks = [
            b'data: {"choices":[{"delta":{"content":"<think>"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"A"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"</think>"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"B"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]
        
        mock_response = MagicMock()
        mock_response.aiter_text = MagicMock(return_value=MockAsyncIterator(chunks))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = lambda *args, **kwargs: mock_response
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await async_collect(
                service.astream_chat_completion_with_thinking([{"role": "user", "content": "test"}])
            )
        
        # Find the transition point
        thinking_contents = "".join(r[1] for r in results if r[0] == "thinking")
        response_contents = "".join(r[1] for r in results if r[0] == "response")
        
        assert "B" in response_contents, f"Content after </think> should be in response: {response_contents}"
        assert "B" not in thinking_contents, f"Content after </think> should not be in thinking: {thinking_contents}"

    @pytest.mark.asyncio
    async def test_split_open_tag(self):
        """Test <think> tag split across chunks - VAL-BE-007."""
        service = InferenceService()
        
        # Tag split: "<thi" in chunk1, "nk>" in chunk2
        chunks = [
            b'data: {"choices":[{"delta":{"content":"<thi"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"nk>reasoning"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"</think>"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"answer"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]
        
        mock_response = MagicMock()
        mock_response.aiter_text = MagicMock(return_value=MockAsyncIterator(chunks))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = lambda *args, **kwargs: mock_response
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await async_collect(
                service.astream_chat_completion_with_thinking([{"role": "user", "content": "test"}])
            )
        
        response_contents = "".join(r[1] for r in results if r[0] == "response")
        thinking_contents = "".join(r[1] for r in results if r[0] == "thinking")
        
        # The complete tag should be recognized, not leaked into response
        assert "<thi" not in response_contents, f"Partial open tag should not leak to response: {response_contents}"
        assert "nk>" not in response_contents, f"Rest of tag should not leak to response: {response_contents}"
        assert "answer" in response_contents, f"Content after </think> should be in response: {response_contents}"
        assert "reasoning" in thinking_contents, f"Thinking content should be present: {thinking_contents}"

    @pytest.mark.asyncio
    async def test_split_close_tag(self):
        """Test </think> tag split across chunks - VAL-BE-007."""
        service = InferenceService()
        
        # Tag split: "</thi" in chunk1, "nk>" in chunk2
        chunks = [
            b'data: {"choices":[{"delta":{"content":"<think>"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"done"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"</thi"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"nk>response"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]
        
        mock_response = MagicMock()
        mock_response.aiter_text = MagicMock(return_value=MockAsyncIterator(chunks))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = lambda *args, **kwargs: mock_response
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await async_collect(
                service.astream_chat_completion_with_thinking([{"role": "user", "content": "test"}])
            )
        
        thinking_contents = "".join(r[1] for r in results if r[0] == "thinking")
        response_contents = "".join(r[1] for r in results if r[0] == "response")
        
        # Close tag parts should not appear in either stream
        assert "</thi" not in response_contents, f"Partial close tag should not leak to response: {response_contents}"
        assert "nk>" not in response_contents, f"Rest of close tag should not leak to response: {response_contents}"
        assert "response" in response_contents, f"Content after </think> should be in response: {response_contents}"
        assert "done" in thinking_contents, f"Thinking content should be present: {thinking_contents}"


# =====================================================================
# TESTS: NO THINK / REASONING CLASSIFICATION
# =====================================================================

class TestThinkingClassification:
    """Test behavior when the model streams plain content or explicit reasoning deltas."""

    @pytest.mark.asyncio
    async def test_no_think_block_defaults_to_response(self):
        """Plain streamed content without reasoning markers must remain response content."""
        service = InferenceService()
        
        chunks = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":" world"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"!"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]
        
        mock_response = MagicMock()
        mock_response.aiter_text = MagicMock(return_value=MockAsyncIterator(chunks))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = lambda *args, **kwargs: mock_response
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await async_collect(
                service.astream_chat_completion_with_thinking([{"role": "user", "content": "test"}])
            )
        
        assert all(r[0] == "response" for r in results), f"Plain content should stay in response: {results}"

        full_content = "".join(r[1] for r in results if r[0] == "response")
        assert "Hello world!" in full_content, f"Full content should be accumulated: {full_content}"

    @pytest.mark.asyncio
    async def test_reasoning_delta_streamed_as_thinking(self):
        """Reasoning-specific deltas must be emitted as thinking in real time."""
        service = InferenceService()

        chunks = [
            b'data: {"choices":[{"delta":{"reasoning":"Need to inspect"}}]}\n\n',
            b'data: {"choices":[{"delta":{"reasoning":" the latest state"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"Final answer"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]

        mock_response = MagicMock()
        mock_response.aiter_text = MagicMock(return_value=MockAsyncIterator(chunks))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_response.status_code = 200

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = lambda *args, **kwargs: mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await async_collect(
                service.astream_chat_completion_with_thinking([{"role": "user", "content": "test"}])
            )

        thinking_content = "".join(r[1] for r in results if r[0] == "thinking")
        response_content = "".join(r[1] for r in results if r[0] == "response")

        assert thinking_content == "Need to inspect the latest state"
        assert response_content == "Final answer"

    @pytest.mark.asyncio
    async def test_reasoning_content_delta_streamed_as_thinking(self):
        """Backward-compatible reasoning_content deltas must also be emitted as thinking."""
        service = InferenceService()

        chunks = [
            b'data: {"choices":[{"delta":{"reasoning_content":"Plan"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"Done"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]

        mock_response = MagicMock()
        mock_response.aiter_text = MagicMock(return_value=MockAsyncIterator(chunks))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_response.status_code = 200

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = lambda *args, **kwargs: mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await async_collect(
                service.astream_chat_completion_with_thinking([{"role": "user", "content": "test"}])
            )

        thinking_content = "".join(r[1] for r in results if r[0] == "thinking")
        response_content = "".join(r[1] for r in results if r[0] == "response")

        assert thinking_content == "Plan"
        assert response_content == "Done"


# =====================================================================
# TESTS: SSE PARSING
# =====================================================================

class TestSSEParsing:
    """Test SSE chunk parsing - VAL-BE-002."""

    @pytest.mark.asyncio
    async def test_done_sentinel_terminates(self):
        """Test that data: [DONE] terminates the generator."""
        service = InferenceService()
        
        chunks = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n',
            b'data: [DONE]\n\n',
            b'data: {"choices":[{"delta":{"content":"Should not see this"}}]}\n\n',
        ]
        
        mock_response = MagicMock()
        mock_response.aiter_text = MagicMock(return_value=MockAsyncIterator(chunks))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = lambda *args, **kwargs: mock_response
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await async_collect(
                service.astream_chat_completion_with_thinking([{"role": "user", "content": "test"}])
            )
        
        full_content = "".join(r[1] for r in results)
        assert "Hello" in full_content, f"Hello should be in content: {full_content}"
        assert "Should not see this" not in full_content, f"Content after [DONE] should not appear: {full_content}"

    @pytest.mark.asyncio
    async def test_empty_lines_ignored(self):
        """Test that empty lines are ignored."""
        service = InferenceService()
        
        chunks = [
            b'data: {"choices":[{"delta":{"content":"A"}}]}\n\n',
            b'\n',  # Empty line
            b'\n',  # Another empty line
            b'data: {"choices":[{"delta":{"content":"B"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]
        
        mock_response = MagicMock()
        mock_response.aiter_text = MagicMock(return_value=MockAsyncIterator(chunks))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = lambda *args, **kwargs: mock_response
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await async_collect(
                service.astream_chat_completion_with_thinking([{"role": "user", "content": "test"}])
            )
        
        full_content = "".join(r[1] for r in results)
        assert "A" in full_content, f"A should be in content: {full_content}"
        assert "B" in full_content, f"B should be in content: {full_content}"

    @pytest.mark.asyncio
    async def test_malformed_chunks_graceful(self):
        """Test handling of malformed JSON chunks."""
        service = InferenceService()
        
        chunks = [
            b'data: {"choices":[{"delta":{"content":"Good"}}]}\n\n',
            b'data: {invalid json\n\n',  # Malformed
            b'data: {"choices":[{"delta":{"content":"Data"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]
        
        mock_response = MagicMock()
        mock_response.aiter_text = MagicMock(return_value=MockAsyncIterator(chunks))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = lambda *args, **kwargs: mock_response
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await async_collect(
                service.astream_chat_completion_with_thinking([{"role": "user", "content": "test"}])
            )
        
        # Should not crash, should still get valid data
        full_content = "".join(r[1] for r in results)
        assert "Good" in full_content, f"Good should be in content: {full_content}"
        assert "Data" in full_content, f"Data should be in content: {full_content}"

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        """Test handling of empty stream."""
        service = InferenceService()
        
        chunks = [
            b'data: [DONE]\n\n',
        ]
        
        mock_response = MagicMock()
        mock_response.aiter_text = MagicMock(return_value=MockAsyncIterator(chunks))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = lambda *args, **kwargs: mock_response
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            results = await async_collect(
                service.astream_chat_completion_with_thinking([{"role": "user", "content": "test"}])
            )
        
        assert len(results) == 0, f"Empty stream should yield no results: {results}"


# =====================================================================
# TESTS: ERROR HANDLING
# =====================================================================

class TestStreamingErrorHandling:
    """Test error handling during streaming - VAL-BE-010."""

    @pytest.mark.asyncio
    async def test_timeout_exception_re_raised(self):
        """Test that httpx.TimeoutException is caught and re-raised as InferenceError."""
        service = InferenceService(timeout=0.1)
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = MagicMock(side_effect=httpx.TimeoutException("Connection timeout"))
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises((InferenceServiceError, InferenceTimeoutError)):
                await async_collect(
                    service.astream_chat_completion_with_thinking([{"role": "user", "content": "test"}])
                )

    @pytest.mark.asyncio
    async def test_connection_error_re_raised(self):
        """Test that httpx connection errors are caught and re-raised."""
        service = InferenceService()
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = MagicMock(side_effect=httpx.ConnectError("Connection failed"))
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(InferenceServiceError):
                await async_collect(
                    service.astream_chat_completion_with_thinking([{"role": "user", "content": "test"}])
                )

    @pytest.mark.asyncio
    async def test_http_error_status(self):
        """Test handling of HTTP error status in streaming response."""
        service = InferenceService()
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.aread = AsyncMock(return_value=b"Internal Server Error")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = lambda *args, **kwargs: mock_response
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(InferenceServiceError):
                await async_collect(
                    service.astream_chat_completion_with_thinking([{"role": "user", "content": "test"}])
                )
