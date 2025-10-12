#!/bin/bash
# Setup script for running Hugin MCP Client locally (recommended for D-Bus access)

set -e

echo "Setting up Hugin MCP Client for local execution..."
echo "=================================================="
echo ""

# Check Python version
PYTHON_VERSION=$(python3.13 --version 2>&1 | awk '{print $2}')
echo "Using Python: $PYTHON_VERSION"

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "Error: Must run from hugin-mcp-client directory"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3.13 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install hugin
echo "Installing Hugin MCP Client..."
pip install -e .

# Check for config
if [ ! -f "config.toml" ]; then
    echo ""
    echo "Creating config.toml from example..."
    cp config.example.toml config.toml
    echo ""
    echo "⚠️  Please edit config.toml to:"
    echo "   1. Set your LLM provider (anthropic/ollama/etc)"
    echo "   2. Configure your MCP servers (e.g., ratatoskr path)"
    echo ""
fi

# Create logs directory
mkdir -p logs

echo ""
echo "✅ Setup complete!"
echo ""
echo "To run Hugin MCP Client:"
echo "  1. Set your API key: export ANTHROPIC_API_KEY='your-key'"
echo "  2. Activate venv: source .venv/bin/activate"
echo "  3. Run: hugin"
echo ""
echo "Or use the provided run script:"
echo "  ./run-local.sh"
