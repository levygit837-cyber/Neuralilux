"""
Vertex AI Inference Service - Integration with Google Vertex AI Express Mode.
Uses google-genai SDK with API key authentication (no project ID required).
Supports chat completion and native function calling (tools).
"""

import warnings
warnings.filterwarnings("ignore", message="Field name .* shadows an attribute in parent")

from google import genai
from google.genai.types import (
    FunctionDeclaration,
    GenerateContentConfig,
    Tool,
    Content,
    Part,
    ThinkingConfig,
)
import structlog
from typing import List, Optional, Dict, Any, AsyncGenerator, Tuple
from dataclasses import dataclass
from app.core.config import settings

logger = structlog.get_logger()


class VertexInferenceServiceError(Exception):
    """Custom exception for Vertex AI inference service errors."""
    pass


class VertexInferenceTimeoutError(VertexInferenceServiceError):
    """Raised when inference request times out."""
    pass


class VertexInferenceRateLimitError(VertexInferenceServiceError):
    """Raised when rate limit is exceeded."""
    pass


@dataclass
class ToolCall:
    """Represents a tool call from the model."""
    name: str
    args: Dict[str, Any]
    call_id: Optional[str] = None


@dataclass
class InferenceResult:
    """Result from inference including text and optional tool calls."""
    text: str
    tool_calls: List[ToolCall]
    finish_reason: str
    usage: Optional[Dict[str, int]] = None


class VertexInferenceService:
    """
    Service for AI inference using Vertex AI Express Mode.

    Features:
    - API key authentication (no project/location needed)
    - Supports gemini-3.1-flash-lite-preview and other Gemini models
    - Native function calling (tools)
    - Streaming support
    - Proper error handling with custom exceptions
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-3-flash-preview",
        max_tokens: int = 2048,
        temperature: float = 0.7,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key or settings.VERTEX_API_KEY
        if not self.api_key:
            raise VertexInferenceServiceError("VERTEX_API_KEY is required")

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries

        # Initialize Vertex AI client in Express Mode
        self.client = genai.Client(
            vertexai=True,
            api_key=self.api_key,
        )

        logger.info(
            "VertexInferenceService initialized",
            model=self.model,
            max_tokens=self.max_tokens,
        )

    def _convert_tools_to_vertex_format(
        self, tools: Optional[List[Dict[str, Any]]]
    ) -> Optional[List[Tool]]:
        """Convert OpenAI-format tools to Vertex AI FunctionDeclaration format."""
        if not tools:
            return None

        function_declarations = []
        for tool in tools:
            # Handle OpenAI format: {"type": "function", "function": {...}}
            if "function" in tool:
                func_data = tool["function"]
                func_decl = FunctionDeclaration(
                    name=func_data.get("name", ""),
                    description=func_data.get("description", ""),
                    parameters=func_data.get("parameters", {"type": "object", "properties": {}}),
                )
            else:
                # Handle flat format: {"name": ..., "description": ..., "parameters": ...}
                func_decl = FunctionDeclaration(
                    name=tool.get("name", ""),
                    description=tool.get("description", ""),
                    parameters=tool.get("parameters", {"type": "object", "properties": {}}),
                )
            function_declarations.append(func_decl)

        if not function_declarations:
            return None

        return [Tool(function_declarations=function_declarations)]

    def _build_contents(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> tuple[Optional[str], List[Content]]:
        """
        Build Vertex AI contents format from messages.

        Vertex AI uses Content/Part structure:
        - roles: "user", "model"
        - system instructions are separate parameter
        - "tool" messages are converted to "user" format
        """
        system_instruction = system_prompt
        contents = []

        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")

            # Map "assistant" to "model" for Vertex AI
            if role == "assistant":
                role = "model"

            # Skip system messages (handled separately)
            if role == "system":
                if not system_instruction:
                    system_instruction = content
                continue

            # Convert "tool" role to "user" with formatted content
            if role == "tool":
                role = "user"
                tool_name = msg.get("tool_call_id", "unknown")
                content = f"[Tool result for {tool_name}]: {content}"

            if content:  # Only add if there's content
                contents.append(Content(
                    role=role,
                    parts=[Part(text=content)],
                ))

        return system_instruction, contents

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> InferenceResult:
        """
        Generate completion with optional tool calling.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt override
            tools: List of tool definitions for function calling
            max_tokens: Override max tokens for this request
            temperature: Override temperature for this request

        Returns:
            InferenceResult with text and optional tool calls
        """
        try:
            # Build contents
            system_instruction, contents = self._build_contents(
                messages, system_prompt
            )

            # Convert tools to Vertex format
            vertex_tools = self._convert_tools_to_vertex_format(tools)

            # Build config
            config = GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
            )

            if vertex_tools:
                config.tools = vertex_tools

            # Make request
            logger.debug(
                "Sending request to Vertex AI",
                model=self.model,
                message_count=len(contents),
                has_tools=bool(vertex_tools),
            )

            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )

            # Extract text and tool calls
            text = ""
            tool_calls = []

            if response.candidates:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if part.text:
                            text += part.text
                        elif part.function_call:
                            tool_calls.append(ToolCall(
                                name=part.function_call.name,
                                args=dict(part.function_call.args) if part.function_call.args else {},
                                call_id=getattr(part.function_call, 'id', None),
                            ))

            # Get usage if available
            usage = None
            if response.usage_metadata:
                usage = {
                    "prompt_tokens": response.usage_metadata.prompt_token_count or 0,
                    "completion_tokens": response.usage_metadata.candidates_token_count or 0,
                    "total_tokens": response.usage_metadata.total_token_count or 0,
                }

            logger.info(
                "Vertex AI inference completed",
                model=self.model,
                text_length=len(text),
                tool_call_count=len(tool_calls),
                usage=usage,
            )

            return InferenceResult(
                text=text,
                tool_calls=tool_calls,
                finish_reason=candidate.finish_reason if candidate else "unknown",
                usage=usage,
            )

        except Exception as e:
            error_msg = str(e).lower()
            if "timeout" in error_msg or "deadline exceeded" in error_msg:
                logger.error("Vertex AI timeout", error=str(e))
                raise VertexInferenceTimeoutError(f"Request timed out: {e}")
            elif "rate limit" in error_msg or "quota exceeded" in error_msg:
                logger.error("Vertex AI rate limit", error=str(e))
                raise VertexInferenceRateLimitError(f"Rate limit exceeded: {e}")
            else:
                logger.error("Vertex AI inference error", error=str(e))
                raise VertexInferenceServiceError(f"Inference failed: {e}")

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream completion from Vertex AI.

        Yields text chunks as they arrive.
        """
        try:
            system_instruction, contents = self._build_contents(
                messages, system_prompt
            )

            vertex_tools = self._convert_tools_to_vertex_format(tools)

            config = GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
            )

            if vertex_tools:
                config.tools = vertex_tools

            logger.debug("Starting Vertex AI stream", model=self.model)

            for chunk in self.client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config,
            ):
                if chunk.candidates:
                    for part in chunk.candidates[0].content.parts:
                        if part.text:
                            yield part.text

            logger.debug("Vertex AI stream completed")

        except Exception as e:
            logger.error("Vertex AI streaming error", error=str(e))
            raise VertexInferenceServiceError(f"Streaming failed: {e}")

    async def stream_chat_completion_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tool_choice: str = "auto",
        on_thinking_token: Any = None,
        on_response_token: Any = None,
    ) -> Dict[str, Any]:
        """
        Streaming chat completion with tool calling for SuperAgent compatibility.

        Streams the response via callbacks so that thinking/reasoning tokens
        can be forwarded to the frontend in real-time via *on_thinking_token*,
        and response content tokens via *on_response_token*.
        Tool calls are accumulated internally and returned in the final result.

        Args:
            messages:          OpenAI-format messages list.
            tools:             OpenAI-format tool definitions.
            system_prompt:     Optional system prompt.
            max_tokens:        Override default max_tokens.
            temperature:       Override default temperature.
            tool_choice:       "auto" | "none" | "required" (Vertex AI only supports "auto").
            on_thinking_token: ``async def(token: str)`` callback fired
                               for every thinking/reasoning token.
            on_response_token: ``async def(token: str)`` callback fired
                               for every response content token.

        Returns:
            Dict with content, tool_calls, model, usage, finish_reason.
        """
        try:
            # Build contents
            system_instruction, contents = self._build_contents(
                messages, system_prompt
            )

            # Convert tools to Vertex format
            vertex_tools = self._convert_tools_to_vertex_format(tools)

            # Build config
            config = GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
            )

            # Enable native thinking for Gemini 3 models
            if "gemini-3" in self.model.lower() or "gemini-2.5" in self.model.lower():
                config.thinking_config = ThinkingConfig(
                    include_thoughts=True,
                )
                logger.debug(
                    "Native thinking enabled with include_thoughts for Vertex AI",
                    model=self.model,
                    thinking_config=config.thinking_config,
                )

            if vertex_tools and tool_choice != "none":
                config.tools = vertex_tools
                # Note: We handle tool calls manually, not using automatic function calling

            logger.debug(
                "Starting Vertex AI streaming tool completion",
                model=self.model,
                message_count=len(contents),
                has_tools=bool(vertex_tools),
                tool_choice=tool_choice,
            )

            # Accumulators
            content_parts: List[str] = []
            tool_calls_acc: List[ToolCall] = []
            finish_reason = "unknown"

            # State machine for thinking detection inside content
            in_think_block = False
            tag_buffer = ""
            THINK_OPEN = "<thinking>"
            THINK_CLOSE = "</thinking>"

            async def _flush_thinking(text: str) -> None:
                """Forward thinking text to the callback if present."""
                if text and on_thinking_token is not None:
                    await on_thinking_token(text)

            async def _process_content_token(token: str) -> None:
                """
                Parse content for thinking blocks. Thinking content is sent
                to the callback; everything else is accumulated as response
                AND streamed in real-time via on_response_token.
                """
                nonlocal in_think_block, tag_buffer

                tag_buffer += token

                while tag_buffer:
                    if in_think_block:
                        close_idx = tag_buffer.find(THINK_CLOSE)
                        if close_idx != -1:
                            think_text = tag_buffer[:close_idx]
                            await _flush_thinking(think_text)
                            tag_buffer = tag_buffer[close_idx + len(THINK_CLOSE):]
                            in_think_block = False
                            continue

                        # Keep enough buffer to detect closing tag across chunks
                        safe = max(0, len(tag_buffer) - (len(THINK_CLOSE) - 1))
                        if safe > 0:
                            await _flush_thinking(tag_buffer[:safe])
                            tag_buffer = tag_buffer[safe:]
                        break  # wait for more data
                    else:
                        open_idx = tag_buffer.find(THINK_OPEN)
                        if open_idx != -1:
                            prefix = tag_buffer[:open_idx]
                            if prefix:
                                content_parts.append(prefix)
                                # Stream response token in real-time
                                if on_response_token is not None:
                                    await on_response_token(prefix)
                            tag_buffer = tag_buffer[open_idx + len(THINK_OPEN):]
                            in_think_block = True
                            continue

                        safe = max(0, len(tag_buffer) - (len(THINK_OPEN) - 1))
                        if safe == 0:
                            break  # wait for more data
                        response_chunk = tag_buffer[:safe]
                        content_parts.append(response_chunk)
                        # Stream response token in real-time
                        if response_chunk and on_response_token is not None:
                            await on_response_token(response_chunk)
                        tag_buffer = tag_buffer[safe:]

            async def _finalize_tag_buffer() -> None:
                """Finalize any remaining content in the tag buffer."""
                nonlocal tag_buffer, in_think_block
                if tag_buffer:
                    if in_think_block:
                        await _flush_thinking(tag_buffer)
                    else:
                        content_parts.append(tag_buffer)
                        # Stream final response token in real-time
                        if on_response_token is not None:
                            await on_response_token(tag_buffer)
                    tag_buffer = ""

            # Stream the response
            for chunk in self.client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config,
            ):
                if chunk.candidates:
                    candidate = chunk.candidates[0]

                    # Track finish reason
                    if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
                        finish_reason = str(candidate.finish_reason)

                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            # Handle native thinking field (Gemini 2.5+)
                            # Note: part.thought is a boolean flag, actual content is in part.text
                            if hasattr(part, 'thought') and part.thought:
                                # This part contains thinking content, extract from text
                                if part.text:
                                    thinking_content = part.text
                                    # Send thinking tokens via callback
                                    if on_thinking_token is not None:
                                        await on_thinking_token(thinking_content)
                                    logger.debug(
                                        "Native thinking token received from Vertex AI",
                                        thinking_length=len(thinking_content),
                                    )
                            elif part.text:
                                # Process text through thinking block detection (for compatibility)
                                await _process_content_token(part.text)
                            elif part.function_call:
                                # Capture tool call
                                tool_call = ToolCall(
                                    name=part.function_call.name,
                                    args=dict(part.function_call.args) if part.function_call.args else {},
                                    call_id=getattr(part.function_call, 'id', None),
                                )
                                tool_calls_acc.append(tool_call)
                                logger.debug(
                                    "Tool call captured during streaming",
                                    tool_name=tool_call.name,
                                )

            # Finalize any remaining buffer
            await _finalize_tag_buffer()

            # Build final content
            final_content = "".join(content_parts).strip()

            # Convert tool calls to OpenAI format
            parsed_tool_calls: List[Dict[str, Any]] = []
            for idx, tc in enumerate(tool_calls_acc):
                parsed_tool_calls.append({
                    "id": tc.call_id or f"call_{idx}",
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.args,
                    },
                })

            if parsed_tool_calls:
                logger.info(
                    "Streamed tool calls received from Vertex AI",
                    count=len(parsed_tool_calls),
                    tools=[tc["function"]["name"] for tc in parsed_tool_calls],
                )
                finish_reason = "tool_calls"

            logger.info(
                "Vertex AI streaming tool completion completed",
                model=self.model,
                content_length=len(final_content),
                tool_call_count=len(parsed_tool_calls),
            )

            return {
                "content": final_content,
                "tool_calls": parsed_tool_calls,
                "model": self.model,
                "usage": {},  # Vertex AI streaming doesn't provide usage in real-time
                "finish_reason": finish_reason,
            }

        except Exception as e:
            logger.error("Vertex AI streaming tool completion error", error=str(e))
            raise VertexInferenceServiceError(f"Streaming tool completion failed: {e}")

    async def astream_chat_completion_with_thinking(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Tuple[str, str], None]:
        """
        Stream chat completion from Vertex AI with thinking detection.

        Yields typed tuples:
        - ('thinking', token): Content inside native thinking blocks
        - ('response', token): Content outside thinking blocks

        This method is used by the WhatsApp agent graph to stream thinking tokens
        to the frontend via socket events.

        Args:
            messages: List of message dicts
            system_prompt: Optional system prompt
            max_tokens: Override max tokens
            temperature: Override temperature
            tools: Optional tool definitions

        Yields:
            Tuple of (type, content) where type is 'thinking' or 'response'
        """
        # Convert tools to Vertex format
        vertex_tools = self._convert_tools_to_vertex_format(tools) if tools else None

        # Build config
        config = GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens or self.max_tokens,
            temperature=temperature or self.temperature,
        )

        # Enable native thinking for Gemini 3 models
        if "gemini-3" in self.model.lower() or "gemini-2.5" in self.model.lower():
            config.thinking_config = ThinkingConfig(
                include_thoughts=True,
            )
            logger.debug(
                "Native thinking enabled with include_thoughts for Vertex AI streaming",
                model=self.model,
                thinking_config=config.thinking_config,
            )

        if vertex_tools:
            config.tools = vertex_tools

        # Convert messages to Vertex format
        contents = self._convert_messages_to_vertex_format(messages)

        logger.debug(
            "Starting Vertex AI streaming with thinking",
            model=self.model,
            message_count=len(contents),
            has_tools=bool(vertex_tools),
        )

        try:
            # Stream the response
            for chunk in self.client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config,
            ):
                if chunk.candidates:
                    candidate = chunk.candidates[0]

                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            # Handle native thinking field (Gemini 2.5+)
                            if hasattr(part, 'thought') and part.thought:
                                # This part contains thinking content, extract from text
                                if part.text:
                                    yield ("thinking", part.text)
                                    logger.debug(
                                        "Thinking token yielded",
                                        thinking_length=len(part.text),
                                    )
                            elif part.text:
                                # Regular response content
                                yield ("response", part.text)
                            elif part.function_call:
                                # Tool calls are handled separately in this streaming method
                                # For now, we'll just log them
                                logger.debug(
                                    "Tool call encountered in streaming",
                                    tool_name=part.function_call.name,
                                )

        except Exception as e:
            logger.error("Vertex AI streaming with thinking error", error=str(e))
            raise VertexInferenceServiceError(f"Streaming with thinking failed: {e}")


# Global service instance (singleton pattern like other services)
vertex_inference_service: Optional[VertexInferenceService] = None


def get_vertex_inference_service(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> VertexInferenceService:
    """Get or create VertexInferenceService singleton."""
    global vertex_inference_service

    if vertex_inference_service is None:
        vertex_inference_service = VertexInferenceService(
            api_key=api_key,
            model=model or settings.VERTEX_MODEL,
            max_tokens=max_tokens or settings.VERTEX_MAX_TOKENS,
            temperature=temperature or settings.VERTEX_TEMPERATURE,
        )

    return vertex_inference_service
