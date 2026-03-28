"""
Gemini Inference Service - Integration with Google Gemini API for AI model inference.
Provides chat completion and response generation capabilities with thinking support.
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
    role: str  # "user", "model"
    content: str


class GeminiInferenceServiceError(Exception):
    """Custom exception for Gemini inference service errors."""
    pass


class GeminiInferenceTimeoutError(GeminiInferenceServiceError):
    """Raised when inference request times out."""
    pass


class GeminiInferenceRateLimitError(GeminiInferenceServiceError):
    """Raised when rate limit is exceeded."""
    pass


class GeminiInferenceService:
    """
    Service for AI inference using Google Gemini API.
    
    Supports streaming, thinking blocks, and markdown output.
    """
    
    def __init__(
        self,
        api_key: str = None,
        model: str = "gemini-3.1-flash-lite-preview",
        max_tokens: int = 2048,
        temperature: float = 0.7,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        """
        Initialize the Gemini inference service.
        
        Args:
            api_key: Google Gemini API key
            model: Model identifier
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-2)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts on failure
        """
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key:
            raise GeminiInferenceServiceError("GEMINI_API_KEY is required")
        
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Gemini API base URL
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            "Content-Type": "application/json",
        }

    def _build_gemini_messages(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """
        Build message list for Gemini API format.
        
        Gemini uses a different format:
        - System instructions are separate
        - Roles are "user" and "model" (not "assistant")
        - Messages alternate between user and model
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt
            
        Returns:
            Tuple of (system_instruction, contents)
        """
        contents = []
        
        for msg in messages:
            if "parts" in msg:
                role = msg.get("role", "user")

                if role == "system":
                    text_parts = [
                        part.get("text", "")
                        for part in msg.get("parts", [])
                        if isinstance(part, dict) and "text" in part
                    ]
                    system_text = "\n\n".join(part for part in text_parts if part)
                    if system_text:
                        if not system_prompt:
                            system_prompt = system_text
                        else:
                            system_prompt += f"\n\n{system_text}"
                    continue

                if role == "assistant":
                    role = "model"

                contents.append({
                    "role": role,
                    "parts": msg.get("parts", []),
                })
                continue

            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # Convert OpenAI-style roles to Gemini roles
            if role == "system":
                # System messages become part of system instruction
                if not system_prompt:
                    system_prompt = content
                else:
                    system_prompt += f"\n\n{content}"
                continue
            elif role == "assistant":
                role = "model"
            
            contents.append({
                "role": role,
                "parts": [{"text": content}]
            })
        
        return system_prompt, contents

    def _build_payload(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str],
        max_tokens: Optional[int],
        temperature: Optional[float],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Build a request payload for Gemini API."""
        system_instruction, contents = self._build_gemini_messages(messages, system_prompt)
        
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens or self.max_tokens,
                "temperature": temperature if temperature is not None else self.temperature,
                "responseMimeType": "text/plain",
            }
        }
        
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }
        
        if tools:
            payload["tools"] = tools
        
        return payload

    async def astream_chat_completion_with_thinking(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Tuple[str, Any], None]:
        """
        Stream chat completion from Gemini API with thinking detection.
        
        Uses streaming to receive tokens in real-time and parses
        <think>...</think> blocks. Yields typed tuples:
        - ('thinking', token): Content inside think blocks
        - ('response', token): Content outside think blocks
        
        Args:
            messages: List of message dicts
            system_prompt: Optional system prompt
            max_tokens: Override max tokens
            temperature: Override temperature
            tools: Optional list of tool definitions for function calling
            
        Yields:
            Tuple of (type, content) where type is 'thinking' or 'response'
            
        Raises:
            GeminiInferenceServiceError: On API errors or connection issues
            GeminiInferenceTimeoutError: On timeout
        """
        url = f"{self.base_url}/models/{self.model}:streamGenerateContent"
        
        # Build payload
        payload = self._build_payload(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
        )
        
        logger.info(
            "Starting Gemini streaming chat completion",
            url=url,
            model=self.model,
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
                    params={"key": self.api_key},
                ) as response:
                    if response.status_code != 200:
                        try:
                            error_text = await response.aread()
                            error_str = error_text.decode()[:200] if error_text else "Unknown error"
                        except Exception:
                            error_str = f"HTTP {response.status_code}"
                        logger.error(
                            "Gemini streaming error",
                            status_code=response.status_code,
                            error=error_str,
                        )
                        raise GeminiInferenceServiceError(
                            f"Gemini API returned status {response.status_code}"
                        )
                    
                    # Buffer for incomplete JSON - use brace counting for robust parsing
                    json_buffer = ""
                    brace_depth = 0
                    in_string = False
                    escape_next = False
                    
                    async for chunk in response.aiter_text():
                        json_buffer += chunk
                        
                        # Extract complete JSON objects using brace counting
                        while json_buffer:
                            # Find the start of a JSON object
                            obj_start = json_buffer.find("{")
                            if obj_start == -1:
                                json_buffer = ""
                                break
                            
                            # Count braces to find complete object
                            brace_depth = 0
                            in_string = False
                            escape_next = False
                            obj_end = -1
                            
                            for i in range(obj_start, len(json_buffer)):
                                char = json_buffer[i]
                                
                                if escape_next:
                                    escape_next = False
                                    continue
                                
                                if char == "\\" and in_string:
                                    escape_next = True
                                    continue
                                
                                if char == '"' and not escape_next:
                                    in_string = not in_string
                                    continue
                                
                                if not in_string:
                                    if char == "{":
                                        brace_depth += 1
                                    elif char == "}":
                                        brace_depth -= 1
                                        if brace_depth == 0:
                                            obj_end = i
                                            break
                            
                            if obj_end == -1:
                                # No complete object yet, wait for more data
                                break
                            
                            json_str = json_buffer[obj_start:obj_end + 1]
                            json_buffer = json_buffer[obj_end + 1:]
                            
                            try:
                                json_data = json.loads(json_str)
                            except json.JSONDecodeError as e:
                                logger.warning("Failed to parse Gemini JSON", error=str(e), snippet=json_str[:100])
                                continue
                            
                            # Extract content from Gemini response
                            candidates = json_data.get("candidates", [])
                            if not candidates:
                                continue
                            
                            candidate = candidates[0]
                            content_part = candidate.get("content", {})
                            parts = content_part.get("parts", [])
                            
                            # Check for native thinking support (Gemini 2.0+)
                            thought = candidate.get("thought", "")
                            if thought:
                                yield ("thinking", thought)
                            
                            for part in parts:
                                if "functionCall" in part:
                                    for item in _drain_content_buffer():
                                        yield item

                                    func_call = part["functionCall"]
                                    yield (
                                        "tool_call",
                                        {
                                            "name": func_call.get("name", ""),
                                            "arguments": func_call.get("args", {}) or {},
                                        },
                                    )
                                    continue

                                text = part.get("text", "")
                                if not text:
                                    continue
                                
                                content_buffer += text
                                for item in _drain_content_buffer():
                                    yield item
                    
                    # Process any remaining buffered content
                    for item in _drain_content_buffer(final=True):
                        yield item
                            
        except httpx.TimeoutException as e:
            logger.error("Gemini streaming timeout", error=str(e))
            raise GeminiInferenceTimeoutError(f"Streaming request timed out after {self.timeout}s")
        except httpx.RequestError as e:
            logger.error("Gemini streaming request error", error=str(e))
            raise GeminiInferenceServiceError(f"Streaming request failed: {str(e)}")
    
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Send chat completion request to Gemini API.
        
        Args:
            messages: List of message dicts
            system_prompt: Optional system prompt
            max_tokens: Override max tokens
            temperature: Override temperature
            tools: Optional list of tool definitions for function calling
            
        Returns:
            Dict with response content and metadata
            
        Raises:
            GeminiInferenceServiceError: On API errors
            GeminiInferenceTimeoutError: On timeout
            GeminiInferenceRateLimitError: On rate limit
        """
        url = f"{self.base_url}/models/{self.model}:generateContent"
        
        payload = self._build_payload(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
        )
        
        logger.info(
            "Sending Gemini chat completion request",
            url=url,
            model=self.model,
        )
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        url,
                        headers=self._get_headers(),
                        json=payload,
                        params={"key": self.api_key},
                    )
                    
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 5))
                        logger.warning("Rate limited, waiting", retry_after=retry_after)
                        await asyncio.sleep(retry_after)
                        continue
                    
                    if response.status_code != 200:
                        error_detail = response.text
                        logger.error(
                            "Gemini API error",
                            status_code=response.status_code,
                            error=error_detail,
                        )
                        raise GeminiInferenceServiceError(
                            f"API returned status {response.status_code}: {error_detail}"
                        )
                    
                    data = response.json()
                    
                    # Extract response content and tool calls
                    content = ""
                    thinking_content = ""
                    tool_calls = []
                    
                    if data.get("candidates") and len(data["candidates"]) > 0:
                        candidate = data["candidates"][0]
                        content_part = candidate.get("content", {})
                        parts = content_part.get("parts", [])
                        
                        # Check for native thinking support (Gemini 2.0+)
                        thinking_content = candidate.get("thought", "")
                        
                        for part in parts:
                            # Extract text content
                            if "text" in part:
                                content += part.get("text", "")
                            
                            # Extract function calls
                            if "functionCall" in part:
                                func_call = part["functionCall"]
                                tool_calls.append({
                                    "name": func_call.get("name", ""),
                                    "arguments": func_call.get("args", {})
                                })
                        
                        content = content.strip()
                    
                    return {
                        "content": content,
                        "thinking_content": thinking_content,
                        "tool_calls": tool_calls,
                        "model": self.model,
                        "usage": data.get("usageMetadata", {}),
                        "finish_reason": data.get("candidates", [{}])[0].get("finishReason"),
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
            raise GeminiInferenceTimeoutError(f"Request timed out after {self.timeout}s")
        
        raise GeminiInferenceServiceError(f"Request failed: {str(last_error)}")
    
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
            GeminiInferenceServiceError: On API errors
            GeminiInferenceTimeoutError: On timeout
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
        Check if Gemini API is available and responding.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            url = f"{self.base_url}/models/{self.model}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    url,
                    params={"key": self.api_key},
                )
                return response.status_code == 200
        except Exception as e:
            logger.error("Gemini health check failed", error=str(e))
            return False


# Singleton instance
gemini_inference_service = GeminiInferenceService() if settings.GEMINI_API_KEY else None