"""Command-line interface for Hugin MCP client."""

import asyncio
import logging
import os
import sys
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .llm_client import LLMClient
from .mcp_client import MCPClient
from .orchestrator import Orchestrator

console = Console()


async def main_async() -> None:
    """Async main function."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    console.print(Panel.fit("🦅  Hugin MCP Client", style="bold blue"))

    # Check for API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        console.print(
            "[red]Error: ANTHROPIC_API_KEY environment variable not set[/red]"
        )
        console.print(
            "Please set it with: export ANTHROPIC_API_KEY='your-api-key-here'"
        )
        sys.exit(1)

    # Initialize clients
    console.print("\n[cyan]Initializing LLM client...[/cyan]")
    llm_client = LLMClient(api_key=api_key)

    console.print("[cyan]Connecting to MCP servers...[/cyan]")

    # Configure MCP servers
    # TODO: Make this configurable via config file
    mcp_clients = {
        "ratatoskr": MCPClient(
            server_command=sys.executable,  # Use current Python (has ratatoskr-mcp-server installed)
            server_args=["-m", "ratatoskr_mcp_server.server"],
        )
    }

    # Initialize orchestrator
    orchestrator = Orchestrator(llm_client, mcp_clients)

    try:
        await orchestrator.initialize()
        console.print(
            f"[green]✓ Connected to {len(mcp_clients)} MCP server(s)[/green]"
        )
        console.print(
            f"[green]✓ Loaded {len(orchestrator.available_tools)} tool(s)[/green]\n"
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
