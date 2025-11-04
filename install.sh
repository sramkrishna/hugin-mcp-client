#!/bin/bash
set -e

echo "=================================="
echo "Hugin MCP Client Installation"
echo "=================================="
echo ""
echo "This will install:"
echo "  - Hugin MCP Client (main orchestrator)"
echo "  - Ratatoskr MCP Server (GNOME/Evolution integration)"
echo "  - Muninn MCP Server (CRM with semantic search)"
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Found Python $PYTHON_VERSION"

# Initialize and update submodules
echo ""
echo "==> Initializing git submodules..."
git submodule init
git submodule update --recursive

# Install Hugin
echo ""
echo "==> Installing Hugin MCP Client..."
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Install Ratatoskr
echo ""
echo "==> Installing Ratatoskr MCP Server..."
cd servers/ratatoskr
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
deactivate
cd ../..

# Install Muninn
echo ""
echo "==> Installing Muninn MCP Server..."
cd servers/muninn
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
deactivate
cd ../..

# Create example config if it doesn't exist
if [ ! -f "config.toml" ]; then
    echo ""
    echo "==> Creating config.toml from example..."
    cp config.example.toml config.toml
    echo "Please edit config.toml to configure your settings"
fi

echo ""
echo "=================================="
echo "Installation Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "  1. Edit config.toml to configure your LLM provider and MCP servers"
echo "  2. Run: source .venv/bin/activate"
echo "  3. Run: hugin"
echo ""
echo "Documentation:"
echo "  - Hugin: README.md"
echo "  - Ratatoskr: servers/ratatoskr/README.md"
echo "  - Muninn: servers/muninn/README.md"
echo ""
