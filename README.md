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

**Quick Setup:**
```bash
./setup-local.sh
```

**Manual Setup:**
```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
```

**Note:** For MCP servers that need D-Bus access (like ratatoskr for GNOME integration), hugin must run directly on the host, not in containers.

## Configuration

1. **Copy the example configuration file:**
   ```bash
   cp config.example.toml config.toml
   ```

2. **Configure your LLM provider** in `config.toml`:

   **Option A: Anthropic (Claude) - Best tool calling**
   ```toml
   [llm]
   provider = "anthropic"
   # model = "claude-sonnet-4-20250514"  # Optional
   ```
   Then set your API key:
   ```bash
   export ANTHROPIC_API_KEY='your-api-key-here'
   ```

3. **(Optional) Configure Logging:**
   ```bash
   export LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL
   export LOG_FILE=/var/log/hugin.log  # Optional log file
   ```

   **Option B: vLLM (native in-process) - Best for local with GPU**

   No server needed! Direct Python integration:
   ```bash
   pip install 'hugin-mcp-client[vllm]'
   ```

   ```toml
   [llm]
   provider = "vllm"
   model = "meta-llama/Meta-Llama-3.1-8B-Instruct"
   tensor_parallel_size = 1  # Number of GPUs to use
   gpu_memory_utilization = 0.9
   ```

   Advantages: Fastest inference, no server overhead, excellent tool calling

   **Option C: OpenAI-compatible servers - Good for flexibility**

   Supports: LM Studio, vLLM server, llama.cpp server, LocalAI
   ```toml
   [llm]
   provider = "openai"
   model = "your-model-name"
   base_url = "http://localhost:1234/v1"
   # api_key not needed for local servers
   ```

   Example servers:
   - **LM Studio**: Download from lmstudio.ai, easiest GUI option
   - **vLLM server**: `vllm serve model-name --api-key none`
   - **llama.cpp**: `./server -m model.gguf --port 8080`

   **Option D: Ollama - Limited tool calling support**
   ```toml
   [llm]
   provider = "ollama"
   model = "mistral"  # Best for tools: mistral, llama3.2
   # base_url = "http://localhost:11434"  # Optional
   ```
   Make sure Ollama is running:
   ```bash
   systemctl start ollama  # or: ollama serve
   ```

3. **(Optional) Configure MCP Servers** in `config.toml`:
   ```toml
   # Example: Filesystem MCP server
   [servers.filesystem]
   command = "uvx"
   args = ["mcp-server-filesystem", "/path/to/workspace"]
   ```

The client will work without any MCP servers configured, but won't have access to any tools.

### Using with Ratatoskr MCP Server

Hugin can connect to the [Ratatoskr MCP Server](https://github.com/yourusername/ratatoskr-mcp-server) to access GNOME Desktop integration tools.

**Configuration:**
```toml
[servers.ratatoskr]
command = "python3.13"
args = ["/path/to/ratatoskr-mcp-server/src/ratatoskr_mcp_server/server.py"]
```

**What you can ask:**
- "What version of GNOME am I running?"
- "What's my desktop environment?"
- "What's my GNOME Shell version?"

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

Add a new section to your `config.toml`:

```toml
[servers.my_server]
command = "my-mcp-server"
args = ["--config", "config.json"]
```

## License

MIT
