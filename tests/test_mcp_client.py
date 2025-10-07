"""Tests for MCP client."""

import pytest

from hugin_mcp_client.mcp_client import MCPClient


def test_mcp_client_initialization():
    """Test MCP client can be initialized."""
    client = MCPClient("python", ["server.py"])
    assert client.server_params.command == "python"
    assert client.server_params.args == ["server.py"]


def test_convert_tools_for_anthropic():
    """Test tool conversion to Anthropic format."""
    from mcp.types import Tool

    client = MCPClient("python", ["server.py"])

    mcp_tools = [
        Tool(
            name="test_tool",
            description="A test tool",
            inputSchema={"type": "object", "properties": {}},
        )
    ]

    anthropic_tools = client.convert_tools_for_anthropic(mcp_tools)

    assert len(anthropic_tools) == 1
    assert anthropic_tools[0]["name"] == "test_tool"
    assert anthropic_tools[0]["description"] == "A test tool"
    assert "input_schema" in anthropic_tools[0]
