"""Command-line interface for Hugin MCP client."""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import tomllib

from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .llm_client import LLMClient, AnthropicProvider
from .logging_config import setup_logging
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from .openvino_provider import OpenVINOProvider
from .mcp_client import MCPClient
from .orchestrator import Orchestrator

# vLLM is optional
try:
    from .vllm_provider import VLLMProvider
    VLLM_AVAILABLE = True
except ImportError:
    VLLM_AVAILABLE = False

console = Console()


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Hugin MCP Client - AI assistant with MCP server integration"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        help="Run with a single prompt (non-interactive mode)",
    )
    parser.add_argument(
        "--output-only",
        action="store_true",
        help="Output only the final response (no logging, no formatting)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=50,
        help="Maximum iterations for tool use (default: 50)",
    )
    return parser.parse_args()


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


def create_llm_provider(llm_config: dict, quiet: bool = False):
    """Create and initialize LLM provider based on configuration."""
    provider = llm_config.get("provider", "anthropic")

    if provider == "ollama":
        model = llm_config.get("model", "llama3.2")
        base_url = llm_config.get("base_url", "http://localhost:11434")
        llm_client = OllamaProvider(model=model, base_url=base_url)
        if not quiet:
            console.print(f"[green]✓ Using Ollama: {model} @ {base_url}[/green]")
    elif provider == "openai":
        model = llm_config.get("model", "gpt-4")
        api_key = llm_config.get("api_key") or os.getenv("OPENAI_API_KEY")
        base_url = llm_config.get("base_url")

        if not api_key and not base_url:
            console.print(
                "[red]Error: OPENAI_API_KEY not set and no base_url for local server[/red]"
            )
            sys.exit(1)

        llm_client = OpenAIProvider(model=model, api_key=api_key, base_url=base_url)
        if not quiet:
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

        if not quiet:
            console.print(f"[yellow]Loading vLLM model (this may take a minute)...[/yellow]")
        llm_client = VLLMProvider(
            model=model,
            tensor_parallel_size=tensor_parallel_size,
            max_model_len=max_model_len,
            gpu_memory_utilization=gpu_memory_utilization,
        )
        if not quiet:
            console.print(f"[green]Using vLLM provider with model: {model}[/green]")
    elif provider == "openvino":
        model_path = llm_config.get("model_path")
        if not model_path:
            model_path = str(Path.home() / "models" / "qwen2.5-coder-3b-openvino")

        device = llm_config.get("device", "NPU")
        max_new_tokens = llm_config.get("max_new_tokens", 2048)

        if not quiet:
            console.print(f"[yellow]Loading OpenVINO model (this may take a minute)...[/yellow]")
        llm_client = OpenVINOProvider(
            model_path=model_path,
            device=device,
            max_new_tokens=max_new_tokens,
        )
        if not quiet:
            console.print(f"[green]✓ Using OpenVINO on {device}: {Path(model_path).name}[/green]")
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
        if not quiet:
            console.print(f"[green]Using Anthropic provider with model: {model}[/green]")
    else:
        console.print(f"[red]Unknown LLM provider: {provider}[/red]")
        sys.exit(1)

    return llm_client


async def main_async() -> None:
    """Async main function (interactive mode)."""
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
    llm_client = create_llm_provider(llm_config)

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

    # Initialize orchestrator with compression settings
    max_result_length = llm_config.get("max_result_length", 10000)  # Increased default to reduce hallucination
    orchestrator = Orchestrator(llm_client, mcp_clients, max_result_length=max_result_length)

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
            "[yellow]Type your questions below\n"
            "Commands: 'exit' to quit, 'clear' to reset, 'tokens' to see usage[/yellow]\n"
        )

        # Create a prompt session for async input
        session = PromptSession(
            style=Style.from_dict({
                'prompt': '#00aa00 bold',  # Green color for prompt
            })
        )

        while True:
            try:
                # Use prompt_toolkit async for better input handling with line wrapping
                with patch_stdout():
                    user_input = await session.prompt_async("You: ")

                if user_input.lower() in ["exit", "quit", "q"]:
                    break

                if user_input.lower() in ["clear", "reset"]:
                    llm_client.clear_history()
                    console.print("[cyan]✨ Conversation history cleared[/cyan]\n")
                    continue

                if user_input.lower() in ["tokens", "usage"]:
                    if hasattr(llm_client, 'format_token_usage'):
                        usage_str = llm_client.format_token_usage()
                        console.print(f"[cyan]📊 Token Usage: {usage_str}[/cyan]\n")
                    else:
                        console.print("[yellow]Token usage not available for this provider[/yellow]\n")
                    continue

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

                # Display token usage if available (Anthropic provider)
                if hasattr(llm_client, 'format_token_usage'):
                    usage_str = llm_client.format_token_usage()
                    console.print(f"[dim]{usage_str}[/dim]")

                console.print()

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted[/yellow]")
                break
            except Exception as e:
                # Check for specific error types with friendly messages
                error_msg = str(e)
                error_type = type(e).__name__

                # DEBUG: Log the actual error before showing friendly message
                logger.error(f"Caught exception: {error_type}: {error_msg}")
                console.print(f"[dim]DEBUG - Error type: {error_type}[/dim]")
                console.print(f"[dim]DEBUG - Error message: {error_msg[:200]}[/dim]")

                if "credit balance is too low" in error_msg or "billing" in error_msg.lower():
                    console.print(
                        "\n[red]💳 Insufficient API Credits[/red]\n\n"
                        "Your Anthropic API account has run out of credits.\n\n"
                        "[cyan]Solutions:[/cyan]\n"
                        "  • Visit https://console.anthropic.com/settings/billing to add credits\n"
                        "  • Switch to a local LLM provider (edit config.toml):\n"
                        "    - Ollama (free, local)\n"
                        "    - vLLM (free, local, requires GPU)\n"
                        "    - LM Studio (free, local GUI)\n"
                    )
                elif "500" in error_msg or "internal server error" in error_msg.lower():
                    console.print(
                        "\n[yellow]⚠️  Anthropic API Internal Error[/yellow]\n\n"
                        "Anthropic's servers are experiencing internal errors (HTTP 500).\n"
                        "This is a temporary server-side issue.\n\n"
                        "[cyan]Options:[/cyan]\n"
                        "  • Wait 1-2 minutes and try again\n"
                        "  • Try a simpler query to test if the API is working\n"
                        "  • Use a local LLM (see config.toml for Ollama options)\n"
                    )
                elif "overloaded" in error_msg.lower() or "529" in error_msg:
                    console.print(
                        "\n[yellow]⚠️  Anthropic API Overloaded[/yellow]\n\n"
                        "Anthropic's servers are temporarily overloaded (high traffic).\n"
                        "This is a temporary issue on their end, not a problem with Hugin.\n\n"
                        "[cyan]Options:[/cyan]\n"
                        "  • Wait 30-60 seconds and try again\n"
                        "  • Try again - Hugin will automatically retry with exponential backoff\n"
                        "  • Use a local LLM (see config.toml for Ollama/vLLM options)\n"
                    )
                elif "rate_limit_error" in error_msg or "429" in error_msg:
                    console.print(
                        "\n[yellow]⚠️  Rate Limit Exceeded[/yellow]\n\n"
                        "The conversation has grown too large and hit the API rate limit.\n"
                        "This happens when too many tokens are sent in a short time.\n\n"
                        "[cyan]Options:[/cyan]\n"
                        "  • Wait a minute and try again\n"
                        "  • Type 'clear' to start a fresh conversation\n"
                        "  • Use a local LLM (see config.toml for Ollama/vLLM options)\n"
                    )
                elif "authentication" in error_msg.lower() or "api_key" in error_msg.lower():
                    console.print(
                        "\n[red]🔑 Authentication Error[/red]\n\n"
                        "Your API key is invalid or missing.\n\n"
                        "[cyan]Fix:[/cyan]\n"
                        "  • Set ANTHROPIC_API_KEY environment variable:\n"
                        "    export ANTHROPIC_API_KEY='your-key-here'\n"
                        "  • Or add it to config.toml (not recommended for security)\n"
                    )
                else:
                    console.print(f"[red]Error: {e}[/red]")
                    logging.exception("Error processing message")

    finally:
        console.print("\n[cyan]Cleaning up...[/cyan]")
        await orchestrator.cleanup()
        console.print("[green]✓ Goodbye![/green]")


async def main_non_interactive(args) -> None:
    """Non-interactive mode - single prompt, output to stdout."""
    # Suppress logging if --output-only
    if args.output_only:
        logging.disable(logging.CRITICAL)
    else:
        log_level = os.getenv("LOG_LEVEL", "INFO")
        log_file = os.getenv("LOG_FILE")
        setup_logging(level=log_level, log_file=log_file, enable_console=False)

    config = load_config()
    llm_config = config.get("llm", {})
    server_configs = config.get("servers", {})

    # Initialize LLM provider (quiet mode)
    llm_client = create_llm_provider(llm_config, quiet=args.output_only)

    # Initialize MCP clients
    mcp_clients = {}
    for name, server_config in server_configs.items():
        if "command" not in server_config:
            continue
        mcp_clients[name] = MCPClient(
            server_command=server_config["command"],
            server_args=server_config.get("args", []),
        )

    # Initialize orchestrator
    max_result_length = llm_config.get("max_result_length", 10000)
    orchestrator = Orchestrator(llm_client, mcp_clients, max_result_length=max_result_length)

    try:
        await orchestrator.initialize()

        # Process single prompt
        response = await orchestrator.process_message(
            args.prompt,
            max_iterations=args.max_iterations
        )

        # Output handling
        if args.output_only:
            # Raw output only - no formatting
            print(response)
        else:
            # Formatted output with Rich
            console.print(Markdown(response))
            # Show token usage
            if hasattr(llm_client, 'format_token_usage'):
                token_usage = llm_client.format_token_usage()
                console.print(f"\n[dim]{token_usage}[/dim]")

    finally:
        await orchestrator.cleanup()


def main() -> None:
    """CLI entry point."""
    args = parse_args()

    # Non-interactive mode
    if args.prompt:
        try:
            asyncio.run(main_non_interactive(args))
        except KeyboardInterrupt:
            sys.exit(1)
        return

    # Interactive mode (existing behavior)
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
