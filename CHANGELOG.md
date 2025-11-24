# Changelog

All notable changes to Hugin MCP Client will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-11-23

### Added

#### Core Features
- **Multi-LLM Provider Support**: Works with Claude (Anthropic), Ollama, OpenAI, vLLM, and OpenVINO
- **MCP Server Architecture**: Modular design with three specialized servers:
  - **Ratatoskr**: GNOME desktop integration (calendar, email, contacts, file manager)
  - **Muninn**: Memory/RAG system for semantic search and conversation history
  - **Yggdrasil**: Git hosting integration (GitLab read-only, GitHub planned)
- **Non-Interactive Mode**: `--prompt` flag for Unix pipeline integration (`just prompt "query"`)
- **Frame-Free Output**: `--no-frame` flag for easier copy-paste of responses
- **Git Submodules**: All MCP servers are independent repositories with their own development

#### Ratatoskr Features (GNOME Integration)
- **Calendar**: Query events, analyze meeting patterns, schedule intelligence
- **Email**: Search Evolution/Thunderbird, semantic filtering, attachment support with auto-zip
- **Contacts**: Query address book, find contact information
- **File Manager**: Nautilus integration via D-Bus for file operations
- **Vision Analysis**: Screenshot and image analysis via vision models
- **Network Detection**: WiFi scanning and NetworkManager integration via D-Bus
- **Markdown to PDF**: Convert markdown documents to PDF with auto-zip for email attachments
- **D-Bus First**: Prefers D-Bus over subprocess for better desktop integration

#### Yggdrasil Features (Git Hosting)
- **GitLab Integration**: List issues, view merge requests, query projects (read-only by default)
- **Read-Only Security**: Write operations disabled by default to prevent accidental modifications
- **glab CLI**: Uses GitLab CLI for reliable API access

#### Muninn Features (Memory/RAG)
- **Semantic Search**: Vector-based search of conversation history
- **Conversation Archive**: Store and retrieve past interactions
- **Context Aware**: Helps maintain continuity across sessions

#### Developer Experience
- **Justfile Automation**: Simple commands for common tasks (`just run`, `just prompt`, etc.)
- **System Dependencies**: Automated installation of OCR tools, glab CLI
- **Configuration**: Clean TOML-based configuration
- **Logging**: Structured logging with configurable levels
- **Error Handling**: Friendly error messages with actionable solutions

### Fixed
- **Web Search**: Updated DuckDuckGo HTML parsing for current page structure
- **Calendar Timezone**: Proper handling of timezone-aware datetime objects
- **Input Line Wrapping**: Better handling of long user inputs with prompt_toolkit
- **Current Datetime**: Added to system context for accurate date calculations

### Changed
- **Branding**: Renamed from "Odinson" to "Hugin" throughout codebase
- **Submodule Structure**: Converted servers to git submodules for independent development
- **Documentation**: Comprehensive docs for setup, usage, and MCP server development

### Security
- **GitLab Read-Only Mode**: Enforced at code level to prevent accidental writes even with valid token
- **No Credential Storage**: Uses system keyring and environment variables for API keys
- **Local Data**: All MCP server data stays local unless explicitly sent to LLM provider

### Known Issues
- **NPU Support**: Intel Lunar Lake NPU detected but not functional on Fedora 43 (driver compatibility issue)
  - CPU inference works (slow)
  - GPU inference broken (same compatibility issue)
  - Documented in `docs/NPU_STATUS.md`
  - Workaround: Use remote GPU or Claude API

### Documentation
- `README.md`: Complete setup and usage guide
- `QUICK_START.md`: Fast setup for new users
- `SETUP.md`: Detailed installation instructions
- `docs/OPENVINO_NPU_SETUP.md`: NPU configuration guide (for when drivers work)
- `docs/NPU_STATUS.md`: Current NPU compatibility status
- `docs/CONVERSATION_ARCHIVAL.md`: Conversation management
- `docs/RELEASE_PROCESS.md`: Release workflow
- `docs/CODE_EXECUTION_MODE.md`: Future token optimization planning

### Performance
- **Token Usage**: ~30k tokens for 75+ tool definitions (optimization planned)
- **Response Time**: Depends on LLM provider (Claude: ~1-2s, Ollama: ~5-10s, vLLM: ~1-3s)
- **MCP Connections**: Persistent connections to all servers for low latency

### Compatibility
- **Python**: 3.13+ required
- **Operating Systems**:
  - Linux: Full support (GNOME integration via D-Bus)
  - macOS: Core features (no GNOME integration)
  - Windows: Core features (no GNOME integration)
- **LLM Providers**:
  - Anthropic Claude: ✅ Full support
  - Ollama: ✅ Full support
  - OpenAI/Compatible APIs: ✅ Full support
  - vLLM: ✅ Full support
  - OpenVINO: ⚠️ CPU only (NPU/GPU issues on Fedora 43)

### Dependencies
- **System**: `poppler-utils`, `tesseract` (for Ratatoskr OCR), `glab` (for Yggdrasil GitLab)
- **Python**: See `pyproject.toml` for full list
- **MCP Servers**: Ratatoskr, Muninn, Yggdrasil (included as submodules)

### Installation
```bash
# Clone with submodules
git clone --recursive https://github.com/sramkrishna/hugin-mcp-client.git
cd hugin-mcp-client

# Setup everything
just setup-all

# Configure
cp config.example.toml config.toml
# Edit config.toml with your settings

# Run
just run
```

### Migration Notes
- First release - no migration needed
- Configuration uses `config.toml` in project root
- Submodules are in `servers/` directory

---

## Release Checksums

*To be added at release time*

## Contributors

- Sri Ramkrishna (@sramkrishna) - Original author and maintainer
- Claude (Anthropic) - AI pair programming assistant

---

**Full Changelog**: https://github.com/sramkrishna/hugin-mcp-client/commits/v1.0.0
