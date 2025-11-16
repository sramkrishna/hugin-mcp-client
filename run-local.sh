#!/bin/bash
# Helper script to run Hugin MCP Client locally (not containerized)
# This is recommended when using MCP servers that need D-Bus access
# Usage: ./run-local.sh

set -e

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Please run ./setup-local.sh first"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Check if config.toml exists
if [ ! -f config.toml ]; then
    echo "config.toml not found. Copying from config.example.toml..."
    cp config.example.toml config.toml
    echo "Please edit config.toml and configure your MCP servers"
    exit 1
fi

# Check if ANTHROPIC_API_KEY is set when using Anthropic provider
if grep -q '^provider = "anthropic"' config.toml; then
    if [ -z "$ANTHROPIC_API_KEY" ]; then
        echo "Error: ANTHROPIC_API_KEY environment variable is not set"
        echo "Please set it with: export ANTHROPIC_API_KEY='your-api-key'"
        echo "Or switch to a different provider (ollama, openai, vllm) in config.toml"
        exit 1
    fi
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Run hugin
echo "Starting Hugin MCP Client (local mode)..."
echo "This will have access to your D-Bus session for GNOME integration"
echo "========================================"
echo ""

export LOG_LEVEL="${LOG_LEVEL:-INFO}"
export LOG_FILE="${LOG_FILE:-logs/hugin.log}"

# Pass all command-line arguments to hugin
.venv/bin/hugin "$@"
