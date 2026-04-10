"""
Custom exceptions for WhatsApp Agent.

These exceptions provide specific error types for different failure scenarios
in the WhatsApp Agent message processing pipeline, making debugging easier.
"""


class WhatsAppAgentError(Exception):
    """Base exception for WhatsApp Agent errors."""

    def __init__(self, message: str, context: dict | None = None):
        self.message = message
        self.context = context or {}
        super().__init__(self.message)

    def __str__(self):
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message


class AgentNotEnabledError(WhatsAppAgentError):
    """Raised when agent is not enabled for the instance."""

    pass


class AgentNotAssignedError(WhatsAppAgentError):
    """Raised when no agent is assigned to the instance."""

    pass


class AgentInactiveError(WhatsAppAgentError):
    """Raised when assigned agent is inactive."""

    pass


class MessageProcessingError(WhatsAppAgentError):
    """Raised when message processing fails."""

    pass


class InferenceError(WhatsAppAgentError):
    """Raised when LM Studio inference fails."""

    pass


class EvolutionAPIError(WhatsAppAgentError):
    """Raised when Evolution API communication fails."""

    pass


class ContextLoadError(WhatsAppAgentError):
    """Raised when conversation context loading fails."""

    pass


class IntentClassificationError(WhatsAppAgentError):
    """Raised when intent classification fails."""

    pass


class ResponseGenerationError(WhatsAppAgentError):
    """Raised when response generation fails."""

    pass


class ToolExecutionError(WhatsAppAgentError):
    """Raised when tool execution fails."""

    pass


class ConversationNotFoundError(WhatsAppAgentError):
    """Raised when conversation is not found."""

    pass


class InstanceNotFoundError(WhatsAppAgentError):
    """Raised when instance is not found."""

    pass
