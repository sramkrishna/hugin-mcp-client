"""Base interface for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, max_conversation_turns: int = 10, enable_summarization: bool = False):
        """
        Initialize the provider.

        Args:
            max_conversation_turns: Maximum number of user-assistant turn pairs to keep
                                   (default: 10 turns = ~20 messages)
            enable_summarization: Enable automatic conversation summarization (experimental)
        """
        self.conversation_history: List[Dict[str, Any]] = []
        self.max_conversation_turns = max_conversation_turns
        self.first_user_message: str | None = None
        self.enable_summarization = enable_summarization
        self.conversation_summary: str | None = None

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
        if content:  # Only add non-empty messages
            # Save the first user message
            if self.first_user_message is None:
                self.first_user_message = content
            self.conversation_history.append({"role": "user", "content": content})
            self._prune_history()

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to conversation history."""
        self.conversation_history.append({"role": "assistant", "content": content})
        self._prune_history()

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []
        self.first_user_message = None

    def _prune_history(self) -> None:
        """
        Prune conversation history to stay within token limits.
        Keeps the most recent turns while preserving conversation context.
        """
        if len(self.conversation_history) <= self.max_conversation_turns * 2:
            return

        # Count actual conversation turns (user messages that aren't tool results)
        turn_count = 0
        for msg in self.conversation_history:
            if msg["role"] == "user":
                # Check if it's a regular user message (not a tool result)
                content = msg.get("content", "")
                if isinstance(content, str):
                    turn_count += 1

        # If we're over the limit, prune from the middle
        # Keep: first user message + recent turns
        if turn_count > self.max_conversation_turns:
            # Find the first user message
            first_user_idx = None
            for i, msg in enumerate(self.conversation_history):
                if msg["role"] == "user" and isinstance(msg.get("content"), str):
                    first_user_idx = i
                    break

            # Keep first turn (first user + any assistant/tool responses)
            # Then keep only the most recent max_conversation_turns
            messages_to_keep = self.max_conversation_turns * 2  # approximate

            if len(self.conversation_history) > messages_to_keep:
                # Keep first user message and recent history
                if first_user_idx is not None:
                    recent_start = max(first_user_idx + 1, len(self.conversation_history) - messages_to_keep)
                    self.conversation_history = (
                        [self.conversation_history[first_user_idx]] +
                        self.conversation_history[recent_start:]
                    )
                else:
                    # No first message found, just keep recent
                    self.conversation_history = self.conversation_history[-messages_to_keep:]
