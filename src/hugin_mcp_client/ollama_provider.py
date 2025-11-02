"""Ollama LLM provider."""

import json
import logging
from typing import Any, Dict, List

import httpx

from .llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Provider for Ollama local LLMs."""

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        timeout: float = 300.0,
    ):
        """
        Initialize Ollama provider.

        Args:
            model: Ollama model to use (e.g., 'llama3.2', 'mistral', 'qwen2.5-coder')
            base_url: Base URL for Ollama API
            timeout: Request timeout in seconds (default 300s / 5min for large models)
        """
        super().__init__()
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout)

    def _convert_tools_to_ollama_format(
        self, tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert MCP tools to Ollama tool format."""
        ollama_tools = []
        for tool in tools:
            ollama_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", {}),
                },
            }
            ollama_tools.append(ollama_tool)
        return ollama_tools

    def create_message(
        self,
        user_message: str,
        tools: List[Dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        Send a message to Ollama.

        Args:
            user_message: The user's message
            tools: Optional list of tools available to the LLM
            max_tokens: Maximum tokens in response (note: not all Ollama models support this)

        Returns:
            Ollama API response
        """
        # Add user message to history
        self.add_user_message(user_message)

        # Build request
        request_data = {
            "model": self.model,
            "messages": self.conversation_history,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
            },
        }

        # Add tools if provided
        if tools:
            request_data["tools"] = self._convert_tools_to_ollama_format(tools)

        logger.info(f"Sending message to Ollama ({self.model}): {user_message[:100]}...")

        try:
            # Use longer timeout for local inference (5 minutes)
            response = self.client.post(
                f"{self.base_url}/api/chat",
                json=request_data,
                timeout=300.0,  # 5 minutes for slow CPU inference
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Received response from Ollama: {result.get('message', {}).get('role', 'unknown')}")
            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error communicating with Ollama: {e}")
            raise

    def extract_text_response(self, response: Dict[str, Any]) -> str:
        """Extract text content from Ollama response."""
        message = response.get("message", {})
        return message.get("content", "")

    def extract_tool_calls(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract tool calls from Ollama response.

        Returns:
            List of tool calls with 'id', 'name', and 'input' keys
        """
        tool_calls = []
        message = response.get("message", {})
        ollama_tool_calls = message.get("tool_calls", [])

        logger.debug(f"Ollama response message: {message}")
        logger.debug(f"Ollama tool_calls: {ollama_tool_calls}")

        for idx, tool_call in enumerate(ollama_tool_calls):
            function = tool_call.get("function", {})
            tool_calls.append(
                {
                    "id": f"call_{idx}",  # Ollama doesn't provide IDs, so we generate them
                    "name": function.get("name", ""),
                    "input": function.get("arguments", {}),
                }
            )

        logger.info(f"Extracted {len(tool_calls)} tool calls from Ollama")
        return tool_calls

    def add_tool_result(
        self, tool_use_id: str, result: str, response: Dict[str, Any]
    ) -> None:
        """
        Add tool result to conversation history.

        Args:
            tool_use_id: ID of the tool use
            result: Result from the tool execution
            response: The full response object from the previous LLM call
        """
        # Check if we already added the assistant message
        if (not self.conversation_history or
            self.conversation_history[-1].get("role") != "assistant"):
            # Add the assistant's message with tool calls
            message = response.get("message", {})
            if message and message.get("role") == "assistant":
                self.conversation_history.append(message)
                logger.debug(f"Added assistant message to history: {message}")

        # Add the tool result as a user message with the result
        # Ollama expects tool results as regular user messages containing the result
        self.conversation_history.append(
            {
                "role": "user",
                "content": f"Tool result: {result}",
            }
        )
        logger.debug(f"Added tool result to history")

    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, "client"):
            self.client.close()
