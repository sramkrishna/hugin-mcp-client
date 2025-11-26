# Hugin MCP Client

A Python client for connecting LLMs (Large Language Models) with MCP (Model Context Protocol) servers, enabling AI assistants to interact with system resources and tools.

Named after Hugin, one of Odin's ravens in Norse mythology who flies around the world gathering information and bringing it back. Just as Hugin gathers knowledge, this client gathers information through MCP servers and AI.

## Complete Suite

This repository includes everything you need via git submodules:

- **Hugin** (this repo): MCP client with LLM orchestration
- **[Ratatoskr](servers/ratatoskr)**: MCP server for GNOME/Evolution integration
  - Evolution email search and analysis (instant SQLite indexing)
  - Contact management
  - Calendar integration (Evolution Data Server)
  - Planify task management
  - File operations with D-Bus (search, move, copy, trash)
  - Document content extraction (PDF, images, Office docs)
  - Network detection and WiFi scanning
  - On-device image analysis with face recognition
  - Markdown to PDF conversion
- **[Muninn](servers/muninn)**: Privacy-first memory storage with semantic search
  - Log interactions, events, and context
  - Semantic search across memory history
  - CalGator event storage (tech meetups, conferences)
  - Local-only storage with full-text search
- **[Yggdrasil](servers/yggdrasil)**: Git hosting platform integration
  - GitLab integration (issues, merge requests, projects)
  - Read-only mode by default for safety
  - glab CLI integration

## Features

### Core Capabilities
- **Multi-LLM Support**: Anthropic Claude (Sonnet 4.5), vLLM, Ollama, OpenAI-compatible servers, OpenVINO
- **MCP Protocol**: Connect to any MCP-compliant server with automatic tool discovery
- **Tool Orchestration**: Intelligent routing of tool calls to appropriate MCP servers
- **Interactive CLI**: Rich terminal UI with formatted output and copy-paste mode (`--no-frame`)
- **Conversation Management**: Token-aware history pruning to prevent context overflow
- **Extensible**: Easy to add support for new LLM providers and MCP servers

### Built-in Tools
- **Web Search**: DuckDuckGo integration for current information
- **File Operations**: Write files, execute commands, manage directories
- **Date Calculations**: Convert natural language time periods to exact date ranges

### Desktop Integration (via Ratatoskr)
- **Email**: Search across all accounts with instant SQLite indexing, full-text content access
- **Calendar**: Query events with attendee info, create new events, timezone-aware
- **Tasks**: Planify integration for task management and project tracking
- **Files**: Search, move, copy, trash, extract text from PDFs/images/Office docs
- **Network**: Detect network status, scan WiFi with signal strength, find AI backends
- **Vision**: On-device image analysis with face recognition and batch processing
- **System Info**: GNOME version, extensions, keybindings, app usage stats

### Memory & Context (via Muninn)
- **Semantic Search**: Find past conversations, events, and context
- **CalGator Events**: Automatic storage of tech meetups and conferences
- **Local Storage**: Privacy-first with full-text search

### Version Control (via Yggdrasil)
- **GitLab**: Issues, merge requests, projects (read-only by default)

## Architecture

```
User Input → Hugin (LLM Client) → Orchestrator → MCP Servers
                      ↓                 ↓             ↓
            Claude/vLLM/Ollama    Tool Routing   Ratatoskr (GNOME)
                                                   Muninn (Memory)
                                                   Yggdrasil (GitLab)
```

## Requirements

- Python 3.13
- Anthropic API key (for Claude) or Ollama (for local models)
- Git (for submodules)
- just (command runner) - optional but recommended

### MCP Server Dependencies

- **Ratatoskr** (GNOME integration): `poppler-utils`, `tesseract` (for PDF OCR)
- **Yggdrasil** (Git hosting): `glab` (GitLab CLI) for GitLab integration

## Installation

```bash
# Clone with submodules
git clone --recursive https://github.com/sramkrishna/hugin-mcp-client.git
cd hugin-mcp-client

# Setup everything (Hugin + all MCP servers)
just setup-all

# Copy example configuration
cp config.example.toml config.toml

# Edit config.toml with your preferences
```

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

*Desktop & System:*
- "What version of GNOME am I running?"
- "What GNOME extensions do I have installed?"
- "Show me my most used apps"

*Email & Calendar:*
- "Search my gmail for messages about AI conferences"
- "What's on my calendar this week?"
- "Show me my upcoming tasks from Planify"

*Files & Documents:*
- "Find all PDFs in my Documents folder modified in the last week"
- "Extract text from this invoice PDF"
- "Convert this markdown file to PDF"

*Network & System:*
- "What WiFi networks are available?"
- "What's my current network status?"
- "Can you detect AI inference backends on my system?"

*Vision & Images:*
- "Analyze this screenshot and tell me what's wrong"
- "Find faces in these photos"
- "What's in this image?"

*Memory & Context:*
- "What did we discuss about the NPU last week?"
- "Find memories about CalGator events"

*Version Control:*
- "Show me my GitLab issues"
- "List merge requests assigned to me"

## Usage

### Interactive CLI

```bash
# Standard mode with rich UI
just run

# Plain output mode (easier copy-paste)
just run-plain

# Or activate venv manually
source .venv/bin/activate
hugin                # Rich UI with frames
hugin --no-frame     # Plain output
```

### Single-Prompt Mode (Non-Interactive)

```bash
# Raw output for Unix pipelines
just prompt "What's on my calendar today?" > output.md

# Formatted markdown output
just prompt-formatted "List my GitLab issues"
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

## Known Issues

### v1.0.0

**Intel NPU/GPU on Fedora 43 (Linux 6.17.8)**
- OpenVINO 2025.1.0 crashes during model compilation on Lunar Lake NPU/GPU
- Error: `ZE_RESULT_ERROR_UNKNOWN, code 0x7ffffffe`
- Both NPU and GPU affected (shared cldnn backend)
- **Workaround**: Use CPU backend or remote GPU server
- Status: Under investigation with Fedora/Intel
- See `docs/NPU_STATUS.md` for details

## License

MIT
