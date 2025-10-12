"""OpenAI-compatible LLM provider for local and cloud models."""

import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """Provider for OpenAI and OpenAI-compatible APIs (LM Studio, vLLM, etc)."""

    def __init__(
        self,
        model: str = "gpt-4",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize OpenAI provider.

        Args:
            model: Model name (e.g., 'gpt-4', or local model name)
            api_key: API key (can be 'none' for local servers)
            base_url: Base URL for API (e.g., 'http://localhost:1234/v1' for LM Studio)
        """
        super().__init__()
        self.model = model

        # For local servers, api_key can be anything
        if api_key is None and base_url is not None:
            api_key = "not-needed"

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    def _convert_tools_to_openai_format(
        self, tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert MCP tools to OpenAI function calling format."""
        openai_tools = []
        for tool in tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", {}),
                },
            }
            openai_tools.append(openai_tool)
        return openai_tools

    def create_message(
        self,
        user_message: str,
        tools: List[Dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> Any:
        """
        Send a message to OpenAI API.

        Args:
            user_message: The user's message
            tools: Optional list of tools available to the LLM
            max_tokens: Maximum tokens in response

        Returns:
            OpenAI API response
        """
        # Add user message to history
        if user_message:
            self.add_user_message(user_message)

        # Build request
        request_params = {
            "model": self.model,
            "messages": self.conversation_history,
            "max_tokens": max_tokens,
        }

        # Add tools if provided
        if tools:
            request_params["tools"] = self._convert_tools_to_openai_format(tools)
            request_params["tool_choice"] = "auto"

        logger.info(f"Sending message to OpenAI API ({self.model}): {user_message[:100] if user_message else '(continuing conversation)'}...")

        try:
            response = self.client.chat.completions.create(**request_params)
            logger.info(f"Received response from OpenAI API: {response.choices[0].finish_reason}")
            return response

        except Exception as e:
            logger.error(f"Error communicating with OpenAI API: {e}")
            raise

    def extract_text_response(self, response: Any) -> str:
        """Extract text content from OpenAI response."""
        if response.choices and response.choices[0].message.content:
            return response.choices[0].message.content
        return ""

    def extract_tool_calls(self, response: Any) -> List[Dict[str, Any]]:
        """
        Extract tool calls from OpenAI response.

        Returns:
            List of tool calls with 'id', 'name', and 'input' keys
        """
        tool_calls = []
        message = response.choices[0].message

        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                import json
                tool_calls.append(
                    {
                        "id": tool_call.id,
                        "name": tool_call.function.name,
                        "input": json.loads(tool_call.function.arguments),
                    }
                )

        logger.info(f"Extracted {len(tool_calls)} tool calls from OpenAI")
        return tool_calls

    def add_tool_result(
        self, tool_use_id: str, result: str, response: Any
    ) -> None:
        """
        Add tool result to conversation history.

        Args:
            tool_use_id: ID of the tool use
            result: Result from the tool execution
            response: The full response object from the previous LLM call
        """
        # Check if we already added the assistant message
        message = response.choices[0].message

        if (not self.conversation_history or
            self.conversation_history[-1].get("role") != "assistant"):
            # Add the assistant's message with tool calls
            assistant_msg = {
                "role": "assistant",
                "content": message.content,
            }

            if hasattr(message, 'tool_calls') and message.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in message.tool_calls
                ]

            self.conversation_history.append(assistant_msg)
            logger.debug(f"Added assistant message to history")

        # Add the tool result
        self.conversation_history.append(
            {
                "role": "tool",
                "tool_call_id": tool_use_id,
                "content": result,
            }
        )
        logger.debug(f"Added tool result to history")
