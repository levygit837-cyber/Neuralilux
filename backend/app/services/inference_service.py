"""
Inference Service - Integration with LM Studio for AI model inference.
Provides chat completion and response generation capabilities.
"""

import httpx
import json
import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import structlog

from app.core.config import settings

logger = structlog.get_logger()


@dataclass
class ChatMessage:
    """Chat message structure."""
    role: str  # "system", "user", "assistant"
    content: str


class InferenceServiceError(Exception):
    """Custom exception for inference service errors."""
    pass


class InferenceTimeoutError(InferenceServiceError):
    """Raised when inference request times out."""
    pass


class InferenceRateLimitError(InferenceServiceError):
    """Raised when rate limit is exceeded."""
    pass


class InferenceService:
    """
    Service for AI inference using LM Studio (OpenAI-compatible API).
    
    LM Studio exposes a local server that follows the OpenAI API format,
    allowing us to use standard chat completion requests.
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:1234",
        model: str = "local-model",
        max_tokens: int = 1024,
        temperature: float = 0.7,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        """
        Initialize the inference service.
        
        Args:
            base_url: LM Studio server URL
            model: Model identifier
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-2)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts on failure
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Rate limiting state
        self._request_count = 0
        self._rate_limit_window_start = 0
        self._rate_limit_per_minute = 60
        
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    def _build_messages(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Build message list with optional system prompt.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt to prepend
            
        Returns:
            Formatted messages list
        """
        formatted = []
        
        if system_prompt:
            formatted.append({
                "role": "system",
                "content": system_prompt
            })
        
        formatted.extend(messages)
        return formatted

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Send chat completion request to LM Studio.
        
        Args:
            messages: List of message dicts
            system_prompt: Optional system prompt
            max_tokens: Override max tokens
            temperature: Override temperature
            
        Returns:
            Dict with response content and metadata
            
        Raises:
            InferenceServiceError: On API errors
            InferenceTimeoutError: On timeout
            InferenceRateLimitError: On rate limit
        """
        url = f"{self.base_url}/v1/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": False,
        }
        
        logger.info(
            "Sending chat completion request",
            url=url,
            message_count=len(payload["messages"]),
            max_tokens=payload["max_tokens"],
        )
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        url,
                        headers=self._get_headers(),
                        json=payload,
                    )
                    
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 5))
                        logger.warning("Rate limited, waiting", retry_after=retry_after)
                        await asyncio.sleep(retry_after)
                        continue
                    
                    if response.status_code != 200:
                        error_detail = response.text
                        logger.error(
                            "LM Studio API error",
                            status_code=response.status_code,
                            error=error_detail,
                        )
                        raise InferenceServiceError(
                            f"API returned status {response.status_code}: {error_detail}"
                        )
                    
                    data = response.json()
                    
                    # Extract response content
                    content = ""
                    if data.get("choices") and len(data["choices"]) > 0:
                        message = data["choices"][0].get("message", {})
                        content = message.get("content", "")
                    
                    return {
                        "content": content,
                        "model": data.get("model", self.model),
                        "usage": data.get("usage", {}),
                        "finish_reason": data.get("choices", [{}])[0].get("finish_reason"),
                    }
                    
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    "Request timeout",
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                    
            except httpx.RequestError as e:
                last_error = e
                logger.error("Request error", error=str(e))
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
                    continue
        
        # All retries exhausted
        if isinstance(last_error, httpx.TimeoutException):
            raise InferenceTimeoutError(f"Request timed out after {self.timeout}s")
        
        raise InferenceServiceError(f"Request failed: {str(last_error)}")
    
    async def generate_response(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Generate a response for a user message.
        
        Args:
            user_message: The user's message
            conversation_history: Optional previous conversation messages
            system_prompt: Optional system prompt
            
        Returns:
            Generated response text
            
        Raises:
            InferenceServiceError: On API errors
            InferenceTimeoutError: On timeout
        """
        messages = []
        
        if conversation_history:
            messages.extend(conversation_history)
        
        messages.append({
            "role": "user",
            "content": user_message,
        })
        
        result = await self.chat_completion(
            messages=messages,
            system_prompt=system_prompt,
        )
        
        return result.get("content", "")
    
    async def health_check(self) -> bool:
        """
        Check if LM Studio is available and responding.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            url = f"{self.base_url}/v1/models"
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return False


# Singleton instance
inference_service = InferenceService()
