"""Pydantic schemas for validating Evolution API payloads and tool inputs."""
from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class EvolutionSendMessagePayload(BaseModel):
    """Schema for Evolution API sendText endpoint payload.
    
    POST /message/sendText/{instance}
    """
    number: str = Field(..., description="Phone number without @s.whatsapp.net suffix")
    text: str = Field(..., min_length=1, max_length=4096, description="Message text content")
    options: dict[str, Any] = Field(
        default_factory=lambda: {"delay": 1200, "presence": "composing"},
        description="Message sending options"
    )

    @field_validator("number")
    @classmethod
    def normalize_number(cls, v: str) -> str:
        """Remove @s.whatsapp.net suffix and non-digit characters."""
        if "@" in v:
            v = v.split("@")[0]
        # Keep only digits
        return re.sub(r"\D", "", v)

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        """Ensure text is not empty after stripping."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message text cannot be empty")
        return stripped

    @field_validator("options")
    @classmethod
    def validate_options(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Ensure options has valid delay and presence values."""
        if "delay" in v:
            try:
                delay = int(v["delay"])
                if delay < 0 or delay > 60000:
                    raise ValueError("Delay must be between 0 and 60000ms")
            except (TypeError, ValueError):
                raise ValueError("Delay must be a valid integer")
        
        if "presence" in v:
            presence = v["presence"]
            if presence not in ("composing", "paused", "recording", "typing"):
                raise ValueError("Presence must be one of: composing, paused, recording, typing")
        
        return v


class EvolutionReadMessagesPayload(BaseModel):
    """Schema for Evolution API findMessages endpoint payload.
    
    POST /chat/findMessages/{instance}
    """
    where: dict[str, Any] = Field(..., description="Query filter conditions")
    limit: int = Field(default=20, ge=1, le=100, description="Number of messages to fetch")

    @model_validator(mode="after")
    def validate_where_clause(self) -> "EvolutionReadMessagesPayload":
        """Ensure where clause contains remoteJid."""
        where = self.where
        if not isinstance(where, dict):
            raise ValueError("where clause must be a dictionary")
        
        key = where.get("key")
        if not isinstance(key, dict):
            raise ValueError("where.key must be a dictionary")
        
        remote_jid = key.get("remoteJid")
        if not remote_jid or not isinstance(remote_jid, str):
            raise ValueError("where.key.remoteJid is required and must be a string")
        
        # Validate JID format
        if "@" not in remote_jid:
            raise ValueError("remoteJid must be in format: number@s.whatsapp.net")
        
        return self


class EvolutionListContactsPayload(BaseModel):
    """Schema for Evolution API findContacts endpoint payload.
    
    POST /chat/findContacts/{instance}
    """
    # This endpoint accepts an empty body, but we include instance_name for validation
    instance_name: str = Field(..., min_length=1, description="Evolution API instance name")


class SendMessageToolInput(BaseModel):
    """Schema for whatsapp_send_message_tool input parameters."""
    instance_name: str = Field(..., min_length=1, description="Evolution API instance name")
    remote_jid: str = Field(..., min_length=1, description="Contact JID (e.g., 5511999999999@s.whatsapp.net)")
    message: str = Field(..., min_length=1, max_length=4096, description="Message text to send")

    @field_validator("remote_jid")
    @classmethod
    def validate_remote_jid(cls, v: str) -> str:
        """Ensure remote_jid has proper format."""
        if "@" not in v:
            # Try to normalize
            digits = re.sub(r"\D", "", v)
            if not digits:
                raise ValueError("remote_jid must contain a valid phone number")
            return f"{digits}@s.whatsapp.net"
        
        # Validate suffix
        if not v.endswith("@s.whatsapp.net"):
            raise ValueError("remote_jid must end with @s.whatsapp.net")
        
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Ensure message is not empty after stripping."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("message cannot be empty")
        return stripped

    def to_evolution_payload(self) -> EvolutionSendMessagePayload:
        """Convert to Evolution API payload format."""
        return EvolutionSendMessagePayload(
            number=self.remote_jid,
            text=self.message,
        )


class ReadMessagesToolInput(BaseModel):
    """Schema for whatsapp_read_messages_tool input parameters."""
    instance_name: str = Field(..., min_length=1, description="Evolution API instance name")
    remote_jid: str = Field(..., min_length=1, description="Contact JID")
    limit: int = Field(default=20, ge=1, le=100, description="Number of messages to fetch")

    @field_validator("remote_jid")
    @classmethod
    def validate_remote_jid(cls, v: str) -> str:
        """Ensure remote_jid has proper format."""
        if "@" not in v:
            digits = re.sub(r"\D", "", v)
            if not digits:
                raise ValueError("remote_jid must contain a valid phone number")
            return f"{digits}@s.whatsapp.net"
        return v


class ListContactsToolInput(BaseModel):
    """Schema for whatsapp_list_contacts_tool input parameters."""
    company_id: str = Field(..., min_length=1, description="Company ID")
    search: Optional[str] = Field(default=None, description="Optional search term")
    instance_name: Optional[str] = Field(default=None, description="Optional instance name filter")
    limit: int = Field(default=20, ge=1, le=50, description="Maximum number of contacts to return")


class ToolExecutionResult(BaseModel):
    """Result of a tool execution with status tracking."""
    success: bool = Field(..., description="Whether the execution succeeded")
    status: str = Field(..., description="Execution status: success, timeout, error, validation_error")
    result: Any = Field(default=None, description="Tool output data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    execution_time_ms: Optional[int] = Field(default=None, description="Execution time in milliseconds")
    used_fallback: bool = Field(default=False, description="Whether fallback data source was used")


# Timeout configurations per tool type (in seconds)
TOOL_TIMEOUTS = {
    "whatsapp_list_contacts": 10,
    "whatsapp_resolve_contacts": 10,
    "whatsapp_read_messages": 15,
    "whatsapp_send_message": 10,
    "whatsapp_send_bulk": 30,
    "database_query": 15,
    "menu_lookup": 10,
    "web_search": 15,
    "web_fetch": 10,
    "knowledge_store": 5,
    "knowledge_search": 5,
    "document_create": 10,
}


def get_tool_timeout(tool_name: str, default: float = 10.0) -> float:
    """Get timeout for a specific tool name."""
    return TOOL_TIMEOUTS.get(tool_name, default)
