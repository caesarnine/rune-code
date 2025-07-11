"""Re-exports pydantic-ai message types so outer layers don't import pydantic-ai directly."""

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter

__all__ = ["ModelMessage", "ModelMessagesTypeAdapter"]
