# Hugin MCP Client - justfile
# Main AI assistant client that connects to MCP servers

# Python to use (requires Python 3.13)
python := "python3.13"

# Default recipe
default:
    @just --list

# Install system dependencies (OCR tools for Ratatoskr, glab for Yggdrasil)
install-system-deps:
    @echo "📦 Installing system dependencies..."
    @if command -v dnf >/dev/null 2>&1; then \
        sudo dnf install -y poppler-utils tesseract glab; \
    elif command -v apt >/dev/null 2>&1; then \
        sudo apt install -y poppler-utils tesseract-ocr glab; \
    elif command -v pacman >/dev/null 2>&1; then \
        sudo pacman -S --noconfirm poppler tesseract gitlab-cli; \
    else \
        echo "⚠️  Unknown package manager. Please install poppler-utils, tesseract, and glab manually."; \
        exit 1; \
    fi
    @echo "✅ System dependencies installed!"

# Setup everything: system deps + Hugin + all MCP server submodules
setup-all: install-system-deps setup setup-submodules
    @echo "✅ Hugin and all MCP servers ready!"

# Setup Hugin virtual environment and install dependencies
setup:
    @echo "🔧 Setting up Hugin MCP Client..."
    @echo "Using Python: {{python}}"
    rm -rf .venv
    {{python}} -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -e .
    @echo "✅ Hugin setup complete!"
    @echo ""
    @echo "To run Hugin:"
    @echo "  just run"

# Setup all MCP server submodules
setup-submodules: setup-ratatoskr setup-muninn setup-yggdrasil
    @echo "✅ All MCP server submodules configured"

# Setup Ratatoskr (GNOME integration)
setup-ratatoskr:
    @echo "🔧 Setting up Ratatoskr MCP Server (GNOME integration)..."
    cd servers/ratatoskr && rm -rf .venv
    cd servers/ratatoskr && {{python}} -m venv .venv --system-site-packages
    cd servers/ratatoskr && .venv/bin/pip install -e . pdf2image pytesseract -q

# Setup Muninn (Memory/Vector DB)
setup-muninn:
    @echo "🔧 Setting up Muninn MCP Server (Memory)..."
    cd servers/muninn && rm -rf .venv
    cd servers/muninn && {{python}} -m venv .venv
    cd servers/muninn && .venv/bin/pip install -e .

# Setup Yggdrasil (Git hosting)
setup-yggdrasil:
    @echo "🔧 Setting up Yggdrasil MCP Server (Git hosting)..."
    cd servers/yggdrasil && rm -rf .venv
    cd servers/yggdrasil && {{python}} -m venv .venv
    cd servers/yggdrasil && .venv/bin/pip install -e .

# Clean everything
clean-all: clean clean-submodules
    @echo "✅ Everything cleaned"

# Clean Hugin virtual environment
clean:
    @echo "🧹 Cleaning Hugin virtual environment..."
    rm -rf .venv
    rm -rf *.egg-info
    rm -rf build dist
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    @echo "✅ Clean complete"

# Clean all submodules
clean-submodules:
    @echo "🧹 Cleaning MCP server submodules..."
    cd servers/ratatoskr && just clean || true
    cd servers/muninn && just clean || true
    cd servers/yggdrasil && just clean || true

# Run Hugin (local mode with MCP servers)
run:
    @echo "🦅 Starting Hugin MCP Client..."
    ./run-local.sh

# Run Hugin with a single prompt (non-interactive, for Unix pipelines)
# Example: just prompt "extract timeline from PDFs" > output.md
prompt PROMPT:
    @.venv/bin/hugin --prompt "{{PROMPT}}" --output-only 2>/dev/null

# Run tests
test:
    .venv/bin/pytest tests/ -v

# Install development dependencies
dev:
    .venv/bin/pip install -e ".[dev]"

# Show configuration
config:
    @cat config.toml

# Check which MCP servers are configured
servers:
    @echo "Configured MCP servers:"
    @grep -A 5 "\\[mcp_servers" config.toml || echo "No MCP servers configured"

# Update git submodules
update-submodules:
    @echo "Updating git submodules..."
    git submodule update --init --recursive
    git submodule update --remote

# Show status of submodules
submodule-status:
    @echo "Submodule status:"
    git submodule status
