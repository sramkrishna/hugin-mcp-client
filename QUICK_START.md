# Quick Start Guide

This guide will get you up and running with Hugin + Ratatoskr for GNOME desktop integration.

## Prerequisites

- Python 3.13
- GNOME desktop environment
- Anthropic API key (or other LLM provider)

## Setup (One-Time)

### 1. Setup Ratatoskr (MCP Server)

```bash
cd /var/home/sri/Projects/ratatoskr-mcp-server
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
deactivate
```

### 2. Setup Hugin (MCP Client)

```bash
cd /var/home/sri/Projects/hugin-mcp-client
./setup-local.sh
```

This will:
- Create a virtual environment
- Install dependencies
- Copy config.example.toml to config.toml

### 3. Configure API Key

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

Or add to your `~/.bashrc` or `~/.config/fish/config.fish`:
```bash
# For bash/zsh
echo 'export ANTHROPIC_API_KEY="your-key"' >> ~/.bashrc

# For fish
echo 'set -x ANTHROPIC_API_KEY "your-key"' >> ~/.config/fish/config.fish
```

### 4. Verify Config

Edit `/var/home/sri/Projects/hugin-mcp-client/config.toml` and ensure the ratatoskr path is correct:

```toml
[servers.ratatoskr]
command = "python3.13"
args = ["/var/home/sri/Projects/ratatoskr-mcp-server/src/ratatoskr_mcp_server/server.py"]
```

## Running Hugin

```bash
cd /var/home/sri/Projects/hugin-mcp-client
./run-local.sh
```

Or manually:
```bash
cd /var/home/sri/Projects/hugin-mcp-client
source .venv/bin/activate
export ANTHROPIC_API_KEY='your-key'
hugin
```

## Example Questions

Once running, try asking:
- "What version of GNOME am I running?"
- "What's my desktop environment?"
- "What's my GNOME Shell version?"

## Troubleshooting

**Issue: "No module named 'dbus'"**
- Solution: Make sure ratatoskr's venv has dbus-python installed
- Run: `cd ratatoskr-mcp-server && source .venv/bin/activate && pip install dbus-python pygobject`

**Issue: "Cannot connect to D-Bus"**
- Solution: Make sure you're running on the host, not in a container
- Verify: `echo $DBUS_SESSION_BUS_ADDRESS` should show a path

**Issue: "Server not found"**
- Solution: Check the path in config.toml points to the correct ratatoskr location

## Architecture

```
You → Hugin (host) → LLM (Claude) → Tool Request → Ratatoskr (host) → D-Bus → GNOME
                                                           ↓
                                       LLM Response ← Tool Result ← Ratatoskr
```

Both Hugin and Ratatoskr run on the host (not containerized) because Ratatoskr needs direct D-Bus access to query GNOME.
