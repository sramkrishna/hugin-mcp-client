"""Base interface for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self):
        """Initialize the provider."""
        self.conversation_history: List[Dict[str, Any]] = []

    @abstractmethod
    def create_message(
        self,
        user_message: str,
        tools: List[Dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> Any:
        """
        Send a message to the LLM.

        Args:
            user_message: The user's message
            tools: Optional list of tools available to the LLM
            max_tokens: Maximum tokens in response

        Returns:
            LLM response
        """
        pass

    @abstractmethod
    def extract_text_response(self, response: Any) -> str:
        """Extract text content from LLM response."""
        pass

    @abstractmethod
    def extract_tool_calls(self, response: Any) -> List[Dict[str, Any]]:
        """
        Extract tool calls from LLM response.

        Returns:
            List of tool calls with 'id', 'name', and 'input' keys
        """
        pass

    @abstractmethod
    def add_tool_result(self, tool_use_id: str, result: str, response: Any) -> None:
        """
        Add tool result to conversation history.

        Args:
            tool_use_id: ID of the tool use from the LLM response
            result: Result from the tool execution
            response: The full response object from the previous LLM call
        """
        pass

    def add_user_message(self, content: str) -> None:
        """Add a user message to conversation history."""
        self.conversation_history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to conversation history."""
        self.conversation_history.append({"role": "assistant", "content": content})

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []
