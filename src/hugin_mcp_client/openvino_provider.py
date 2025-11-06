"""OpenVINO LLM provider for local NPU/GPU inference."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class OpenVINOProvider(LLMProvider):
    """Provider for OpenVINO local LLMs with NPU acceleration."""

    def __init__(
        self,
        model_path: str,
        device: str = "NPU",
        max_new_tokens: int = 2048,
    ):
        """
        Initialize OpenVINO provider.

        Args:
            model_path: Path to OpenVINO IR model directory
            device: Device to use: "NPU", "GPU", "CPU", or "AUTO"
            max_new_tokens: Maximum tokens to generate
        """
        super().__init__()
        self.model_path = Path(model_path).expanduser()
        self.device = device
        self.max_new_tokens = max_new_tokens

        # Lazy imports to avoid loading OpenVINO unless this provider is used
        self.model = None
        self.tokenizer = None
        self.streamer = None

        logger.info(f"OpenVINO provider initialized: {model_path} on {device}")

    def _ensure_loaded(self):
        """Lazy load model and tokenizer on first use."""
        if self.model is not None:
            return

        try:
            from optimum.intel import OVModelForCausalLM
            from transformers import AutoTokenizer, TextIteratorStreamer
            from threading import Thread

            logger.info(f"Loading OpenVINO model from {self.model_path}...")
            logger.info(f"Target device: {self.device}")

            # Load and compile model for target device
            self.model = OVModelForCausalLM.from_pretrained(
                self.model_path,
                device=self.device,
                compile=True,
            )

            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)

            # Get actual device used (in case of AUTO or fallback)
            actual_device = self.model.device
            logger.info(f"✓ Model loaded and compiled for {actual_device}")

        except Exception as e:
            logger.error(f"Failed to load OpenVINO model: {e}")
            raise

    def _convert_tools_to_prompt(
        self, tools: List[Dict[str, Any]]
    ) -> str:
        """Convert MCP tools to prompt format for models without native tool support."""
        if not tools:
            return ""

        tools_desc = "\n\nYou have access to the following tools:\n\n"
        for tool in tools:
            tools_desc += f"Tool: {tool['name']}\n"
            tools_desc += f"Description: {tool.get('description', '')}\n"
            params = tool.get('inputSchema', {}).get('properties', {})
            if params:
                tools_desc += "Parameters:\n"
                for param_name, param_info in params.items():
                    param_type = param_info.get('type', 'string')
                    param_desc = param_info.get('description', '')
                    tools_desc += f"  - {param_name} ({param_type}): {param_desc}\n"
            tools_desc += "\n"

        tools_desc += (
            "To use a tool, respond with JSON in this format:\n"
            '{"tool_calls": [{"name": "tool_name", "arguments": {"param": "value"}}]}\n\n'
        )
        return tools_desc

    def create_message(
        self,
        user_message: str,
        tools: List[Dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        Send a message to OpenVINO model.

        Args:
            user_message: The user's message
            tools: Optional list of tools available to the LLM
            max_tokens: Maximum tokens in response

        Returns:
            Response in Anthropic-like format for compatibility
        """
        self._ensure_loaded()

        # Add user message to history
        self.add_user_message(user_message)

        # Build system message with tool information
        from datetime import datetime
        now = datetime.now()

        system_message = (
            f"Current date and time: {now.strftime('%A, %B %d, %Y at %I:%M %p %Z')}\n\n"
            "You are Hugin, an intelligent AI assistant with access to tools for calendar, "
            "email, memory, and external systems.\n\n"
        )

        if tools:
            system_message += self._convert_tools_to_prompt(tools)

        # Build chat prompt using Qwen format
        prompt = ""

        # Add system message
        if system_message:
            prompt += f"<|im_start|>system\n{system_message}<|im_end|>\n"

        # Add conversation history
        for msg in self.conversation_history:
            role = msg["role"]
            content = msg["content"]

            # Handle list content (from tool results)
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        tool_result = block.get("content", "")
                        if isinstance(tool_result, list):
                            tool_result = "\n".join(str(x) for x in tool_result)
                        text_parts.append(f"Tool result: {tool_result}")
                content = "\n".join(text_parts)

            prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"

        # Add assistant turn
        prompt += "<|im_start|>assistant\n"

        logger.debug(f"Generated prompt ({len(prompt)} chars)")

        # Tokenize
        inputs = self.tokenizer(prompt, return_tensors="pt")

        # Generate
        logger.info(f"Generating response (max {min(max_tokens, self.max_new_tokens)} tokens)...")
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=min(max_tokens, self.max_new_tokens),
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id,
        )

        # Decode response
        full_response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Extract only the new assistant response
        assistant_response = full_response.split("<|im_start|>assistant\n")[-1]
        if "<|im_end|>" in assistant_response:
            assistant_response = assistant_response.split("<|im_end|>")[0]

        assistant_response = assistant_response.strip()

        logger.info(f"Generated {len(assistant_response)} characters")

        # Check if response contains tool calls
        tool_calls = None
        try:
            # Try to parse as JSON tool call
            if assistant_response.startswith("{") and "tool_calls" in assistant_response:
                tool_data = json.loads(assistant_response)
                if "tool_calls" in tool_data:
                    tool_calls = tool_data["tool_calls"]
                    logger.info(f"Detected {len(tool_calls)} tool call(s)")
        except json.JSONDecodeError:
            pass

        # Build response in Anthropic format for compatibility
        response = {
            "id": f"msg_openvino_{id(self)}",
            "type": "message",
            "role": "assistant",
            "model": str(self.model_path.name),
            "content": [],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": len(inputs["input_ids"][0]),
                "output_tokens": len(outputs[0]) - len(inputs["input_ids"][0]),
            },
        }

        if tool_calls:
            # Add tool use blocks
            for tool_call in tool_calls:
                response["content"].append({
                    "type": "tool_use",
                    "id": f"toolu_{id(tool_call)}",
                    "name": tool_call["name"],
                    "input": tool_call.get("arguments", {}),
                })
            response["stop_reason"] = "tool_use"
        else:
            # Regular text response
            response["content"].append({
                "type": "text",
                "text": assistant_response,
            })

        # Add assistant response to history
        self.add_assistant_message(response["content"])

        return response

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        self._ensure_loaded()
        return len(self.tokenizer.encode(text))

    def extract_text_response(self, response: Dict[str, Any]) -> str:
        """
        Extract text content from LLM response.

        Args:
            response: Response from create_message

        Returns:
            Text content as string
        """
        text_parts = []
        for block in response.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return "\n".join(text_parts)

    def extract_tool_calls(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract tool calls from LLM response.

        Args:
            response: Response from create_message

        Returns:
            List of tool calls with 'id', 'name', and 'input' keys
        """
        tool_calls = []
        for block in response.get("content", []):
            if block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block.get("id"),
                    "name": block.get("name"),
                    "input": block.get("input", {}),
                })
        return tool_calls

    def add_tool_result(self, tool_use_id: str, result: str, response: Dict[str, Any]) -> None:
        """
        Add tool result to conversation history.

        Args:
            tool_use_id: ID of the tool use from the LLM response
            result: Result from the tool execution
            response: The full response object from the previous LLM call
        """
        # First add the assistant's tool use message if not already added
        if not self.conversation_history or self.conversation_history[-1].get("role") != "assistant":
            self.add_assistant_message(response.get("content", []))

        # Add user message with tool result
        self.conversation_history.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result,
                }
            ],
        })
