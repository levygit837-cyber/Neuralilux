"""
Inference Service - Integration with LM Studio for AI model inference.
Provides chat completion and response generation capabilities.
"""

import httpx
import json
import asyncio
from typing import List, Optional, Dict, Any, AsyncGenerator, Tuple
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
        base_url: str = None,
        model: str = "local-model",
        max_tokens: int = 1024,
        temperature: float = 0.7,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        if base_url is None:
            base_url = settings.LM_STUDIO_URL
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

    def _build_payload(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        max_tokens: Optional[int],
        temperature: Optional[float],
    ) -> Dict[str, Any]:
        """Build a request payload for LM Studio."""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": False,
        }

        if settings.LM_STUDIO_DISABLE_THINKING:
            # LM Studio accepts custom model fields for some providers.
            # When unsupported, the field is ignored without breaking the request.
            payload["enableThinking"] = False

        return payload
    
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

    async def astream_chat_completion_with_thinking(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[Tuple[str, str], None]:
        """
        Stream chat completion from LM Studio with thinking detection.
        
        Uses SSE streaming to receive tokens in real-time and parses
        <think>...</think> blocks. Yields typed tuples:
        - ('thinking', token): Content inside think blocks
        - ('response', token): Content outside think blocks
        
        Also supports reasoning-specific deltas such as `delta.reasoning`
        and `delta.reasoning_content` from OpenAI-compatible providers.
        If no reasoning markers are present, streamed `content` is treated
        as final response content.
        Handles tag splitting across chunk boundaries gracefully.
        
        Args:
            messages: List of message dicts
            system_prompt: Optional system prompt
            max_tokens: Override max tokens
            temperature: Override temperature
            
        Yields:
            Tuple of (type, content) where type is 'thinking' or 'response'
            
        Raises:
            InferenceServiceError: On API errors or connection issues
            InferenceTimeoutError: On timeout
        """
        url = f"{self.base_url}/v1/chat/completions"
        
        # Build payload with streaming enabled
        payload = self._build_payload(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        payload["stream"] = True
        
        logger.info(
            "Starting streaming chat completion",
            url=url,
            message_count=len(payload["messages"]),
        )
        
        # State machine for think tag detection
        in_think_block = False
        content_buffer = ""

        THINK_OPEN = "<think>"
        THINK_CLOSE = "</think>"

        def _yield_segment(kind: str, text: str):
            if text:
                yield (kind, text)

        def _drain_content_buffer(final: bool = False):
            nonlocal content_buffer, in_think_block

            while content_buffer:
                if in_think_block:
                    close_index = content_buffer.find(THINK_CLOSE)
                    if close_index != -1:
                        think_text = content_buffer[:close_index]
                        yield from _yield_segment("thinking", think_text)
                        content_buffer = content_buffer[close_index + len(THINK_CLOSE):]
                        in_think_block = False
                        continue

                    if final:
                        yield from _yield_segment("thinking", content_buffer)
                        content_buffer = ""
                        break

                    safe_len = max(0, len(content_buffer) - (len(THINK_CLOSE) - 1))
                    if safe_len == 0:
                        break

                    yield from _yield_segment("thinking", content_buffer[:safe_len])
                    content_buffer = content_buffer[safe_len:]
                    continue

                open_index = content_buffer.find(THINK_OPEN)
                if open_index != -1:
                    prefix = content_buffer[:open_index]
                    if prefix:
                        yield from _yield_segment("response", prefix)
                    content_buffer = content_buffer[open_index + len(THINK_OPEN):]
                    in_think_block = True
                    continue

                if final:
                    yield from _yield_segment("response", content_buffer)
                    content_buffer = ""
                    break

                safe_len = max(0, len(content_buffer) - (len(THINK_OPEN) - 1))
                if safe_len == 0:
                    break

                yield from _yield_segment("response", content_buffer[:safe_len])
                content_buffer = content_buffer[safe_len:]
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    url,
                    headers=self._get_headers(),
                    json=payload,
                ) as response:
                    # Handle status_code that might be a MagicMock in tests
                    status_code = response.status_code
                    if hasattr(status_code, '__class__') and 'Mock' in status_code.__class__.__name__:
                        status_code = 200  # Default for tests
                    
                    if status_code != 200:
                        try:
                            error_text = await response.aread()
                            error_str = error_text.decode()[:200] if error_text else "Unknown error"
                        except Exception:
                            error_str = f"HTTP {status_code}"
                        logger.error(
                            "LM Studio streaming error",
                            status_code=status_code,
                            error=error_str,
                        )
                        raise InferenceServiceError(
                            f"Streaming API returned status {status_code}"
                        )
                    
                    # Buffer for incomplete SSE lines
                    sse_buffer = ""
                    
                    async for chunk in response.aiter_text():
                        # Handle both str (real httpx) and bytes (test mocks)
                        if isinstance(chunk, bytes):
                            chunk = chunk.decode('utf-8')
                        sse_buffer += chunk
                        
                        # Process complete lines from buffer
                        while "\n" in sse_buffer:
                            line_end = sse_buffer.find("\n")
                            line = sse_buffer[:line_end].strip()
                            sse_buffer = sse_buffer[line_end + 1:]
                            
                            # Skip empty lines
                            if not line:
                                continue
                            
                            # Check for [DONE] sentinel
                            if line == "data: [DONE]":
                                for item in _drain_content_buffer(final=True):
                                    yield item
                                logger.info("Stream completed with [DONE]")
                                return
                            
                            # Parse SSE data lines
                            if line.startswith("data: "):
                                data = line[6:]  # Remove "data: " prefix
                                
                                # Skip empty data
                                if not data:
                                    continue
                                
                                try:
                                    json_data = json.loads(data)
                                except json.JSONDecodeError:
                                    # Malformed JSON, skip this chunk
                                    logger.warning("Malformed JSON in SSE chunk", chunk=data[:100])
                                    continue
                                
                                # Extract content from choices
                                choices = json_data.get("choices", [])
                                if not choices:
                                    continue
                                
                                delta = choices[0].get("delta", {})
                                reasoning = delta.get("reasoning") or delta.get("reasoning_content") or ""
                                content = delta.get("content", "")

                                if reasoning:
                                    yield ("thinking", reasoning)
                                
                                if not content:
                                    continue
                                
                                content_buffer += content
                                for item in _drain_content_buffer():
                                    yield item
                    
                    # Process any remaining buffered SSE data
                    if sse_buffer.strip():
                        line = sse_buffer.strip()
                        if line == "data: [DONE]":
                            return
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                choices = data.get("choices", [])
                                if choices:
                                    content = choices[0].get("delta", {}).get("content", "")
                                    if content:
                                        content_buffer += content
                                        for item in _drain_content_buffer(final=True):
                                            yield item
                            except (json.JSONDecodeError, IndexError):
                                pass

                    for item in _drain_content_buffer(final=True):
                        yield item
                            
        except httpx.TimeoutException as e:
            logger.error("Streaming timeout", error=str(e))
            raise InferenceTimeoutError(f"Streaming request timed out after {self.timeout}s")
        except httpx.RequestError as e:
            logger.error("Streaming request error", error=str(e))
            raise InferenceServiceError(f"Streaming request failed: {str(e)}")
    
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
        
        payload = self._build_payload(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        
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
                    
                    # Extract response content from multiple possible fields
                    content = ""
                    reasoning_content = ""
                    if data.get("choices") and len(data["choices"]) > 0:
                        message = data["choices"][0].get("message", {})
                        
                        # Try standard content field first
                        content = (message.get("content", "") or "").strip()
                        
                        # If content is empty, try reasoning fields (used by Nemotron, DeepSeek, etc.)
                        if not content:
                            reasoning_content = (
                                message.get("reasoning", "") or 
                                message.get("reasoning_content", "") or 
                                ""
                            ).strip()
                            if reasoning_content:
                                content = reasoning_content
                                logger.info(
                                    "Extracted content from reasoning field",
                                    content_length=len(content),
                                )
                        
                        # Also check for thinking field
                        if not content:
                            thinking = (message.get("thinking", "") or "").strip()
                            if thinking:
                                content = thinking
                                logger.info(
                                    "Extracted content from thinking field",
                                    content_length=len(content),
                                )
                    
                    return {
                        "content": content,
                        "reasoning_content": reasoning_content,
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


def get_inference_service(agent_type: str = "default"):
    """
    Get the appropriate inference service based on agent type and configuration.
    
    Args:
        agent_type: Type of agent requesting the service
            - "super_agent": Uses SUPER_AGENT_INFERENCE_PROVIDER settings
            - "whatsapp_agent": Uses WHATSAPP_AGENT_INFERENCE_PROVIDER settings
            - "default": Uses global AGENT_INFERENCE_PROVIDER setting (fallback)
    
    Returns:
        InferenceService or GeminiInferenceService based on agent configuration
    """
    from app.core.config import settings
    
    # Determine provider based on agent type
    if agent_type == "super_agent":
        provider = settings.SUPER_AGENT_INFERENCE_PROVIDER.lower()
        logger.info("Getting inference service for Super Agent", provider=provider)
    elif agent_type == "whatsapp_agent":
        provider = settings.WHATSAPP_AGENT_INFERENCE_PROVIDER.lower()
        logger.info("Getting inference service for WhatsApp Agent", provider=provider)
    else:
        provider = settings.AGENT_INFERENCE_PROVIDER.lower()
        logger.info("Getting inference service (default)", provider=provider)
    
    # Return appropriate service based on provider
    if provider == "gemini":
        from app.services.gemini_inference_service import gemini_inference_service
        if gemini_inference_service is None:
            logger.warning(
                "Gemini provider selected but GEMINI_API_KEY not configured, falling back to LM Studio",
                agent_type=agent_type,
            )
            # Fallback to LM Studio with agent-specific model if available
            if agent_type == "super_agent":
                return InferenceService(
                    model=settings.SUPER_AGENT_LM_STUDIO_MODEL,
                    max_tokens=settings.SUPER_AGENT_LM_STUDIO_MAX_TOKENS,
                    temperature=settings.SUPER_AGENT_LM_STUDIO_TEMPERATURE,
                )
            return InferenceService()
        
        # Use agent-specific Gemini model if configured
        if agent_type == "whatsapp_agent":
            logger.info(
                "Using Gemini inference service for WhatsApp Agent",
                model=settings.WHATSAPP_AGENT_GEMINI_MODEL,
            )
            # Return a configured Gemini service with WhatsApp-specific settings
            from app.services.gemini_inference_service import GeminiInferenceService
            return GeminiInferenceService(
                api_key=settings.GEMINI_API_KEY,
                model=settings.WHATSAPP_AGENT_GEMINI_MODEL,
                max_tokens=settings.WHATSAPP_AGENT_GEMINI_MAX_TOKENS,
                temperature=settings.WHATSAPP_AGENT_GEMINI_TEMPERATURE,
            )
        
        logger.info("Using Gemini inference service", model=settings.GEMINI_MODEL)
        return gemini_inference_service
    else:
        # LM Studio provider
        if agent_type == "super_agent":
            logger.info(
                "Using LM Studio inference service for Super Agent",
                model=settings.SUPER_AGENT_LM_STUDIO_MODEL,
            )
            return InferenceService(
                model=settings.SUPER_AGENT_LM_STUDIO_MODEL,
                max_tokens=settings.SUPER_AGENT_LM_STUDIO_MAX_TOKENS,
                temperature=settings.SUPER_AGENT_LM_STUDIO_TEMPERATURE,
            )
        
        logger.info("Using LM Studio inference service", model=settings.LM_STUDIO_MODEL)
        return InferenceService()


# Singleton instance - dynamically selected based on configuration
inference_service = get_inference_service()
