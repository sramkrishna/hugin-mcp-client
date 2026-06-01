"""LLM provider factory — wraps Hugin's scattered providers into one lookup."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def create_provider(provider_name: str, config: dict[str, Any]):
    """Instantiate the correct Hugin LLM provider from config."""
    from hugin_mcp_client.llm_provider import LLMProvider

    if provider_name == "anthropic":
        from hugin_mcp_client.llm_client import AnthropicProvider
        return AnthropicProvider(
            api_key=config.get("api_key"),
            model=config.get("model", "claude-sonnet-4-20250514"),
        )

    elif provider_name == "openai":
        from hugin_mcp_client.openai_provider import OpenAIProvider
        return OpenAIProvider(
            api_key=config.get("api_key"),
            model=config.get("model", "gpt-4"),
            base_url=config.get("base_url", "https://api.openai.com/v1"),
        )

    elif provider_name == "ollama":
        from hugin_mcp_client.ollama_provider import OllamaProvider
        return OllamaProvider(
            model=config.get("model", "mistral"),
            base_url=config.get("base_url", "http://localhost:11434"),
        )

    elif provider_name == "vllm":
        from hugin_mcp_client.vllm_provider import VLLMProvider
        return VLLMProvider(
            model=config.get("model", "meta-llama/Meta-Llama-3.1-8B-Instruct"),
        )

    elif provider_name == "openvino":
        from hugin_mcp_client.openvino_provider import OpenVINOProvider
        return OpenVINOProvider()

    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
