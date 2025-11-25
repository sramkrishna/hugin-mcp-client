"""Base interface for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, max_conversation_turns: int = 5, enable_summarization: bool = False, max_history_tokens: int = 150000):
        """
        Initialize the provider.

        Args:
            max_conversation_turns: Maximum number of user-assistant turn pairs to keep
                                   (default: 5 turns = ~10 messages, more aggressive)
            enable_summarization: Enable automatic conversation summarization (experimental)
            max_history_tokens: Maximum tokens to keep in history (default: 150k, leaves 50k for tools/system)
        """
        self.conversation_history: List[Dict[str, Any]] = []
        self.max_conversation_turns = max_conversation_turns
        self.max_history_tokens = max_history_tokens
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

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Uses rough approximation: 1 token ≈ 4 characters.
        """
        return len(text) // 4

    def _estimate_message_tokens(self, message: Dict[str, Any]) -> int:
        """Estimate tokens in a message."""
        total = 0
        content = message.get("content", "")

        if isinstance(content, str):
            total += self._estimate_tokens(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    if "text" in item:
                        total += self._estimate_tokens(str(item["text"]))
                    if "tool_result" in item:
                        # Tool results can be large, count them
                        total += self._estimate_tokens(str(item["tool_result"]))
                elif isinstance(item, str):
                    total += self._estimate_tokens(item)

        return total

    def _prune_history(self) -> None:
        """
        Prune conversation history to stay within token limits.
        Uses aggressive token-aware pruning to prevent context overflow.
        """
        # Quick check: if history is short, no need to prune
        if len(self.conversation_history) <= 4:
            return

        # Estimate total tokens in history
        total_tokens = sum(self._estimate_message_tokens(msg) for msg in self.conversation_history)

        # If we're over the token limit, aggressively prune
        if total_tokens > self.max_history_tokens:
            # Keep only the most recent messages that fit within budget
            messages_to_keep = []
            current_tokens = 0

            # Start from the end (most recent) and work backwards
            for msg in reversed(self.conversation_history):
                msg_tokens = self._estimate_message_tokens(msg)
                if current_tokens + msg_tokens <= self.max_history_tokens:
                    messages_to_keep.insert(0, msg)
                    current_tokens += msg_tokens
                else:
                    break

            self.conversation_history = messages_to_keep

        # Also enforce turn count limit as a secondary measure
        elif len(self.conversation_history) > self.max_conversation_turns * 2:
            # Keep only recent turns
            messages_to_keep = self.max_conversation_turns * 2
            self.conversation_history = self.conversation_history[-messages_to_keep:]
