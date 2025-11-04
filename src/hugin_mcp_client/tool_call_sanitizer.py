"""Tool call sanitizer for normalizing responses from different LLM providers."""

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ToolCallSanitizer:
    """
    Sanitizes and normalizes tool calls from different LLM providers.

    Handles cases where:
    - Models output structured tool calls (Claude, GPT-4)
    - Models output tool calls as JSON text (Qwen, some Ollama models)
    - Models output malformed or partial tool calls
    """

    @staticmethod
    def sanitize(raw_tool_calls: List[Dict[str, Any]], text_content: str) -> List[Dict[str, Any]]:
        """
        Sanitize tool calls from any provider.

        Args:
            raw_tool_calls: Tool calls extracted by provider
            text_content: Text content from response

        Returns:
            Normalized list of tool calls with 'id', 'name', and 'input' keys
        """
        # If we already have structured tool calls, return them
        if raw_tool_calls:
            logger.debug(f"Using structured tool calls: {len(raw_tool_calls)}")
            return raw_tool_calls

        # Fallback: Parse tool calls from text content if model outputs them as JSON
        parsed_calls = ToolCallSanitizer._parse_json_from_text(text_content)
        if parsed_calls:
            logger.info(f"Sanitized {len(parsed_calls)} tool calls from text content")
            return parsed_calls

        return []

    @staticmethod
    def _parse_json_from_text(text_content: str) -> List[Dict[str, Any]]:
        """
        Parse tool calls that are embedded as JSON in text content.

        Handles formats like:
        - { "name": "tool_name", "arguments": {...} }
        - Whitespace/newlines around JSON
        - Multiple JSON objects
        """
        content = text_content.strip()

        if not content:
            return []

        # Quick check if this looks like a tool call
        if not ("{" in content and '"name"' in content and '"arguments"' in content):
            return []

        logger.debug(f"Attempting to parse tool call from text: {content[:200]}")

        try:
            # Find the JSON object boundaries
            start = content.find("{")
            end = content.rfind("}") + 1

            if start < 0 or end <= start:
                return []

            json_str = content[start:end]
            tool_call_json = json.loads(json_str)

            # Normalize different JSON formats
            # Format 1: {"name": "tool_name", "arguments": {...}}
            # Format 2: {"function_name": "tool_name", "function_arg": {...}}
            name = tool_call_json.get("name") or tool_call_json.get("function_name")
            args = tool_call_json.get("arguments") or tool_call_json.get("function_arg") or tool_call_json.get("args")

            if not name:
                logger.debug(f"JSON found but missing tool name (tried 'name', 'function_name')")
                return []

            if args is None:
                logger.debug(f"JSON found but missing arguments (tried 'arguments', 'function_arg', 'args')")
                args = {}

            logger.info(f"Parsed tool call: {name}")

            return [{
                "id": "call_0",
                "name": name,
                "input": args,
            }]

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.debug(f"Failed to parse JSON from content: {e}")
            return []
