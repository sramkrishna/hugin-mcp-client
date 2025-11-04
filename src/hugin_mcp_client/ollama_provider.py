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

        # Build system message for tool usage guidance
        from datetime import datetime
        now = datetime.now()

        system_message = (
            f"Current date: {now.strftime('%A, %B %d, %Y')}\n\n"
            "CRITICAL TOOL USAGE RULES - READ CAREFULLY:\n\n"
            "Planify Tasks (ABSOLUTE RULE - QWEN3 SPECIFIC):\n"
            "WORKFLOW FOR ANY TASK QUERY:\n"
            "1. ALWAYS call query_planify_tasks(completed=false) with NO OTHER PARAMETERS\n"
            "2. You will get ALL uncompleted tasks with their due_date fields\n"
            "3. Filter the results yourself in your response based on dates\n"
            "\n"
            "NEVER use these parameters (they cause 0 results):\n"
            "  X due_date - BROKEN for ranges, only works for exact dates\n"
            "  X has_due_date - Not needed, you'll see all tasks anyway\n"
            "\n"
            "ONLY use completed=false, that's it!\n"
            "\n"
            "Examples:\n"
            "  User: 'todos this week' → query_planify_tasks(completed=false)\n"
            "  User: 'upcoming tasks' → query_planify_tasks(completed=false)\n"
            "  User: 'overdue tasks' → query_planify_tasks(completed=false)\n"
            "  Then YOU filter by due_date in the response\n\n"
            "Calendar Events:\n"
            "- Parameter name is 'start_date' (NOT 'date')\n"
            "- For 'today': use start_date='today' to get events from midnight\n"
            "- Omitting start_date defaults to 'now' and misses earlier events\n\n"
            "Email Queries (CRITICAL - MOST IMPORTANT RULE):\n"
            "- ALWAYS call get_email_accounts FIRST to see all available accounts\n"
            "- Evolution uses account_id hashes internally, NOT email addresses\n"
            "- Map user's request to the correct email address:\n"
            "  * 'gmail' or 'personal' → sriram.ramkrishna@gmail.com (302k emails)\n"
            "  * 'open source' or 'oss' or 'ramkrishna.me' → sri@ramkrishna.me (131k emails)\n"
            "  * 'hotmail' or 'microsoft' → sribabe@hotmail.com (269 emails, Microsoft account only)\n"
            "  * Specific email like 'sriram.ramkrishna@gmail.com' → match exactly\n"
            "  * If ambiguous, ask user to clarify\n"
            "- Then pass the matched account_id to query_emails\n"
            "- DO NOT default to first account - always match the user's intent\n"
            "- Example flow:\n"
            "  User: 'emails from gmail'\n"
            "  1. Call get_email_accounts → see sriram.ramkrishna@gmail.com (account_id: 6f004791...)\n"
            "  2. Call query_emails(account_id='6f004791b4e0c360459fef2770ce1da49755fea6', limit=10)\n\n"
            "PROACTIVE EVENT AWARENESS:\n"
            "- At the start of conversations (first user message), check for recent CalGator events\n"
            "- Use search_memories tool with query='calgator event' to find recent events\n"
            "- If you find interesting events from the past few days, mention them naturally:\n"
            "  'By the way, I noticed an interesting AI conference coming up...'\n"
            "- Don't be pushy - only mention if genuinely relevant to the user's interests\n"
            "- CalGator events are stored in Muninn with event_type='calgator_event'\n"
            "- Events include: title, link, published date, and summary"
        )

        # Inject system message as first message if not already present
        messages = self.conversation_history.copy()
        if not messages or messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": system_message})
        else:
            # Update existing system message
            messages[0] = {"role": "system", "content": system_message}

        # Build request
        request_data = {
            "model": self.model,
            "messages": messages,
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

        except httpx.ConnectError as e:
            error_msg = (
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Please check that:\n"
                f"  1. Ollama is running on the remote machine\n"
                f"  2. It's configured to listen on 0.0.0.0 (not just 127.0.0.1)\n"
                f"  3. The machine is accessible on the network\n"
                f"Original error: {e}"
            )
            logger.error(error_msg)
            raise ConnectionError(error_msg) from e
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

        logger.debug(f"Extracted {len(tool_calls)} structured tool calls from Ollama")
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
