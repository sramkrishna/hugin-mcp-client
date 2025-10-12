"""Command-line interface for Hugin MCP client."""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import tomllib

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .llm_client import LLMClient, AnthropicProvider
from .logging_config import setup_logging
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from .mcp_client import MCPClient
from .orchestrator import Orchestrator

# vLLM is optional
try:
    from .vllm_provider import VLLMProvider
    VLLM_AVAILABLE = True
except ImportError:
    VLLM_AVAILABLE = False

console = Console()


def load_config() -> dict:
    """Load configuration from config.toml file."""
    config_path = Path.cwd() / "config.toml"

    if not config_path.exists():
        return {"servers": {}, "llm": {}}

    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        return config
    except Exception as e:
        console.print(f"[red]Error loading config.toml: {e}[/red]")
        return {"servers": {}, "llm": {}}


async def main_async() -> None:
    """Async main function."""
    # Setup logging
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE")
    setup_logging(level=log_level, log_file=log_file, enable_console=True)
    logger = logging.getLogger(__name__)
    logger.info("Starting Hugin MCP client")

    console.print(Panel.fit("🦅  Hugin MCP Client", style="bold blue"))

    # Load configuration
    config = load_config()
    llm_config = config.get("llm", {})
    server_configs = config.get("servers", {})

    # Initialize LLM provider
    console.print("\n[cyan]Initializing LLM client...[/cyan]")
    provider = llm_config.get("provider", "anthropic")

    if provider == "ollama":
        model = llm_config.get("model", "llama3.2")
        base_url = llm_config.get("base_url", "http://localhost:11434")
        llm_client = OllamaProvider(model=model, base_url=base_url)
        console.print(f"[green]Using Ollama provider with model: {model}[/green]")
    elif provider == "openai":
        model = llm_config.get("model", "gpt-4")
        api_key = llm_config.get("api_key") or os.getenv("OPENAI_API_KEY")
        base_url = llm_config.get("base_url")  # Optional, for local servers

        if not api_key and not base_url:
            console.print(
                "[red]Error: OPENAI_API_KEY not set and no base_url for local server[/red]"
            )
            sys.exit(1)

        llm_client = OpenAIProvider(model=model, api_key=api_key, base_url=base_url)
        if base_url:
            console.print(f"[green]Using OpenAI-compatible API at {base_url} with model: {model}[/green]")
        else:
            console.print(f"[green]Using OpenAI provider with model: {model}[/green]")
    elif provider == "vllm":
        if not VLLM_AVAILABLE:
            console.print("[red]vLLM is not installed. Install it with: pip install 'hugin-mcp-client[vllm]'[/red]")
            sys.exit(1)

        model = llm_config.get("model")
        if not model:
            console.print("[red]Error: 'model' is required for vLLM provider[/red]")
            sys.exit(1)

        tensor_parallel_size = llm_config.get("tensor_parallel_size", 1)
        max_model_len = llm_config.get("max_model_len")
        gpu_memory_utilization = llm_config.get("gpu_memory_utilization", 0.9)

        console.print(f"[yellow]Loading vLLM model (this may take a minute)...[/yellow]")
        llm_client = VLLMProvider(
            model=model,
            tensor_parallel_size=tensor_parallel_size,
            max_model_len=max_model_len,
            gpu_memory_utilization=gpu_memory_utilization,
        )
        console.print(f"[green]Using vLLM provider with model: {model}[/green]")
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            console.print(
                "[red]Error: ANTHROPIC_API_KEY environment variable not set[/red]"
            )
            console.print(
                "Please set it with: export ANTHROPIC_API_KEY='your-api-key-here'"
            )
            sys.exit(1)
        model = llm_config.get("model", "claude-sonnet-4-20250514")
        llm_client = AnthropicProvider(api_key=api_key, model=model)
        console.print(f"[green]Using Anthropic provider with model: {model}[/green]")
    else:
        console.print(f"[red]Unknown LLM provider: {provider}[/red]")
        sys.exit(1)

    # Load and configure MCP servers from config file
    mcp_clients = {}

    for name, server_config in server_configs.items():
        if "command" not in server_config:
            console.print(f"[yellow]Warning: Server '{name}' missing 'command', skipping[/yellow]")
            continue
        mcp_clients[name] = MCPClient(
            server_command=server_config["command"],
            server_args=server_config.get("args", []),
        )

    if mcp_clients:
        console.print("[cyan]Connecting to MCP servers...[/cyan]")

    # Initialize orchestrator
    orchestrator = Orchestrator(llm_client, mcp_clients)

    try:
        await orchestrator.initialize()
        if mcp_clients:
            console.print(
                f"[green]✓ Connected to {len(mcp_clients)} MCP server(s)[/green]"
            )
            console.print(
                f"[green]✓ Loaded {len(orchestrator.available_tools)} tool(s)[/green]\n"
            )
        else:
            console.print(
                "[yellow]No MCP servers configured. Copy config.example.toml to config.toml and edit to enable tools.[/yellow]\n"
            )

        # Interactive loop
        console.print(
            "[yellow]Type your questions below (Ctrl+C or 'exit' to quit)[/yellow]\n"
        )

        while True:
            try:
                user_input = console.input("[bold green]You:[/bold green] ")

                if user_input.lower() in ["exit", "quit", "q"]:
                    break

                if not user_input.strip():
                    continue

                console.print()

                # Process message
                response = await orchestrator.process_message(user_input)

                # Display response
                console.print(
                    Panel(
                        Markdown(response),
                        title="🤖 Assistant",
                        border_style="blue",
                    )
                )
                console.print()

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted[/yellow]")
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                logging.exception("Error processing message")

    finally:
        console.print("\n[cyan]Cleaning up...[/cyan]")
        await orchestrator.cleanup()
        console.print("[green]✓ Goodbye![/green]")


def main() -> None:
    """CLI entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
