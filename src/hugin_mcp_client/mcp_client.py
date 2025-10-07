"""MCP client for connecting to MCP servers."""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import mcp.types as types

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for interacting with MCP servers."""

    def __init__(self, server_command: str, server_args: List[str], env: Optional[Dict[str, str]] = None):
        """
        Initialize MCP client.

        Args:
            server_command: Command to run the MCP server
            server_args: Arguments to pass to the server
            env: Optional environment variables (defaults to current environment)
        """
        server_env = dict(os.environ)
        if env:
            server_env.update(env)

        self.server_params = StdioServerParameters(
            command=server_command,
            args=server_args,
            env=server_env,
        )
        self.session: Optional[ClientSession] = None
        self._client_context = None

    async def connect(self) -> None:
        """Connect to the MCP server."""
        logger.info(
            f"Connecting to MCP server: {self.server_params.command} {' '.join(self.server_params.args)}"
        )

        self._client_context = stdio_client(self.server_params)
        read, write = await self._client_context.__aenter__()
        self.session = ClientSession(read, write)
        await self.session.__aenter__()
        await self.session.initialize()

        logger.info("Connected to MCP server")

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self.session:
            await self.session.__aexit__(None, None, None)
        if self._client_context:
            await self._client_context.__aexit__(None, None, None)

        logger.info("Disconnected from MCP server")

    async def list_resources(self) -> List[types.Resource]:
        """List available resources from the server."""
        if not self.session:
            raise RuntimeError("Not connected to server")

        result = await self.session.list_resources()
        return result.resources

    async def read_resource(self, uri: str) -> str:
        """
        Read a resource from the server.

        Args:
            uri: Resource URI to read

        Returns:
            Resource content as string
        """
        if not self.session:
            raise RuntimeError("Not connected to server")

        result = await self.session.read_resource(uri)
        # Combine all content parts
        return "\n".join(content.text for content in result.contents)

    async def list_tools(self) -> List[types.Tool]:
        """List available tools from the server."""
        if not self.session:
            raise RuntimeError("Not connected to server")

        result = await self.session.list_tools()
        return result.tools

    async def call_tool(
        self, tool_name: str, arguments: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Call a tool on the server.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Tool result as string
        """
        if not self.session:
            raise RuntimeError("Not connected to server")

        result = await self.session.call_tool(tool_name, arguments or {})
        # Combine all content parts
        return "\n".join(content.text for content in result.content)

    def convert_tools_for_anthropic(self, tools: List[types.Tool]) -> List[Dict[str, Any]]:
        """
        Convert MCP tools to Anthropic tool format.

        Args:
            tools: List of MCP tools

        Returns:
            List of tools in Anthropic format
        """
        anthropic_tools = []
        for tool in tools:
            anthropic_tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                }
            )
        return anthropic_tools
