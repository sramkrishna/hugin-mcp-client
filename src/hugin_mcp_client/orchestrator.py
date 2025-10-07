"""Orchestrator for coordinating MCP servers and LLM."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .llm_client import LLMClient
from .mcp_client import MCPClient

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrates interactions between LLM and MCP servers."""

    def __init__(
        self,
        llm_client: LLMClient,
        mcp_clients: Dict[str, MCPClient],
    ):
        """
        Initialize orchestrator.

        Args:
            llm_client: LLM client for AI interactions
            mcp_clients: Dictionary of MCP clients (name -> client)
        """
        self.llm = llm_client
        self.mcp_clients = mcp_clients
        self.available_tools: List[Dict[str, Any]] = []

    async def initialize(self) -> None:
        """Initialize all MCP connections and gather available tools."""
        logger.info("Initializing orchestrator...")

        # Connect to all MCP servers
        for name, client in self.mcp_clients.items():
            logger.info(f"Connecting to MCP server: {name}")
            await client.connect()

        # Gather all available tools
        all_tools = []
        for name, client in self.mcp_clients.items():
            tools = await client.list_tools()
            # Convert to Anthropic format and add server prefix
            for tool in client.convert_tools_for_anthropic(tools):
                # Prefix tool name with server name to avoid conflicts
                tool["name"] = f"{name}_{tool['name']}"
                tool["description"] = f"[{name}] {tool['description']}"
                all_tools.append(tool)

        self.available_tools = all_tools
        logger.info(f"Initialized with {len(self.available_tools)} tools")

    async def cleanup(self) -> None:
        """Cleanup and disconnect from all MCP servers."""
        for name, client in self.mcp_clients.items():
            logger.info(f"Disconnecting from MCP server: {name}")
            await client.disconnect()

    async def process_message(self, user_message: str, max_iterations: int = 5) -> str:
        """
        Process a user message with LLM and MCP tools.

        Args:
            user_message: User's input message
            max_iterations: Maximum number of tool use iterations

        Returns:
            Final response from LLM
        """
        logger.info(f"Processing message: {user_message}")

        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Iteration {iteration}/{max_iterations}")

            # Send message to LLM
            response = self.llm.create_message(
                user_message if iteration == 1 else "",
                tools=self.available_tools,
            )

            # Check if LLM wants to use tools
            if response.stop_reason == "tool_use":
                logger.info("LLM requested tool use")
                tool_calls = self.llm.extract_tool_calls(response)

                # Add assistant message to history (with tool use)
                self.llm.conversation_history.append(
                    {"role": "assistant", "content": response.content}
                )

                # Execute each tool call
                for tool_call in tool_calls:
                    tool_name = tool_call["name"]
                    tool_input = tool_call["input"]
                    tool_id = tool_call["id"]

                    logger.info(f"Executing tool: {tool_name}")

                    # Parse server name and actual tool name
                    if "_" in tool_name:
                        server_name, actual_tool_name = tool_name.split("_", 1)
                    else:
                        logger.error(f"Invalid tool name format: {tool_name}")
                        continue

                    # Find the appropriate MCP client
                    if server_name not in self.mcp_clients:
                        logger.error(f"Unknown server: {server_name}")
                        continue

                    mcp_client = self.mcp_clients[server_name]

                    # Call the tool
                    try:
                        result = await mcp_client.call_tool(actual_tool_name, tool_input)
                        logger.info(f"Tool result: {result[:100]}...")
                    except Exception as e:
                        result = f"Error calling tool: {str(e)}"
                        logger.error(result)

                    # Add tool result to conversation
                    self.llm.add_tool_result(tool_id, result)

                # Continue loop to let LLM process tool results
                continue

            elif response.stop_reason == "end_turn":
                # LLM is done, return final response
                final_text = self.llm.extract_text_response(response)
                self.llm.add_assistant_message(final_text)
                return final_text

            else:
                logger.warning(f"Unexpected stop reason: {response.stop_reason}")
                final_text = self.llm.extract_text_response(response)
                return final_text

        logger.warning(f"Reached maximum iterations ({max_iterations})")
        return "I've reached the maximum number of tool uses. Please try rephrasing your question."
