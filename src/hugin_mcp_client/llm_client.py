"""LLM client for interacting with language models."""

import logging
from typing import Any, Dict, List, Optional

from anthropic import Anthropic
from anthropic.types import Message, TextBlock, ToolUseBlock

from .llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Provider for Anthropic Claude API."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514", enable_caching: bool = True):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            model: Claude model to use
            enable_caching: Enable prompt caching for tools (reduces costs)
        """
        super().__init__()
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.enable_caching = enable_caching
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.cache_creation_tokens = 0
        self.cache_read_tokens = 0

    def create_message(
        self,
        user_message: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
    ) -> Message:
        """
        Send a message to the LLM with retry logic and prompt caching.

        Args:
            user_message: The user's message
            tools: Optional list of tools available to the LLM
            max_tokens: Maximum tokens in response

        Returns:
            Claude API response
        """
        import time
        from datetime import datetime
        from anthropic import RateLimitError
        try:
            from anthropic import OverloadedError
        except ImportError:
            # OverloadedError doesn't exist in all versions
            OverloadedError = type('OverloadedError', (Exception,), {})

        # Add user message to history
        self.add_user_message(user_message)

        # Build system message with current date to prevent date hallucinations
        # Use local time and date only (no time) for better prompt caching
        now = datetime.now()

        system_message = (
            f"Current date: {now.strftime('%A, %B %d, %Y')}\n"
            f"Today is {now.strftime('%A')}.\n\n"
            "CRITICAL RULES - READ CAREFULLY:\n\n"
            "1. DATE CALCULATION:\n"
            "   - ALWAYS use the 'hugin_calculate_date_range' tool to convert period descriptions\n"
            "     (like 'last week', 'past 7 days', 'last 2 months') into exact date ranges\n"
            "   - This tool uses Python's datetime/timedelta for accurate calculations\n"
            "   - Weeks are Sunday-Saturday, not locale-dependent\n"
            "   - The tool handles: today, yesterday, this week, last week, this month, last month,\n"
            "     last N weeks, last N months, past N days, N weeks ago, N months ago,\n"
            "     last monday/tuesday/etc., this monday/tuesday/etc.\n"
            "   - After getting dates from the tool, use them to query calendar events\n\n"
            "   When querying calendar events:\n"
            "   - Always use ISO format from the date tool: start_date='2025-10-26', end_date='2025-11-01'\n"
            "   - Include end date completely (not midnight, but end of day)\n\n"
            "2. CALENDAR EVENTS - ABSOLUTE RULE:\n"
            "   - Calendar data is grouped by date with pre-calculated day-of-week\n"
            "   - Format: events_by_day[\"2025-10-30\"] = {\"day_of_week\": \"Thursday\", \"events\": [...]}\n"
            "   - ALWAYS use the provided 'day_of_week' field - it's calculated by Python datetime\n"
            "   - DO NOT try to calculate day-of-week yourself\n"
            "   - Each event has an exact 'start' timestamp showing the time\n"
            "   - DO NOT move events from one day to another\n"
            "   - DO NOT assume events repeat unless marked as 'recurring: true'\n"
            "   - DO NOT copy events from one day to fill in other days\n"
            "   - Report ONLY the events actually in the calendar data\n"
            "   - Each event belongs to EXACTLY the date in its 'start' field\n\n"
            "3. ANTI-HALLUCINATION:\n"
            "   - NEVER invent, guess, or assume events\n"
            "   - If a day has no events in the data, say it has no events\n"
            "   - Do not use patterns from other days to fill in gaps\n"
            "   - If unsure, ask for clarification\n\n"
            "4. TOOL USAGE PATTERNS (CRITICAL FOR CORRECT RESULTS):\n\n"
            "   Planify Tasks (ABSOLUTE RULE):\n"
            "   WORKFLOW FOR ANY TASK QUERY:\n"
            "   1. ALWAYS call query_planify_tasks(completed=false) with NO OTHER PARAMETERS\n"
            "   2. You will get ALL uncompleted tasks with their due_date fields\n"
            "   3. Filter the results yourself in your response based on dates\n"
            "   \n"
            "   NEVER use these parameters (they cause 0 results or wrong results):\n"
            "     X due_date - BROKEN for ranges, only works for exact dates\n"
            "     X has_due_date - Not needed, you'll see all tasks anyway\n"
            "   \n"
            "   ONLY use completed=false, that's it!\n"
            "   \n"
            "   Examples:\n"
            "     User: 'todos this week' → query_planify_tasks(completed=false)\n"
            "     User: 'upcoming tasks' → query_planify_tasks(completed=false)\n"
            "     User: 'overdue tasks' → query_planify_tasks(completed=false)\n"
            "     Then YOU filter by due_date in the response\n\n"
            "   Calendar Events:\n"
            "   - Parameter name is 'start_date' (NOT 'date')\n"
            "   - For 'today': use start_date='today' to get events from midnight\n"
            "   - Omitting start_date defaults to 'now' and misses earlier events\n\n"
            "   Email Queries (CRITICAL - MOST IMPORTANT RULE):\n"
            "   - ALWAYS call get_email_accounts FIRST to see all available accounts\n"
            "   - Evolution uses account_id hashes internally, NOT email addresses\n"
            "   - Map user's request to the correct email address:\n"
            "     * 'gmail' or 'personal' → sriram.ramkrishna@gmail.com (302k emails)\n"
            "     * 'open source' or 'oss' or 'ramkrishna.me' → sri@ramkrishna.me (131k emails)\n"
            "     * 'hotmail' or 'microsoft' → sribabe@hotmail.com (269 emails, Microsoft account only)\n"
            "     * Specific email like 'sriram.ramkrishna@gmail.com' → match exactly\n"
            "     * If ambiguous, ask user to clarify\n"
            "   - Then pass the matched account_id to query_emails\n"
            "   - DO NOT default to first account - always match the user's intent\n"
            "   - Example flow:\n"
            "     User: 'emails from gmail'\n"
            "     1. Call get_email_accounts → see sriram.ramkrishna@gmail.com (account_id: 6f004791...)\n"
            "     2. Call query_emails(account_id='6f004791b4e0c360459fef2770ce1da49755fea6', limit=10)\n\n"
            "5. PROACTIVE EVENT AWARENESS:\n"
            "   - At the start of conversations (first user message), check for recent CalGator events\n"
            "   - Use search_memories tool with query='calgator event' to find recent events\n"
            "   - If you find interesting events from the past few days, mention them naturally:\n"
            "     'By the way, I noticed an interesting AI conference coming up...'\n"
            "   - Don't be pushy - only mention if genuinely relevant to the user's interests\n"
            "   - CalGator events are stored in Muninn with event_type='calgator_event'\n"
            "   - Events include: title, link, published date, and summary"
        )

        # Build request
        request_params = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": self.conversation_history,
            "system": system_message,
        }

        # Add prompt caching to tools if enabled
        if tools and self.enable_caching:
            # Mark the last tool with cache_control for caching
            # This caches all tools since they're sent as a block
            tools_with_cache = tools.copy()
            if len(tools_with_cache) > 0:
                # Add cache control to the last tool
                tools_with_cache[-1] = {
                    **tools_with_cache[-1],
                    "cache_control": {"type": "ephemeral"}
                }
            request_params["tools"] = tools_with_cache
        elif tools:
            request_params["tools"] = tools

        logger.info(f"Sending message to LLM: {user_message[:100]}...")
        logger.info(f"System message: {system_message[:150]}...")

        # Retry with exponential backoff
        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(**request_params)

                # Track token usage
                usage = response.usage
                self.total_input_tokens += usage.input_tokens
                self.total_output_tokens += usage.output_tokens

                # Track cache metrics if available
                if hasattr(usage, 'cache_creation_input_tokens'):
                    self.cache_creation_tokens += usage.cache_creation_input_tokens
                if hasattr(usage, 'cache_read_input_tokens'):
                    self.cache_read_tokens += usage.cache_read_input_tokens

                logger.info(
                    f"Received response from LLM: {response.stop_reason} | "
                    f"Tokens: {usage.input_tokens} in, {usage.output_tokens} out"
                )

                return response

            except (RateLimitError, OverloadedError) as e:
                error_type = "Overloaded" if isinstance(e, OverloadedError) else "Rate limit"
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"{error_type} error, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                else:
                    logger.error(f"{error_type} error after all retries")
                    raise

    def extract_text_response(self, response: Message) -> str:
        """Extract text content from LLM response."""
        text_parts = []
        for block in response.content:
            if isinstance(block, TextBlock):
                text_parts.append(block.text)
        return "\n".join(text_parts)

    def extract_tool_calls(self, response: Message) -> List[Dict[str, Any]]:
        """
        Extract tool calls from LLM response.

        Returns:
            List of tool calls with 'name' and 'input' keys
        """
        tool_calls = []
        for block in response.content:
            if isinstance(block, ToolUseBlock):
                tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
        return tool_calls

    def add_tool_result(self, tool_use_id: str, result: str, response: Message) -> None:
        """
        Add tool result to conversation history.

        Args:
            tool_use_id: ID of the tool use from the LLM response
            result: Result from the tool execution
            response: The full response object from the previous LLM call
        """
        # Add assistant message with tool use
        # Note: This should be the full assistant message including tool use
        # For simplicity, we'll handle this in the orchestrator

        # Add tool result
        self.conversation_history.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result,
                    }
                ],
            }
        )

    def get_token_usage(self) -> Dict[str, int]:
        """
        Get token usage statistics.

        Returns:
            Dictionary with token usage metrics
        """
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cache_read_tokens": self.cache_read_tokens,
        }

    def format_token_usage(self) -> str:
        """
        Format token usage as a readable string.

        Returns:
            Formatted token usage string
        """
        usage = self.get_token_usage()
        parts = [
            f"Total: {usage['total_tokens']:,} tokens",
            f"(In: {usage['input_tokens']:,}, Out: {usage['output_tokens']:,})"
        ]

        if usage['cache_read_tokens'] > 0:
            parts.append(f"Cache hits: {usage['cache_read_tokens']:,}")
        if usage['cache_creation_tokens'] > 0:
            parts.append(f"Cache writes: {usage['cache_creation_tokens']:,}")

        return " | ".join(parts)


# Backwards compatibility alias
LLMClient = AnthropicProvider
