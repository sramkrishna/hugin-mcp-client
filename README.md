# Hugin MCP Client

A Python client for connecting LLMs (Large Language Models) with MCP (Model Context Protocol) servers, enabling AI assistants to interact with system resources and tools.

Named after Hugin, one of Odin's ravens in Norse mythology who flies around the world gathering information and bringing it back. Just as Hugin gathers knowledge, this client gathers information through MCP servers and AI.

## Features

- **LLM Integration**: Built-in support for Anthropic's Claude API
- **MCP Protocol**: Connect to any MCP-compliant server
- **Tool Orchestration**: Automatic tool discovery and execution
- **Interactive CLI**: Chat interface with rich terminal output
- **Extensible**: Easy to add support for new LLM providers

## Architecture

```
User Input → LLM Client → Orchestrator → MCP Servers
                 ↓             ↓              ↓
            Claude API    Tool Routing   Resources/Tools
```

## Requirements

- Python 3.9 - 3.13
- Anthropic API key
- One or more MCP servers to connect to

## Installation

```bash
pip install -e .
```

## Configuration

### Set API Key

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

### Configure MCP Servers

Edit `src/ratatoskr_client/cli.py` to add your MCP servers:

```python
mcp_clients = {
    "ratatoskr": MCPClient(
        server_command="python3.13",
        server_args=["/path/to/ratatoskr-mcp-server/src/ratatoskr_mcp_server/server.py"],
    ),
    "filesystem": MCPClient(
        server_command="mcp-server-filesystem",
        server_args=["/path/to/workspace"],
    ),
}
```

## Usage

### Interactive CLI

```bash
hugin
```

Or:

```bash
python -m hugin_mcp_client.cli
```

### Example Session

```
🦅  Hugin MCP Client

Initializing LLM client...
Connecting to MCP servers...
✓ Connected to 1 MCP server(s)
✓ Loaded 1 tool(s)

Type your questions below (Ctrl+C or 'exit' to quit)

You: What version of GNOME am I running?

╭─ 🤖 Assistant ─────────────────────────────────────╮
│ You're running GNOME Shell version 48.4 in user   │
│ mode. Your GTK version is 3.24.49.                │
╰────────────────────────────────────────────────────╯
```

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest tests/
```

### Project Structure

```
src/hugin_mcp_client/
├── __init__.py
├── cli.py              # Command-line interface
├── llm_client.py       # LLM client (Anthropic)
├── mcp_client.py       # MCP protocol client
└── orchestrator.py     # Coordinates LLM + MCP
```

## How It Works

1. **Initialization**: Connects to configured MCP servers and discovers available tools
2. **User Input**: You ask a question
3. **LLM Processing**: Claude receives your question + available tools
4. **Tool Use**: If needed, Claude requests to use tools
5. **Orchestration**: Client executes tools via MCP servers
6. **Response**: Results are sent back to Claude, which generates final answer

## Extending

### Add New LLM Provider

Create a new client in `llm_client.py`:

```python
class OpenAIClient:
    # Implement OpenAI-specific logic
    pass
```

### Add New MCP Server

In your CLI or config:

```python
mcp_clients["my_server"] = MCPClient(
    server_command="my-mcp-server",
    server_args=["--config", "config.json"],
)
```

## License

MIT
