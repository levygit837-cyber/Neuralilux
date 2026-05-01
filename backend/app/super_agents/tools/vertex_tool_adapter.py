"""
Vertex AI Tool Adapter - Converts internal tool definitions to Vertex AI format.

This adapter converts OpenAI-format tool schemas to Vertex AI FunctionDeclaration format
for native function calling support with Vertex AI models.
"""

import warnings
warnings.filterwarnings("ignore", message="Field name .* shadows an attribute in parent")

from typing import List, Dict, Any, Optional
from google.genai.types import FunctionDeclaration, Tool
import structlog

from app.super_agents.tools.tool_schemas import SUPER_AGENT_TOOLS

logger = structlog.get_logger()


def convert_openai_tool_to_vertex(tool: Dict[str, Any]) -> FunctionDeclaration:
    """
    Convert OpenAI-format tool to Vertex AI FunctionDeclaration.

    OpenAI format:
    {
        "type": "function",
        "function": {
            "name": "tool_name",
            "description": "Tool description",
            "parameters": {...}
        }
    }

    Vertex AI format:
    FunctionDeclaration(
        name="tool_name",
        description="Tool description",
        parameters={...}
    )

    Args:
        tool: OpenAI-format tool definition

    Returns:
        Vertex AI FunctionDeclaration
    """
    function_data = tool.get("function", {})

    name = function_data.get("name", "")
    description = function_data.get("description", "")
    parameters = function_data.get("parameters", {"type": "object", "properties": {}})

    return FunctionDeclaration(
        name=name,
        description=description,
        parameters=parameters,
    )


def convert_tools_to_vertex_format(
    tools: List[Dict[str, Any]]
) -> List[Tool]:
    """
    Convert list of OpenAI-format tools to Vertex AI format.

    Args:
        tools: List of OpenAI-format tool definitions

    Returns:
        List of Vertex AI Tool objects containing FunctionDeclarations
    """
    if not tools:
        return []

    function_declarations = []
    for tool in tools:
        try:
            func_decl = convert_openai_tool_to_vertex(tool)
            function_declarations.append(func_decl)
            logger.debug("Converted tool to Vertex format", tool_name=tool.get("function", {}).get("name"))
        except Exception as e:
            logger.warning(
                "Failed to convert tool to Vertex format",
                tool_name=tool.get("function", {}).get("name"),
                error=str(e)
            )

    if not function_declarations:
        return []

    return [Tool(function_declarations=function_declarations)]


def get_vertex_tools_for_super_agent() -> List[Tool]:
    """
    Get all Super Agent tools formatted for Vertex AI.

    Returns:
        List of Vertex AI Tool objects ready to pass to VertexInferenceService
    """
    return convert_tools_to_vertex_format(SUPER_AGENT_TOOLS)


def extract_function_call_args(tool_call: Any) -> Dict[str, Any]:
    """
    Extract arguments from a Vertex AI function call.

    Vertex AI returns function calls in the format:
    FunctionCall(name="func_name", args={"key": "value"})

    Args:
        tool_call: Vertex AI function call object

    Returns:
        Dictionary of argument name to value
    """
    if hasattr(tool_call, 'args') and tool_call.args:
        return dict(tool_call.args)
    return {}


def format_tool_result_for_agent(
    tool_name: str,
    tool_args: Dict[str, Any],
    tool_result: Any
) -> Dict[str, Any]:
    """
    Format a tool execution result for returning to the agent.

    This creates a standardized response format that can be used
    in the conversation history.

    Args:
        tool_name: Name of the tool that was called
        tool_args: Arguments passed to the tool
        tool_result: Result returned by the tool

    Returns:
        Formatted tool result dictionary
    """
    return {
        "role": "tool",
        "tool_call_id": None,  # Vertex AI doesn't provide call IDs like OpenAI
        "name": tool_name,
        "content": str(tool_result) if tool_result is not None else "",
    }
