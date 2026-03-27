"""
Tests for inference endpoints (/v1/messages/inference).
Mocks LM Studio API responses using respx and httpx.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status
import httpx


# =====================================================================
# FIXTURES
# =====================================================================

@pytest.fixture
def mock_lm_studio_response():
    """Mock successful LM Studio chat completion response."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "local-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Olá! Eu sou um assistente de IA. Como posso ajudá-lo hoje?"
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 25,
            "completion_tokens": 18,
            "total_tokens": 43
        }
    }


@pytest.fixture
def mock_lm_studio_models_response():
    """Mock LM Studio models list response."""
    return {
        "object": "list",
        "data": [
            {
                "id": "local-model",
                "object": "model",
                "created": 1677652288,
                "owned_by": "local"
            }
        ]
    }


# =====================================================================
# TESTS: REQUEST/RESPONSE FORMAT
# =====================================================================

class TestInferenceRequestResponseFormat:
    """Test request and response format validation."""

    def test_inference_request_valid_format(self, client, auth_headers):
        """Test that valid request format is accepted."""
        with patch("app.services.inference_service.inference_service.chat_completion") as mock:
            mock.return_value = {
                "content": "Test response",
                "model": "local-model",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "finish_reason": "stop"
            }
            
            response = client.post(
                "/api/v1/messages/inference",
                headers=auth_headers,
                json={
                    "messages": [
                        {"role": "user", "content": "Hello"}
                    ]
                }
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "content" in data
            assert "model" in data
            assert "usage" in data
            assert "finish_reason" in data

    def test_inference_request_with_all_parameters(self, client, auth_headers):
        """Test request with all optional parameters."""
        with patch("app.services.inference_service.inference_service.chat_completion") as mock:
            mock.return_value = {
                "content": "Detailed response",
                "model": "local-model",
                "usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
                "finish_reason": "stop"
            }
            
            response = client.post(
                "/api/v1/messages/inference",
                headers=auth_headers,
                json={
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Tell me a joke."}
                    ],
                    "system_prompt": "Be concise.",
                    "max_tokens": 256,
                    "temperature": 0.5
                }
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["content"] == "Detailed response"
            assert data["model"] == "local-model"

    def test_inference_request_missing_messages(self, client, auth_headers):
        """Test that missing messages field returns 422."""
        response = client.post(
            "/api/v1/messages/inference",
            headers=auth_headers,
            json={}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_inference_request_empty_messages(self, client, auth_headers):
        """Test that empty messages list returns 422."""
        response = client.post(
            "/api/v1/messages/inference",
            headers=auth_headers,
            json={"messages": []}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_inference_request_invalid_message_format(self, client, auth_headers):
        """Test that invalid message format returns 422."""
        response = client.post(
            "/api/v1/messages/inference",
            headers=auth_headers,
            json={
                "messages": [
                    {"content": "Missing role field"}
                ]
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_inference_request_invalid_temperature(self, client, auth_headers):
        """Test that invalid temperature returns 422."""
        response = client.post(
            "/api/v1/messages/inference",
            headers=auth_headers,
            json={
                "messages": [{"role": "user", "content": "Test"}],
                "temperature": 3.0  # Max is 2.0
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_inference_request_invalid_max_tokens(self, client, auth_headers):
        """Test that invalid max_tokens returns 422."""
        response = client.post(
            "/api/v1/messages/inference",
            headers=auth_headers,
            json={
                "messages": [{"role": "user", "content": "Test"}],
                "max_tokens": -1
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =====================================================================
# TESTS: AUTHENTICATION
# =====================================================================

class TestInferenceAuthentication:
    """Test authentication requirements."""

    def test_inference_requires_auth(self, client):
        """Test that inference endpoint requires authentication."""
        response = client.post(
            "/api/v1/messages/inference",
            json={
                "messages": [{"role": "user", "content": "Test"}]
            }
        )
        
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ]


# =====================================================================
# TESTS: ERROR HANDLING
# =====================================================================

class TestInferenceErrorHandling:
    """Test error handling scenarios."""

    def test_inference_service_error(self, client, auth_headers):
        """Test handling of inference service errors."""
        from app.services.inference_service import InferenceServiceError
        
        with patch("app.services.inference_service.inference_service.chat_completion") as mock:
            mock.side_effect = InferenceServiceError("LM Studio connection failed")
            
            response = client.post(
                "/api/v1/messages/inference",
                headers=auth_headers,
                json={
                    "messages": [{"role": "user", "content": "Test"}]
                }
            )
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "error" in response.json()["detail"].lower() or "internal" in response.json()["detail"].lower()

    def test_inference_timeout_error(self, client, auth_headers):
        """Test handling of timeout errors."""
        from app.services.inference_service import InferenceTimeoutError
        
        with patch("app.services.inference_service.inference_service.chat_completion") as mock:
            mock.side_effect = InferenceTimeoutError("Request timed out after 60s")
            
            response = client.post(
                "/api/v1/messages/inference",
                headers=auth_headers,
                json={
                    "messages": [{"role": "user", "content": "Test"}]
                }
            )
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_inference_unexpected_exception(self, client, auth_headers):
        """Test handling of unexpected exceptions."""
        with patch("app.services.inference_service.inference_service.chat_completion") as mock:
            mock.side_effect = Exception("Unexpected error")
            
            response = client.post(
                "/api/v1/messages/inference",
                headers=auth_headers,
                json={
                    "messages": [{"role": "user", "content": "Test"}]
                }
            )
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_inference_returns_empty_choices(self, client, auth_headers):
        """Test handling when LM Studio returns empty choices."""
        with patch("app.services.inference_service.inference_service.chat_completion") as mock:
            mock.return_value = {
                "content": "",
                "model": "local-model",
                "usage": {},
                "finish_reason": None
            }
            
            response = client.post(
                "/api/v1/messages/inference",
                headers=auth_headers,
                json={
                    "messages": [{"role": "user", "content": "Test"}]
                }
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["content"] == ""


# =====================================================================
# TESTS: TIMEOUT HANDLING
# =====================================================================

class TestInferenceTimeout:
    """Test timeout handling in inference service."""

    @pytest.mark.asyncio
    async def test_chat_completion_timeout(self):
        """Test that chat_completion raises InferenceTimeoutError on timeout."""
        from app.services.inference_service import (
            InferenceService, InferenceTimeoutError
        )
        
        service = InferenceService(timeout=0.1, max_retries=1)
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Connection timeout")
            
            with pytest.raises(InferenceTimeoutError):
                await service.chat_completion(
                    messages=[{"role": "user", "content": "Test"}]
                )

    @pytest.mark.asyncio
    async def test_chat_completion_retries_on_timeout(self):
        """Test that service retries on timeout."""
        from app.services.inference_service import (
            InferenceService, InferenceTimeoutError
        )
        
        service = InferenceService(timeout=0.1, max_retries=3)
        
        call_count = 0
        
        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("Connection timeout")
        
        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            with pytest.raises(InferenceTimeoutError):
                await service.chat_completion(
                    messages=[{"role": "user", "content": "Test"}]
                )
        
        assert call_count == 3  # Should have retried 3 times


# =====================================================================
# TESTS: RATE LIMITING
# =====================================================================

class TestInferenceRateLimiting:
    """Test rate limiting handling."""

    @pytest.mark.asyncio
    async def test_rate_limit_429_handling(self):
        """Test that 429 responses are handled with retry."""
        from app.services.inference_service import InferenceService
        
        service = InferenceService(max_retries=2)
        
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "1"}
        
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {
            "model": "local-model",
            "choices": [{"message": {"content": "Success"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
        }
        
        call_count = 0
        
        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_response_429
            return mock_response_200
        
        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await service.chat_completion(
                    messages=[{"role": "user", "content": "Test"}]
                )
        
        assert result["content"] == "Success"
        assert call_count == 2


# =====================================================================
# TESTS: HEALTH CHECK
# =====================================================================

class TestInferenceHealthCheck:
    """Test health check endpoint."""

    def test_health_check_healthy(self, client):
        """Test health check when LM Studio is available."""
        with patch("app.services.inference_service.inference_service.health_check") as mock:
            mock.return_value = True
            
            with patch("app.services.inference_service.inference_service.base_url", "http://localhost:1234"):
                with patch("app.services.inference_service.inference_service.model", "local-model"):
                    with patch("app.services.inference_service.inference_service.max_tokens", 1024):
                        with patch("app.services.inference_service.inference_service.temperature", 0.7):
                            response = client.get("/api/v1/messages/inference/health")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert "url" in data
            assert "model" in data

    def test_health_check_unhealthy(self, client):
        """Test health check when LM Studio is unavailable."""
        with patch("app.services.inference_service.inference_service.health_check") as mock:
            mock.return_value = False
            
            with patch("app.services.inference_service.inference_service.base_url", "http://localhost:1234"):
                with patch("app.services.inference_service.inference_service.model", "local-model"):
                    with patch("app.services.inference_service.inference_service.max_tokens", 1024):
                        with patch("app.services.inference_service.inference_service.temperature", 0.7):
                            response = client.get("/api/v1/messages/inference/health")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "unhealthy"

    def test_health_check_exception(self, client):
        """Test health check when exception occurs."""
        with patch("app.services.inference_service.inference_service.health_check") as mock:
            mock.side_effect = Exception("Connection refused")
            
            response = client.get("/api/v1/messages/inference/health")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "error" in data


# =====================================================================
# TESTS: CHAT INFERENCE ENDPOINT
# =====================================================================

class TestChatInferenceEndpoint:
    """Test /messages/inference/chat endpoint."""

    def test_chat_inference_success(self, client, auth_headers):
        """Test successful chat inference."""
        with patch("app.services.inference_service.inference_service.generate_response") as mock_gen:
            mock_gen.return_value = "Olá! Como posso ajudá-lo?"
            
            with patch("app.services.inference_service.inference_service.model", "local-model"):
                response = client.post(
                    "/api/v1/messages/inference/chat",
                    headers=auth_headers,
                    json={
                        "message": "Olá!"
                    }
                )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "response" in data
            assert "model" in data
            assert data["response"] == "Olá! Como posso ajudá-lo?"

    def test_chat_inference_with_history(self, client, auth_headers):
        """Test chat inference with conversation history."""
        with patch("app.services.inference_service.inference_service.generate_response") as mock_gen:
            mock_gen.return_value = "Baseado no histórico, aqui está minha resposta."
            
            with patch("app.services.inference_service.inference_service.model", "local-model"):
                response = client.post(
                    "/api/v1/messages/inference/chat",
                    headers=auth_headers,
                    json={
                        "message": "Continue a conversa",
                        "conversation_history": [
                            {"role": "user", "content": "Primeira pergunta"},
                            {"role": "assistant", "content": "Primeira resposta"}
                        ]
                    }
                )
            
            assert response.status_code == status.HTTP_200_OK
            assert "response" in response.json()

    def test_chat_inference_missing_message(self, client, auth_headers):
        """Test chat inference with missing message field."""
        response = client.post(
            "/api/v1/messages/inference/chat",
            headers=auth_headers,
            json={}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_chat_inference_empty_message(self, client, auth_headers):
        """Test chat inference with empty message."""
        response = client.post(
            "/api/v1/messages/inference/chat",
            headers=auth_headers,
            json={"message": ""}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_chat_inference_error(self, client, auth_headers):
        """Test chat inference error handling."""
        from app.services.inference_service import InferenceServiceError
        
        with patch("app.services.inference_service.inference_service.generate_response") as mock_gen:
            mock_gen.side_effect = InferenceServiceError("Generation failed")
            
            response = client.post(
                "/api/v1/messages/inference/chat",
                headers=auth_headers,
                json={"message": "Test"}
            )
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# =====================================================================
# TESTS: ENDPOINT FUNCTIONALITY
# =====================================================================

class TestInferenceEndpointFunctionality:
    """Test that endpoints are working correctly."""

    def test_inference_endpoint_exists(self, client, auth_headers):
        """Test that inference endpoint exists and responds."""
        with patch("app.services.inference_service.inference_service.chat_completion") as mock:
            mock.return_value = {
                "content": "Test",
                "model": "local-model",
                "usage": {},
                "finish_reason": "stop"
            }
            
            response = client.post(
                "/api/v1/messages/inference",
                headers=auth_headers,
                json={
                    "messages": [{"role": "user", "content": "Hello"}]
                }
            )
            
            assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_inference_chat_endpoint_exists(self, client, auth_headers):
        """Test that inference chat endpoint exists and responds."""
        with patch("app.services.inference_service.inference_service.generate_response") as mock:
            mock.return_value = "Response"
            
            with patch("app.services.inference_service.inference_service.model", "local-model"):
                response = client.post(
                    "/api/v1/messages/inference/chat",
                    headers=auth_headers,
                    json={"message": "Hello"}
                )
            
            assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_health_endpoint_exists(self, client):
        """Test that health check endpoint exists."""
        response = client.get("/api/v1/messages/inference/health")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_inference_passes_correct_parameters(self, client, auth_headers):
        """Test that endpoint passes correct parameters to service."""
        with patch("app.services.inference_service.inference_service.chat_completion") as mock:
            mock.return_value = {
                "content": "Test",
                "model": "local-model",
                "usage": {},
                "finish_reason": "stop"
            }
            
            client.post(
                "/api/v1/messages/inference",
                headers=auth_headers,
                json={
                    "messages": [{"role": "user", "content": "Hello"}],
                    "system_prompt": "Be helpful",
                    "max_tokens": 256,
                    "temperature": 0.8
                }
            )
            
            mock.assert_called_once()
            call_kwargs = mock.call_args
            # Check that parameters were passed correctly
            assert call_kwargs[1]["system_prompt"] == "Be helpful"
            assert call_kwargs[1]["max_tokens"] == 256
            assert call_kwargs[1]["temperature"] == 0.8
