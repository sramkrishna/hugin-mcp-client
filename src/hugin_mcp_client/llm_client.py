"""LLM client for interacting with language models."""

import logging
from typing import Any, Dict, List, Optional

from anthropic import Anthropic
from anthropic.types import Message, TextBlock, ToolUseBlock

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for interacting with LLMs (Anthropic Claude)."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize LLM client.

        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            model: Claude model to use
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.conversation_history: List[Dict[str, Any]] = []

    def add_user_message(self, content: str) -> None:
        """Add a user message to conversation history."""
        self.conversation_history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to conversation history."""
        self.conversation_history.append({"role": "assistant", "content": content})

    def create_message(
        self,
        user_message: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
    ) -> Message:
        """
        Send a message to the LLM.

        Args:
            user_message: The user's message
            tools: Optional list of tools available to the LLM
            max_tokens: Maximum tokens in response

        Returns:
            Claude API response
        """
        # Add user message to history
        self.add_user_message(user_message)

        # Build request
        request_params = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": self.conversation_history,
        }

        if tools:
            request_params["tools"] = tools

        logger.info(f"Sending message to LLM: {user_message[:100]}...")
        response = self.client.messages.create(**request_params)
        logger.info(f"Received response from LLM: {response.stop_reason}")

        return response

    def extract_text_response(self, response: Message) -> str:
        """Extract text content from LLM response."""
        text_parts = []
        for block in response.content:
            if isinstance(block, TextBlock):
                text_parts.append(block.text)
        return "\n".join(text_parts)

    def extract_tool_calls(self, response: Message) -> List[Dict[str, Any]]:
        """
        Extract tool calls from LLM response.

        Returns:
            List of tool calls with 'name' and 'input' keys
        """
        tool_calls = []
        for block in response.content:
            if isinstance(block, ToolUseBlock):
                tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
        return tool_calls

    def add_tool_result(self, tool_use_id: str, result: str) -> None:
        """
        Add tool result to conversation history.

        Args:
            tool_use_id: ID of the tool use from the LLM response
            result: Result from the tool execution
        """
        # Add assistant message with tool use
        # Note: This should be the full assistant message including tool use
        # For simplicity, we'll handle this in the orchestrator

        # Add tool result
        self.conversation_history.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result,
                    }
                ],
            }
        )

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []
