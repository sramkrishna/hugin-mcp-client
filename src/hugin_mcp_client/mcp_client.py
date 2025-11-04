"""MCP client for connecting to MCP servers."""

import asyncio
import logging
import os
import subprocess
from pathlib import Path
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

        # Set LOG_LEVEL to WARNING to suppress INFO messages from MCP servers
        # This prevents server logs from cluttering the console
        if "LOG_LEVEL" not in server_env:
            server_env["LOG_LEVEL"] = "WARNING"

        # Optional: Redirect MCP server logs to a file
        # Create logs directory if it doesn't exist
        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(exist_ok=True)
        server_env["LOG_FILE"] = str(log_dir / "mcp_servers.log")

        if env:
            server_env.update(env)

        self.server_params = StdioServerParameters(
            command=server_command,
            args=server_args,
            env=server_env,
        )
        self.session: Optional[ClientSession] = None
        self._client_context = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3

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
        try:
            if self.session:
                try:
                    await self.session.__aexit__(None, None, None)
                except (Exception, asyncio.CancelledError) as e:
                    logger.debug(f"Error closing session: {e}")
                finally:
                    self.session = None
        finally:
            if self._client_context:
                try:
                    await self._client_context.__aexit__(None, None, None)
                except (Exception, asyncio.CancelledError) as e:
                    logger.debug(f"Error closing client context: {e}")
                finally:
                    self._client_context = None

        logger.info("Disconnected from MCP server")

    def is_connected(self) -> bool:
        """Check if connected to the MCP server."""
        return self.session is not None and self._client_context is not None

    async def reconnect(self) -> bool:
        """
        Attempt to reconnect to the MCP server.

        Returns:
            True if reconnection successful, False otherwise
        """
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self._max_reconnect_attempts}) reached")
            return False

        self._reconnect_attempts += 1
        logger.warning(f"Attempting to reconnect (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})...")

        try:
            # Clean up old connection
            await self.disconnect()
            # Give the server a moment to fully shutdown
            await asyncio.sleep(1)
            # Try to reconnect
            await self.connect()
            # Reset reconnect counter on success
            self._reconnect_attempts = 0
            logger.info("Reconnection successful")
            return True
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            return False

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
