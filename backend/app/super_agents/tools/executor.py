"""Tool executor with timeout handling and fallback mechanisms."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Coroutine, Optional, TypeVar

import structlog

from app.super_agents.tools.schemas import ToolExecutionResult, get_tool_timeout

logger = structlog.get_logger()

T = TypeVar("T")


class ToolTimeoutError(Exception):
    """Raised when a tool execution exceeds its timeout."""
    pass


class ToolValidationError(Exception):
    """Raised when tool input validation fails."""
    pass


async def execute_with_timeout(
    coro: Coroutine[Any, Any, T],
    tool_name: str,
    timeout_seconds: Optional[float] = None,
    company_id: Optional[str] = None,
) -> ToolExecutionResult:
    """Execute a coroutine with timeout handling.
    
    Args:
        coro: The coroutine to execute
        tool_name: Name of the tool for logging and timeout lookup
        timeout_seconds: Override timeout (uses default from TOOL_TIMEOUTS if not provided)
        company_id: Company ID for context in logs
        
    Returns:
        ToolExecutionResult with status and result or error
    """
    timeout = timeout_seconds or get_tool_timeout(tool_name)
    start_time = time.time()
    
    logger.info(
        "Starting tool execution with timeout",
        tool=tool_name,
        timeout_seconds=timeout,
        company_id=company_id,
    )
    
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
        execution_time = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Tool execution completed successfully",
            tool=tool_name,
            execution_time_ms=execution_time,
            company_id=company_id,
        )
        
        return ToolExecutionResult(
            success=True,
            status="success",
            result=result,
            execution_time_ms=execution_time,
        )
        
    except asyncio.TimeoutError:
        execution_time = int((time.time() - start_time) * 1000)
        
        logger.warning(
            "Tool execution timed out",
            tool=tool_name,
            timeout_seconds=timeout,
            execution_time_ms=execution_time,
            company_id=company_id,
        )
        
        return ToolExecutionResult(
            success=False,
            status="timeout",
            error=f"Tool execution exceeded {timeout} seconds timeout",
            execution_time_ms=execution_time,
        )
        
    except Exception as exc:
        execution_time = int((time.time() - start_time) * 1000)
        
        logger.error(
            "Tool execution failed",
            tool=tool_name,
            error=str(exc),
            error_type=type(exc).__name__,
            execution_time_ms=execution_time,
            company_id=company_id,
        )
        
        return ToolExecutionResult(
            success=False,
            status="error",
            error=str(exc),
            execution_time_ms=execution_time,
        )


def execute_sync_with_timeout(
    func: Callable[[], T],
    tool_name: str,
    timeout_seconds: Optional[float] = None,
    company_id: Optional[str] = None,
) -> ToolExecutionResult:
    """Execute a synchronous function with timeout using thread pool.
    
    Args:
        func: The synchronous function to execute
        tool_name: Name of the tool for logging and timeout lookup
        timeout_seconds: Override timeout
        company_id: Company ID for context in logs
        
    Returns:
        ToolExecutionResult with status and result or error
    """
    timeout = timeout_seconds or get_tool_timeout(tool_name)
    start_time = time.time()
    
    logger.info(
        "Starting sync tool execution with timeout",
        tool=tool_name,
        timeout_seconds=timeout,
        company_id=company_id,
    )
    
    try:
        # Use ThreadPoolExecutor for sync functions
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            result = future.result(timeout=timeout)
            
        execution_time = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Sync tool execution completed successfully",
            tool=tool_name,
            execution_time_ms=execution_time,
            company_id=company_id,
        )
        
        return ToolExecutionResult(
            success=True,
            status="success",
            result=result,
            execution_time_ms=execution_time,
        )
        
    except concurrent.futures.TimeoutError:
        execution_time = int((time.time() - start_time) * 1000)
        
        logger.warning(
            "Sync tool execution timed out",
            tool=tool_name,
            timeout_seconds=timeout,
            execution_time_ms=execution_time,
            company_id=company_id,
        )
        
        return ToolExecutionResult(
            success=False,
            status="timeout",
            error=f"Tool execution exceeded {timeout} seconds timeout",
            execution_time_ms=execution_time,
        )
        
    except Exception as exc:
        execution_time = int((time.time() - start_time) * 1000)
        
        logger.error(
            "Sync tool execution failed",
            tool=tool_name,
            error=str(exc),
            error_type=type(exc).__name__,
            execution_time_ms=execution_time,
            company_id=company_id,
        )
        
        return ToolExecutionResult(
            success=False,
            status="error",
            error=str(exc),
            execution_time_ms=execution_time,
        )


async def execute_with_fallback(
    primary_coro: Coroutine[Any, Any, T],
    fallback_coro: Coroutine[Any, Any, T],
    tool_name: str,
    timeout_seconds: Optional[float] = None,
    company_id: Optional[str] = None,
) -> ToolExecutionResult:
    """Execute primary coroutine with fallback if it times out or fails.
    
    Args:
        primary_coro: Primary execution coroutine (e.g., Evolution API)
        fallback_coro: Fallback execution coroutine (e.g., database query)
        tool_name: Name of the tool
        timeout_seconds: Timeout for primary execution
        company_id: Company ID for context
        
    Returns:
        ToolExecutionResult with primary or fallback result
    """
    # Try primary first
    primary_result = await execute_with_timeout(
        primary_coro,
        tool_name=f"{tool_name}_primary",
        timeout_seconds=timeout_seconds,
        company_id=company_id,
    )
    
    if primary_result.success:
        return primary_result
    
    # Log fallback attempt
    logger.info(
        "Attempting fallback execution",
        tool=tool_name,
        primary_status=primary_result.status,
        company_id=company_id,
    )
    
    # Try fallback
    fallback_result = await execute_with_timeout(
        fallback_coro,
        tool_name=f"{tool_name}_fallback",
        timeout_seconds=timeout_seconds,  # Same timeout for fallback
        company_id=company_id,
    )
    
    if fallback_result.success:
        fallback_result.used_fallback = True
        return fallback_result
    
    # Both failed - return combined error
    return ToolExecutionResult(
        success=False,
        status="error",
        error=f"Primary failed: {primary_result.error}. Fallback failed: {fallback_result.error}",
        execution_time_ms=primary_result.execution_time_ms,
    )


def validate_and_execute(
    validator_class: type,
    executor_func: Callable,
    input_data: dict[str, Any],
    tool_name: str,
    timeout_seconds: Optional[float] = None,
    company_id: Optional[str] = None,
) -> ToolExecutionResult:
    """Validate input data and execute function with timeout.
    
    Args:
        validator_class: Pydantic model class for validation
        executor_func: Function to execute (sync or async)
        input_data: Raw input data to validate
        tool_name: Name of the tool
        timeout_seconds: Execution timeout
        company_id: Company ID for context
        
    Returns:
        ToolExecutionResult
    """
    start_time = time.time()
    
    # Validate input
    try:
        validated = validator_class(**input_data)
        logger.info(
            "Input validation passed",
            tool=tool_name,
            company_id=company_id,
        )
    except Exception as exc:
        execution_time = int((time.time() - start_time) * 1000)
        
        logger.warning(
            "Input validation failed",
            tool=tool_name,
            error=str(exc),
            company_id=company_id,
        )
        
        return ToolExecutionResult(
            success=False,
            status="validation_error",
            error=f"Invalid input: {str(exc)}",
            execution_time_ms=execution_time,
        )
    
    # Execute
    import inspect
    
    if inspect.iscoroutinefunction(executor_func):
        # Async function - need to run in event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're already in async context, can't use run_until_complete
                # Return a special result indicating async execution needed
                return ToolExecutionResult(
                    success=False,
                    status="error",
                    error="Async execution required - use async version of this function",
                )
            result = loop.run_until_complete(
                execute_with_timeout(
                    executor_func(validated),
                    tool_name=tool_name,
                    timeout_seconds=timeout_seconds,
                    company_id=company_id,
                )
            )
            return result
        except RuntimeError:
            # No event loop running
            return asyncio.run(
                execute_with_timeout(
                    executor_func(validated),
                    tool_name=tool_name,
                    timeout_seconds=timeout_seconds,
                    company_id=company_id,
                )
            )
    else:
        # Sync function
        return execute_sync_with_timeout(
            lambda: executor_func(validated),
            tool_name=tool_name,
            timeout_seconds=timeout_seconds,
            company_id=company_id,
        )
