# Hugin MCP Client - Setup Guide

## Overview

Hugin is an AI assistant client that connects to MCP (Model Context Protocol) servers to provide integrated functionality for GNOME desktop, memory management, and Git hosting.

## Project Structure

```
hugin-mcp-client/
├── justfile              # Build commands (just/ujust)
├── config.toml           # Configuration
├── servers/              # MCP server submodules
│   ├── ratatoskr/       # GNOME integration (email, calendar, contacts)
│   ├── muninn/          # Memory & vector database
│   └── yggdrasil/       # Git hosting (GitHub, GitLab)
└── src/                 # Hugin source code
```

## Prerequisites

- Python 3.13+ (or 3.14)
- `just` command runner (or `ujust` on Universal Blue)
- Evolution (for email/calendar - Flatpak version)
- `gh` CLI tool (for GitHub integration)
- `glab` CLI tool (for GitLab integration)

### Installing Prerequisites

```bash
# On Fedora/Universal Blue
sudo dnf install just gh glab

# Install Evolution if not present
flatpak install flathub org.gnome.Evolution
```

## Quick Start

### One-Command Setup

Set up everything (Hugin + all MCP servers):

```bash
cd /var/home/sri/Projects/hugin-mcp-client
just setup-all
```

This will:
1. Create Python virtual environments
2. Install all dependencies
3. Configure Ratatoskr (GNOME integration)
4. Configure Muninn (Memory/Vector DB)
5. Configure Yggdrasil (Git hosting)

### Run Hugin

```bash
just run
```

Or manually:

```bash
source .venv/bin/activate
hugin
```

## Individual Server Setup

If you only want to set up specific servers:

```bash
# Setup just Ratatoskr (GNOME integration)
just setup-ratatoskr

# Setup just Muninn (Memory)
just setup-muninn

# Setup just Yggdrasil (Git hosting)
just setup-yggdrasil
```

## Available Commands

Run `just` or `just --list` to see all available commands:

```bash
just setup-all        # Setup everything
just setup            # Setup Hugin only
just clean-all        # Clean all virtual environments
just run              # Run Hugin
just servers          # Show configured MCP servers
just config           # Show configuration
just submodule-status # Show git submodule status
```

## Configuration

Edit `config.toml` to configure:

- LLM provider (Anthropic, OpenAI, Ollama, OpenVINO)
- API keys
- MCP server paths
- Model parameters

### Example: Using OpenVINO for Offline Inference

```toml
[llm]
provider = "openvino"
model_path = "~/models/qwen2.5-coder-3b-openvino"
device = "GPU"  # Options: "NPU", "GPU", "CPU"
max_new_tokens = 2048
```

## MCP Servers

### Ratatoskr (GNOME Integration)

**Location:** `servers/ratatoskr/`

**Features:**
- Fast email search (190,000+ emails in <1ms)
- Read email bodies (Evolution Maildir format)
- Compose emails (xdg-open integration)
- Calendar event creation with timezone support
- Video call URL handling (Zoom, Google Meet, etc.)
- Contact management
- GNOME notifications

**Requirements:**
- Evolution configured with email accounts
- Evolution running for email body caching
- dbus-python (system D-Bus bindings)
- icalendar, python-dateutil

**Setup:**
```bash
just setup-ratatoskr
cd servers/ratatoskr && just check-evolution  # Verify Evolution setup
```

### Muninn (Memory & Knowledge)

**Location:** `servers/muninn/`

**Features:**
- Store and retrieve memories
- Semantic search using ChromaDB
- Vector embeddings with sentence-transformers
- SQLite-backed persistence

**Requirements:**
- chromadb >= 0.5.0
- sentence-transformers >= 2.2.0

**Setup:**
```bash
just setup-muninn
```

### Yggdrasil (Git Hosting)

**Location:** `servers/yggdrasil/`

**Features:**
- GitHub integration (issues, PRs, repos)
- GitLab integration (issues, MRs, projects)
- Uses `gh` and `glab` CLI tools

**Requirements:**
- `gh` CLI (GitHub)
- `glab` CLI (GitLab)
- Authenticated sessions

**Setup:**
```bash
just setup-yggdrasil
cd servers/yggdrasil && just check-tools       # Verify CLI tools
cd servers/yggdrasil && just auth-status       # Check authentication
```

## Troubleshooting

### Email Body Reading Issues

If email bodies can't be read:

1. **Start Evolution:**
   ```bash
   flatpak run org.gnome.Evolution &
   ```

2. **Enable Offline Downloads:**
   ```bash
   gsettings set org.gnome.evolution.mail send-receive-downloads-for-offline true
   ```

3. **Configure Sync Window:**
   Open Evolution → Edit → Preferences → Mail Accounts → Edit → Receiving Options
   - Set "Download messages for offline use" to 2 years (or desired window)

### Dependencies Missing

If you get import errors:

```bash
just clean-all      # Clean everything
just setup-all      # Reinstall all dependencies
```

### Git Submodules Out of Sync

```bash
just update-submodules    # Update to latest versions
just submodule-status     # Check status
```

## Development

### Running Tests

```bash
just test                           # Test Hugin
cd servers/ratatoskr && just test   # Test Ratatoskr
cd servers/muninn && just test      # Test Muninn
cd servers/yggdrasil && just test   # Test Yggdrasil
```

### Installing Dev Dependencies

```bash
just dev
```

## Demo Tonight (5:30 PM)

For the "Hacking AI Agents PDX" event:

1. **Pre-Demo Checklist:**
   ```bash
   # 1. Ensure Evolution is running
   flatpak run org.gnome.Evolution &

   # 2. Verify all servers are set up
   just setup-all

   # 3. Test Hugin startup
   just run
   ```

2. **Demo Workflow:**
   - Query Cynthia's networking circle emails
   - Extract event details from email bodies
   - Create calendar event with correct timezone
   - Zoom link automatically appears in location field

3. **OpenVINO Demo (Optional):**
   - Show local NPU/GPU inference
   - ~4.4 tokens/sec on GPU
   - No internet required

## Additional Resources

- [MCP Protocol](https://modelcontextprotocol.io/)
- [Evolution Email Client](https://wiki.gnome.org/Apps/Evolution)
- [Intel OpenVINO](https://docs.openvino.ai/)
