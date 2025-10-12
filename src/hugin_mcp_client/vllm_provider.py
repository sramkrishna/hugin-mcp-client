"""Native vLLM provider for in-process inference."""

import json
import logging
from typing import Any, Dict, List, Optional

from .llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class VLLMProvider(LLMProvider):
    """Provider for vLLM in-process inference (no server needed)."""

    def __init__(
        self,
        model: str,
        tensor_parallel_size: int = 1,
        max_model_len: Optional[int] = None,
        gpu_memory_utilization: float = 0.9,
    ):
        """
        Initialize vLLM provider.

        Args:
            model: Model name or path (e.g., 'meta-llama/Meta-Llama-3.1-8B-Instruct')
            tensor_parallel_size: Number of GPUs to use (default 1)
            max_model_len: Maximum model context length (auto-detected if None)
            gpu_memory_utilization: Fraction of GPU memory to use (0.0-1.0)
        """
        super().__init__()

        try:
            from vllm import LLM, SamplingParams
            self.SamplingParams = SamplingParams
        except ImportError:
            raise ImportError(
                "vLLM is not installed. Install it with: pip install vllm"
            )

        logger.info(f"Loading vLLM model: {model}")
        self.model_name = model
        self.llm = LLM(
            model=model,
            tensor_parallel_size=tensor_parallel_size,
            max_model_len=max_model_len,
            gpu_memory_utilization=gpu_memory_utilization,
            trust_remote_code=True,
        )
        logger.info(f"vLLM model loaded successfully")

    def _format_tools_for_prompt(self, tools: List[Dict[str, Any]]) -> str:
        """Format tools as text for the prompt."""
        if not tools:
            return ""

        tools_text = "\n\nYou have access to the following tools:\n\n"
        for tool in tools:
            tools_text += f"- {tool['name']}: {tool.get('description', '')}\n"
            tools_text += f"  Parameters: {json.dumps(tool.get('inputSchema', {}), indent=2)}\n\n"

        tools_text += """To use a tool, respond with a JSON object in this format:
{"tool_call": {"name": "tool_name", "arguments": {...}}}

After receiving tool results, provide your final answer in plain text."""
        return tools_text

    def _parse_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """Try to extract a tool call from the response text."""
        # Look for JSON object with tool_call
        try:
            # Try to find JSON in the text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                potential_json = text[start:end]
                parsed = json.loads(potential_json)
                if "tool_call" in parsed:
                    return parsed["tool_call"]
        except json.JSONDecodeError:
            pass

        return None

    def create_message(
        self,
        user_message: str,
        tools: List[Dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        Generate a response using vLLM.

        Args:
            user_message: The user's message
            tools: Optional list of tools available to the LLM
            max_tokens: Maximum tokens in response

        Returns:
            Dict with 'text' and optionally 'tool_call'
        """
        # Add user message to history
        if user_message:
            self.add_user_message(user_message)

        # Build prompt from conversation history
        prompt = ""
        for msg in self.conversation_history:
            role = msg["role"]
            content = msg.get("content", "")

            if role == "user":
                prompt += f"User: {content}\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n"

        # Add tools to prompt if provided
        if tools:
            tools_text = self._format_tools_for_prompt(tools)
            # Insert tools before the last user message
            parts = prompt.rsplit("User:", 1)
            if len(parts) == 2:
                prompt = parts[0] + tools_text + "\n\nUser:" + parts[1]

        prompt += "Assistant: "

        logger.info(f"Generating response with vLLM (max_tokens={max_tokens})")

        # Generate response
        sampling_params = self.SamplingParams(
            max_tokens=max_tokens,
            temperature=0.7,
            top_p=0.9,
        )

        outputs = self.llm.generate([prompt], sampling_params)
        text = outputs[0].outputs[0].text.strip()

        logger.info(f"Generated response ({len(text)} chars)")

        # Check if response contains a tool call
        tool_call = self._parse_tool_call(text) if tools else None

        return {
            "text": text,
            "tool_call": tool_call,
        }

    def extract_text_response(self, response: Dict[str, Any]) -> str:
        """Extract text content from vLLM response."""
        text = response.get("text", "")

        # If there's a tool call, remove it from the text
        if response.get("tool_call"):
            # Remove JSON from text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[:start] + text[end:]

        return text.strip()

    def extract_tool_calls(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract tool calls from vLLM response.

        Returns:
            List of tool calls with 'id', 'name', and 'input' keys
        """
        tool_call = response.get("tool_call")
        if not tool_call:
            return []

        return [
            {
                "id": "call_0",
                "name": tool_call.get("name", ""),
                "input": tool_call.get("arguments", {}),
            }
        ]

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
        # Add the assistant's message with tool call
        if response.get("tool_call"):
            self.conversation_history.append(
                {
                    "role": "assistant",
                    "content": f"Using tool: {json.dumps(response['tool_call'])}",
                }
            )

        # Add the tool result as a user message
        self.conversation_history.append(
            {
                "role": "user",
                "content": f"Tool result: {result}",
            }
        )
        logger.debug("Added tool result to conversation history")
