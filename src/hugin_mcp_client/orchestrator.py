"""Orchestrator for coordinating MCP servers and LLM."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .llm_provider import LLMProvider
from .mcp_client import MCPClient
from .builtin_tools import BuiltinTools

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrates interactions between LLM and MCP servers."""

    def __init__(
        self,
        llm_client: LLMProvider,
        mcp_clients: Dict[str, MCPClient],
        max_result_length: int = 10000,  # Increased from 2000 to prevent hallucination
    ):
        """
        Initialize orchestrator.

        Args:
            llm_client: LLM provider for AI interactions
            mcp_clients: Dictionary of MCP clients (name -> client)
            max_result_length: Maximum length for tool results (longer results are compressed)
        """
        self.llm = llm_client
        self.mcp_clients = mcp_clients
        self.available_tools: List[Dict[str, Any]] = []
        self.max_result_length = max_result_length

    async def initialize(self) -> None:
        """Initialize all MCP connections and gather available tools."""
        logger.info("Initializing orchestrator...")

        # Add built-in tools first
        all_tools = []
        builtin_tool_defs = BuiltinTools.get_tool_definitions()
        all_tools.extend(builtin_tool_defs)
        logger.info(f"Registered {len(builtin_tool_defs)} built-in tools")

        # Connect to all MCP servers
        for name, client in self.mcp_clients.items():
            logger.info(f"Connecting to MCP server: {name}")
            await client.connect()

        # Gather all available tools from MCP servers
        for name, client in self.mcp_clients.items():
            tools = await client.list_tools()
            # Convert to Anthropic format and add server prefix
            for tool in client.convert_tools_for_anthropic(tools):
                # Prefix tool name with server name to avoid conflicts
                tool["name"] = f"{name}_{tool['name']}"
                tool["description"] = f"[{name}] {tool['description']}"
                all_tools.append(tool)

        self.available_tools = all_tools
        logger.info(f"Initialized with {len(self.available_tools)} tools total")

    async def cleanup(self) -> None:
        """Cleanup and disconnect from all MCP servers."""
        for name, client in self.mcp_clients.items():
            logger.info(f"Disconnecting from MCP server: {name}")
            try:
                await client.disconnect()
            except Exception as e:
                logger.debug(f"Error disconnecting from {name}: {e}")

    def _simplify_calendar_result(self, result: str) -> str:
        """
        Simplify calendar results by removing unnecessary fields and grouping by day.
        This reduces token usage and improves accuracy.

        Args:
            result: Raw calendar JSON result

        Returns:
            Simplified calendar JSON grouped by day
        """
        import json
        from datetime import datetime
        from collections import defaultdict

        try:
            data = json.loads(result)
            events = data.get("events", [])

            if not events:
                return result  # Return as-is if no events

            # Group events by day with day-of-week
            events_by_day = defaultdict(lambda: {"day_of_week": "", "events": []})

            for event in events:
                # Extract essential fields only
                start_str = event.get("start", "")
                if not start_str:
                    continue

                # Parse date (handle timezone)
                try:
                    if "T" in start_str:
                        # Has time component
                        date_part = start_str.split("T")[0]
                    else:
                        date_part = start_str

                    # Calculate day of week from date
                    date_obj = datetime.strptime(date_part, "%Y-%m-%d")
                    day_of_week = date_obj.strftime("%A")  # e.g., "Monday", "Tuesday"

                    simplified_event = {
                        "summary": event.get("summary", ""),
                        "start": start_str,
                        "end": event.get("end", ""),
                        "all_day": event.get("all_day", False),
                    }

                    # Optional fields (only if present and meaningful)
                    if event.get("location"):
                        simplified_event["location"] = event["location"]
                    if event.get("recurring"):
                        simplified_event["recurring"] = True

                    # Add event to the day
                    events_by_day[date_part]["day_of_week"] = day_of_week
                    events_by_day[date_part]["events"].append(simplified_event)

                except Exception as e:
                    logger.warning(f"Error parsing event start time '{start_str}': {e}")
                    continue

            # Build simplified response grouped by day
            simplified = {
                "events_by_day": dict(events_by_day),
                "total_events": len(events),
                "date_range": {
                    "start": data.get("query", {}).get("start_date", ""),
                    "end": data.get("query", {}).get("end_date", ""),
                }
            }

            return json.dumps(simplified, indent=2)

        except Exception as e:
            logger.error(f"Error simplifying calendar result: {e}")
            # Fall back to compression if simplification fails
            return self._compress_result(result)

    def _compress_result(self, result: str) -> str:
        """
        Compress tool results to reduce token usage.
        Uses intelligent compression that keeps 80% of content to minimize hallucination.

        Args:
            result: The tool result to compress

        Returns:
            Compressed result string
        """
        if len(result) <= self.max_result_length:
            return result

        # Keep 70% at beginning, 10% at end (was 50% + 25% - too aggressive!)
        head_length = int(self.max_result_length * 0.7)
        tail_length = int(self.max_result_length * 0.1)

        head = result[:head_length]
        tail = result[-tail_length:]

        truncated_bytes = len(result) - head_length - tail_length
        truncated_lines = result[head_length:-tail_length].count('\n')

        # Try to show a snippet of what was truncated
        middle_snippet = result[head_length:head_length + 200].strip()
        if len(middle_snippet) > 150:
            middle_snippet = middle_snippet[:150] + "..."

        compression_note = (
            f"\n\n... [COMPRESSED: Removed {truncated_bytes:,} characters ({truncated_lines} lines) "
            f"from middle of response]\n"
            f"[First truncated content: {middle_snippet}]\n"
            f"[NOTE: Important data may have been removed - ask for specific details if needed] ...\n\n"
        )

        return head + compression_note + tail

    async def process_message(self, user_message: str, max_iterations: int = 10) -> str:
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
            tool_calls = self.llm.extract_tool_calls(response)
            logger.info(f"Iteration {iteration}: Found {len(tool_calls)} tool calls")

            # Also check if there's text content
            text_content = self.llm.extract_text_response(response)
            logger.info(f"Iteration {iteration}: Text content length: {len(text_content)}")

            if tool_calls:
                logger.info("LLM requested tool use")

                # Add assistant message to history (with tool use)
                # For Anthropic, response.content is the full content
                # For Ollama, we need to add the message from response
                if hasattr(response, 'content'):
                    self.llm.conversation_history.append(
                        {"role": "assistant", "content": response.content}
                    )

                # Execute each tool call
                for tool_call in tool_calls:
                    tool_name = tool_call["name"]
                    tool_input = tool_call["input"]
                    tool_id = tool_call["id"]

                    logger.info(f"Executing tool: {tool_name}")

                    # Check if this is a built-in tool
                    if tool_name.startswith("hugin_"):
                        # Handle built-in tool
                        try:
                            result = await BuiltinTools.call_tool(tool_name, tool_input)
                            logger.info(f"Built-in tool result: {result[:100]}... (length: {len(result)})")
                        except Exception as e:
                            logger.error(f"Built-in tool call failed: {e}")
                            result = f"Error calling built-in tool: {str(e)}"

                        # Don't compress built-in tool results (usually small JSON)
                        compressed_result = result
                    else:
                        # Handle MCP server tool
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

                        # Call the tool with auto-reconnect on failure
                        try:
                            # Log calendar query parameters to debug date issues
                            if actual_tool_name == "query_calendar_events":
                                logger.info(f"Calendar query input: {tool_input}")

                            result = await mcp_client.call_tool(actual_tool_name, tool_input)
                            logger.info(f"Tool result: {result[:100]}... (length: {len(result)})")

                            # Debug: Log full calendar results to help debug hallucinations
                            if actual_tool_name == "query_calendar_events":
                                logger.info(f"Full calendar result:\n{result}")
                        except Exception as e:
                            logger.error(f"Tool call failed: {e}")

                            # Check if server is still connected
                            if not mcp_client.is_connected():
                                logger.warning(f"MCP server '{server_name}' appears disconnected. Attempting to reconnect...")
                                print(f"\n⚠️  Warning: MCP server '{server_name}' disconnected. Reconnecting...\n")

                                # Try to reconnect
                                if await mcp_client.reconnect():
                                    print(f"✅ Reconnected to '{server_name}'\n")
                                    # Retry the tool call
                                    try:
                                        result = await mcp_client.call_tool(actual_tool_name, tool_input)
                                        logger.info(f"Tool result after reconnect: {result[:100]}... (length: {len(result)})")
                                    except Exception as retry_e:
                                        result = f"Error calling tool after reconnect: {str(retry_e)}"
                                        logger.error(result)
                                else:
                                    result = f"Failed to reconnect to MCP server '{server_name}'. Tool unavailable."
                                    print(f"❌ Failed to reconnect to '{server_name}'\n")
                                    logger.error(result)
                            else:
                                result = f"Error calling tool: {str(e)}"

                        # Compress result before adding to conversation
                        # EXCEPTION: Don't compress calendar results - structured JSON loses meaning when truncated
                        if actual_tool_name == "query_calendar_events":
                            # Simplify calendar data to reduce token usage and improve accuracy
                            compressed_result = self._simplify_calendar_result(result)
                            logger.info(f"Calendar result simplified from {len(result)} to {len(compressed_result)} chars")
                        else:
                            compressed_result = self._compress_result(result)
                            if len(compressed_result) < len(result):
                                logger.info(f"Compressed result from {len(result)} to {len(compressed_result)} chars")

                        # Debug: Log what we're sending to Claude for calendar queries
                        if actual_tool_name == "query_calendar_events":
                            logger.info(f"Sending to Claude (simplified):\n{compressed_result}")

                    # Add tool result to conversation
                    self.llm.add_tool_result(tool_id, compressed_result, response)

                # Continue loop to let LLM process tool results
                continue

            else:
                # LLM is done, return final response
                final_text = self.llm.extract_text_response(response)
                self.llm.add_assistant_message(final_text)
                return final_text

        logger.warning(f"Reached maximum iterations ({max_iterations})")
        # Log the last few tool calls to help debug
        logger.warning("This might indicate a tool calling loop or a very complex task.")
        return (
            f"I've reached the maximum number of tool uses ({max_iterations} iterations). "
            "This might mean:\n"
            "1. The task is very complex and needs more steps\n"
            "2. I'm stuck in a loop calling the same tools\n"
            "3. There's an issue with the tool responses\n\n"
            "Try breaking your question into smaller parts, or check the logs for details."
        )
