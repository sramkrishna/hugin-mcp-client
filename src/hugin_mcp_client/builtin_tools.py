"""Built-in tools provided by Hugin."""

import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from html.parser import HTMLParser

logger = logging.getLogger(__name__)


class DuckDuckGoSearchParser(HTMLParser):
    """Parse DuckDuckGo HTML search results."""

    def __init__(self):
        super().__init__()
        self.results = []
        self.current_result = {}
        self.in_result = False
        self.in_title = False
        self.in_snippet = False
        self.capture_data = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        # Result container
        if tag == 'article' or (tag == 'div' and 'data-testid' in attrs_dict and 'result' in attrs_dict.get('data-testid', '')):
            self.in_result = True
            self.current_result = {}

        # Title link
        if self.in_result and tag == 'a' and 'href' in attrs_dict:
            href = attrs_dict['href']
            # DuckDuckGo wraps URLs, extract actual URL
            if href.startswith('//duckduckgo.com/l/'):
                # Extract uddg parameter which contains the actual URL
                import urllib.parse
                params = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                if 'uddg' in params:
                    href = params['uddg'][0]
            if href and not href.startswith('//duckduckgo.com'):
                self.current_result['url'] = href
                self.in_title = True
                self.capture_data = True

        # Snippet/description
        if self.in_result and tag == 'span' and attrs_dict.get('class', '').find('snippet') != -1:
            self.in_snippet = True
            self.capture_data = True

    def handle_endtag(self, tag):
        if tag == 'article' or tag == 'div':
            if self.in_result and self.current_result.get('url'):
                self.results.append(self.current_result.copy())
            self.in_result = False
            self.current_result = {}

        if tag == 'a' and self.in_title:
            self.in_title = False
            self.capture_data = False

        if tag == 'span' and self.in_snippet:
            self.in_snippet = False
            self.capture_data = False

    def handle_data(self, data):
        data = data.strip()
        if not data:
            return

        if self.capture_data:
            if self.in_title and 'title' not in self.current_result:
                self.current_result['title'] = data
            elif self.in_snippet and 'snippet' not in self.current_result:
                self.current_result['snippet'] = data


class BuiltinTools:
    """Provides built-in tools for Hugin."""

    @staticmethod
    def get_tool_definitions() -> List[Dict[str, Any]]:
        """
        Get tool definitions in Anthropic format.

        Returns:
            List of tool definitions
        """
        return [
            {
                "name": "hugin_calculate_date_range",
                "description": (
                    "Calculate start and end dates for time period descriptions. "
                    "Use this tool to convert period descriptions like 'last week', 'past 7 days', "
                    "'last 2 months' into exact date ranges. Weeks are Sunday-Saturday."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "string",
                            "description": (
                                "Time period description. Supported formats:\n"
                                "- 'today', 'yesterday'\n"
                                "- 'this week', 'last week', 'this month', 'last month'\n"
                                "- 'last N weeks', 'last N months' (e.g., 'last 2 weeks')\n"
                                "- 'past N days', 'past N weeks', 'past N months' (e.g., 'past 7 days', 'past 4 weeks')\n"
                                "- 'N weeks ago', 'N months ago' (e.g., '2 weeks ago')\n"
                                "- 'last monday', 'last tuesday', etc. (most recent occurrence)\n"
                                "- 'this monday', 'this tuesday', etc. (in current week)"
                            ),
                        },
                        "reference_date": {
                            "type": "string",
                            "description": "Optional reference date in YYYY-MM-DD format (defaults to today)",
                        },
                    },
                    "required": ["period"],
                },
            },
            {
                "name": "hugin_write_file",
                "description": (
                    "Write content to a file. Supports any text-based file format including "
                    "code files (py, js, ts, etc.), documentation (md, txt, rst), "
                    "data files (json, yaml, toml, csv, xml), and configuration files. "
                    "Can create parent directories automatically."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": (
                                "Path to the file to write (absolute or relative to current directory). "
                                "Example: '/home/user/document.txt' or 'output/data.json'"
                            ),
                        },
                        "content": {
                            "type": "string",
                            "description": "The content to write to the file",
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": "Whether to overwrite the file if it already exists (default: false)",
                        },
                        "create_dirs": {
                            "type": "boolean",
                            "description": "Whether to create parent directories if they don't exist (default: true)",
                        },
                    },
                    "required": ["file_path", "content"],
                },
            },
            {
                "name": "hugin_web_search",
                "description": (
                    "Search the web using DuckDuckGo and return a list of results. "
                    "Useful for finding information about healthcare providers, websites, "
                    "products, services, or any general web information. "
                    "Returns titles, URLs, and snippets for each result."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query (e.g., 'pediatric neurologist Boston' or 'NeuroSports clinic')",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 10, max: 20)",
                        },
                        "region": {
                            "type": "string",
                            "description": "Region code for localized results (e.g., 'us-en', 'uk-en', 'wt-wt' for global). Default: 'us-en'",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "hugin_execute_command",
                "description": (
                    "Execute a shell command or script in a safe manner. Useful for running Python scripts, "
                    "processing data, executing system commands, or any task that requires command-line execution. "
                    "Commands run in the current working directory with a 5-minute timeout. "
                    "IMPORTANT: Only use for safe, non-destructive commands. Avoid rm, dd, mkfs, or network modification commands."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": (
                                "The command to execute. Can be a shell command, script path, or command with arguments. "
                                "Examples: 'python3 script.py', 'ls -lh /path', './process_data.sh'"
                            ),
                        },
                        "working_dir": {
                            "type": "string",
                            "description": "Optional working directory for command execution (defaults to current directory)",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Maximum execution time in seconds (default: 300, max: 600)",
                        },
                    },
                    "required": ["command"],
                },
            }
        ]

    @staticmethod
    async def call_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a built-in tool.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            JSON string with tool result

        Raises:
            ValueError: If tool name is unknown
        """
        if tool_name == "hugin_calculate_date_range":
            return await BuiltinTools._calculate_date_range(arguments)
        elif tool_name == "hugin_write_file":
            return await BuiltinTools._write_file(arguments)
        elif tool_name == "hugin_web_search":
            return await BuiltinTools._web_search(arguments)
        elif tool_name == "hugin_execute_command":
            return await BuiltinTools._execute_command(arguments)
        else:
            raise ValueError(f"Unknown built-in tool: {tool_name}")

    @staticmethod
    async def _calculate_date_range(arguments: Dict[str, Any]) -> str:
        """
        Calculate date range from period description.

        Args:
            arguments: Dict with 'period' and optional 'reference_date'

        Returns:
            JSON string with start_date, end_date, and metadata
        """
        period = arguments.get("period", "").lower().strip()
        reference_date_str = arguments.get("reference_date")

        # Handle empty/missing period - default to "this week"
        if not period:
            period = "this week"
            logger.warning("Empty period provided, defaulting to 'this week'")

        # Parse reference date or use today
        if reference_date_str:
            try:
                reference_date = datetime.strptime(reference_date_str, "%Y-%m-%d")
            except ValueError:
                return json.dumps({
                    "error": f"Invalid reference_date format: {reference_date_str}. Use YYYY-MM-DD."
                })
        else:
            reference_date = datetime.now()

        logger.info(f"Calculating date range for period: '{period}' (reference: {reference_date.date()})")

        try:
            start_date, end_date, description = BuiltinTools._parse_period(period, reference_date)

            result = {
                "period": period,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "description": description,
                "reference_date": reference_date.strftime("%Y-%m-%d"),
            }

            logger.info(f"Calculated range: {result['start_date']} to {result['end_date']} ({description})")
            return json.dumps(result, indent=2)

        except ValueError as e:
            logger.error(f"Error parsing period '{period}': {e}")
            return json.dumps({
                "error": str(e),
                "period": period,
                "hint": "Try: 'today', 'yesterday', 'this week', 'last week', 'this month', 'last month', 'past 7 days', 'past 4 weeks', 'last 2 weeks', etc."
            })

    @staticmethod
    def _parse_period(period: str, reference_date: datetime) -> tuple[datetime, datetime, str]:
        """
        Parse period description into start/end dates.

        Args:
            period: Period description (e.g., "last week", "past 7 days")
            reference_date: Reference date for calculations

        Returns:
            Tuple of (start_date, end_date, human_description)

        Raises:
            ValueError: If period format is not recognized
        """
        # Helper function to get week boundaries (Sunday-Saturday)
        def get_week_start(date: datetime) -> datetime:
            """Get the Sunday that starts the week containing this date."""
            days_since_sunday = (date.weekday() + 1) % 7  # Sunday = 0
            return date - timedelta(days=days_since_sunday)

        def get_week_end(week_start: datetime) -> datetime:
            """Get the Saturday that ends this week."""
            return week_start + timedelta(days=6)

        # Helper function to get month boundaries
        def get_month_start(date: datetime) -> datetime:
            """Get the first day of the month."""
            return date.replace(day=1)

        def get_month_end(date: datetime) -> datetime:
            """Get the last day of the month."""
            if date.month == 12:
                next_month = date.replace(year=date.year + 1, month=1, day=1)
            else:
                next_month = date.replace(month=date.month + 1, day=1)
            return next_month - timedelta(days=1)

        # Strip time component from reference date
        ref_date = reference_date.replace(hour=0, minute=0, second=0, microsecond=0)

        # Day name mappings
        day_names = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }

        # Handle "last <dayname>" (most recent occurrence of that day)
        if period.startswith("last ") and any(period.endswith(day) for day in day_names.keys()):
            day_name = period.replace("last ", "").strip()
            if day_name in day_names:
                target_weekday = day_names[day_name]
                current_weekday = ref_date.weekday()

                # Calculate days back to the most recent occurrence
                # If today is Friday (4) and we want last Monday (0):
                # days_back = (4 - 0) % 7 = 4, but if 0 we need to go back 7
                days_back = (current_weekday - target_weekday) % 7
                if days_back == 0:
                    days_back = 7  # "last monday" when today is Monday = 7 days ago

                target_date = ref_date - timedelta(days=days_back)
                return target_date, target_date, f"Last {day_name.capitalize()} ({target_date.strftime('%b %d')})"

        # Handle "this <dayname>" (day in current week, Sunday-Saturday)
        if period.startswith("this ") and any(period.endswith(day) for day in day_names.keys()):
            day_name = period.replace("this ", "").strip()
            if day_name in day_names:
                target_weekday = day_names[day_name]
                week_start = get_week_start(ref_date)
                # Add days from Sunday (week_start)
                # Sunday = 6 in Python's weekday, but we want 0
                # Monday = 0 in Python's weekday
                # So: Sunday in our week is at offset 6, Monday at offset 0
                # Actually, let's convert: our day_names uses Monday=0, but we need to offset from Sunday
                # Sunday (week_start) + 0 days = Sunday
                # Sunday (week_start) + 1 day = Monday
                # Sunday (week_start) + 2 days = Tuesday
                # etc.
                if day_name == "sunday":
                    offset = 0
                else:
                    offset = target_weekday + 1  # Monday is day 0, but 1 day after Sunday

                target_date = week_start + timedelta(days=offset)
                return target_date, target_date, f"This {day_name.capitalize()} ({target_date.strftime('%b %d')})"

        # Today / Yesterday
        if period == "today":
            return ref_date, ref_date, "Today"
        elif period == "yesterday":
            yesterday = ref_date - timedelta(days=1)
            return yesterday, yesterday, "Yesterday"

        # This week / Last week
        elif period in ["this week", "this past week"]:
            week_start = get_week_start(ref_date)
            week_end = get_week_end(week_start)
            return week_start, week_end, f"This week ({week_start.strftime('%b %d')} - {week_end.strftime('%b %d')})"

        elif period == "last week":
            current_week_start = get_week_start(ref_date)
            last_week_start = current_week_start - timedelta(days=7)
            last_week_end = current_week_start - timedelta(days=1)
            return last_week_start, last_week_end, f"Last week ({last_week_start.strftime('%b %d')} - {last_week_end.strftime('%b %d')})"

        # This month / Last month
        elif period == "this month":
            month_start = get_month_start(ref_date)
            month_end = get_month_end(ref_date)
            return month_start, month_end, f"This month ({month_start.strftime('%b %Y')})"

        elif period == "last month":
            current_month_start = get_month_start(ref_date)
            last_month_end = current_month_start - timedelta(days=1)
            last_month_start = get_month_start(last_month_end)
            return last_month_start, last_month_end, f"Last month ({last_month_start.strftime('%b %Y')})"

        # "last N weeks" - multiple complete weeks
        elif period.startswith("last ") and "week" in period:
            try:
                parts = period.split()
                num_weeks = int(parts[1])
                current_week_start = get_week_start(ref_date)
                # Go back N weeks from current week start
                start_date = current_week_start - timedelta(days=7 * num_weeks)
                # End is the day before current week starts
                end_date = current_week_start - timedelta(days=1)
                return start_date, end_date, f"Last {num_weeks} weeks"
            except (ValueError, IndexError):
                raise ValueError(f"Invalid format: '{period}'. Use 'last N weeks' where N is a number.")

        # "last N months" - multiple complete months
        elif period.startswith("last ") and "month" in period:
            try:
                parts = period.split()
                num_months = int(parts[1])
                current_month_start = get_month_start(ref_date)
                # Go back N months
                # Calculate by subtracting from month
                year = ref_date.year
                month = ref_date.month - num_months
                while month <= 0:
                    month += 12
                    year -= 1
                start_date = datetime(year, month, 1)
                # End is day before current month
                end_date = current_month_start - timedelta(days=1)
                return start_date, end_date, f"Last {num_months} months"
            except (ValueError, IndexError):
                raise ValueError(f"Invalid format: '{period}'. Use 'last N months' where N is a number.")

        # "past N days" - including today
        elif period.startswith("past ") and "day" in period:
            try:
                parts = period.split()
                num_days = int(parts[1])
                # Past N days includes today
                start_date = ref_date - timedelta(days=num_days - 1)
                end_date = ref_date
                return start_date, end_date, f"Past {num_days} days"
            except (ValueError, IndexError):
                raise ValueError(f"Invalid format: '{period}'. Use 'past N days' where N is a number.")

        # "past N weeks" - including current week (rolling N weeks)
        elif period.startswith("past ") and "week" in period:
            try:
                parts = period.split()
                num_weeks = int(parts[1])
                # Past N weeks = N * 7 days back to today
                start_date = ref_date - timedelta(days=num_weeks * 7 - 1)
                end_date = ref_date
                return start_date, end_date, f"Past {num_weeks} weeks"
            except (ValueError, IndexError):
                raise ValueError(f"Invalid format: '{period}'. Use 'past N weeks' where N is a number.")

        # "past N months" - rolling N months including current date
        elif period.startswith("past ") and "month" in period:
            try:
                parts = period.split()
                num_months = int(parts[1])
                # Go back N months from current date (not month boundaries)
                # Approximate: 30 days per month
                start_date = ref_date - timedelta(days=num_months * 30)
                end_date = ref_date
                return start_date, end_date, f"Past {num_months} months (approx)"
            except (ValueError, IndexError):
                raise ValueError(f"Invalid format: '{period}'. Use 'past N months' where N is a number.")

        # "N weeks ago" - specific week N weeks back
        elif "week" in period and "ago" in period:
            try:
                parts = period.split()
                num_weeks = int(parts[0])
                current_week_start = get_week_start(ref_date)
                target_week_start = current_week_start - timedelta(days=7 * num_weeks)
                target_week_end = get_week_end(target_week_start)
                return target_week_start, target_week_end, f"{num_weeks} weeks ago"
            except (ValueError, IndexError):
                raise ValueError(f"Invalid format: '{period}'. Use 'N weeks ago' where N is a number.")

        # "N months ago" - specific month N months back
        elif "month" in period and "ago" in period:
            try:
                parts = period.split()
                num_months = int(parts[0])
                # Go back N months
                year = ref_date.year
                month = ref_date.month - num_months
                while month <= 0:
                    month += 12
                    year -= 1
                target_month_start = datetime(year, month, 1)
                target_month_end = get_month_end(target_month_start)
                return target_month_start, target_month_end, f"{num_months} months ago ({target_month_start.strftime('%b %Y')})"
            except (ValueError, IndexError):
                raise ValueError(f"Invalid format: '{period}'. Use 'N months ago' where N is a number.")

        else:
            raise ValueError(
                f"Unrecognized period format: '{period}'. "
                "Supported: today, yesterday, this week, last week, this month, last month, "
                "last N weeks, last N months, past N days, past N weeks, past N months, "
                "N weeks ago, N months ago, last monday/tuesday/etc., this monday/tuesday/etc."
            )

    @staticmethod
    async def _web_search(arguments: Dict[str, Any]) -> str:
        """
        Search the web using DuckDuckGo.

        Args:
            arguments: Dict with 'query', optional 'max_results' and 'region'

        Returns:
            JSON string with search results
        """
        query = arguments.get("query", "").strip()
        max_results = min(arguments.get("max_results", 10), 20)  # Cap at 20
        region = arguments.get("region", "us-en")

        if not query:
            return json.dumps({
                "error": "query is required",
                "results": []
            })

        try:
            # Build DuckDuckGo search URL
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}&kl={region}"

            # Create request with headers to mimic browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }

            request = Request(search_url, headers=headers)

            logger.info(f"Searching DuckDuckGo for: '{query}' (region: {region}, max: {max_results})")

            # Fetch search results
            with urlopen(request, timeout=10) as response:
                html_content = response.read().decode('utf-8')

            # Parse results - DuckDuckGo uses result divs with links containing uddg parameter
            results = []

            # Updated regex to handle current DuckDuckGo HTML structure
            # Results are in divs with classes like "result results_links results_links_deep web-result"
            result_pattern = r'<div[^>]+class="[^"]*result[^"]*"[^>]*>(.*?)</div>\s*(?=<div[^>]+class="[^"]*result|<div id=|$)'
            result_blocks = re.findall(result_pattern, html_content, re.DOTALL)

            for block in result_blocks:
                if len(results) >= max_results:
                    break

                # Extract URL with uddg parameter
                url_match = re.search(r'href="//duckduckgo\.com/l/\?[^"]*uddg=([^"&]+)', block)
                if not url_match:
                    continue

                # Decode the URL
                from urllib.parse import unquote
                url = unquote(url_match.group(1))

                # Extract title - look for link text (more flexible pattern)
                title_match = re.search(r'<a[^>]+class="[^"]*result[^"]*"[^>]*>(.+?)</a>', block, re.DOTALL)
                if title_match:
                    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                else:
                    title = "No title"

                # Extract snippet - look for snippet class or fallback to text after title
                snippet_match = re.search(r'class="[^"]*snippet[^"]*"[^>]*>(.+?)</(?:a|span)>', block, re.DOTALL)
                if snippet_match:
                    snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()
                else:
                    # Fallback: extract any text content
                    snippet_text = re.sub(r'<[^>]+>', ' ', block)
                    snippet = ' '.join(snippet_text.split())[:200]

                # Clean up HTML entities
                import html as html_lib
                title = html_lib.unescape(title)
                snippet = html_lib.unescape(snippet)

                # Remove excessive whitespace
                title = ' '.join(title.split())
                snippet = ' '.join(snippet.split())

                # Skip if we don't have meaningful content
                if not title or title == "No title":
                    continue

                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet
                })

            logger.info(f"Found {len(results)} search results for '{query}'")

            return json.dumps({
                "query": query,
                "results": results,
                "count": len(results),
                "region": region
            }, indent=2)

        except Exception as e:
            error_msg = f"Error searching web: {str(e)}"
            logger.error(error_msg)
            return json.dumps({
                "error": error_msg,
                "query": query,
                "results": [],
                "exception_type": type(e).__name__
            })

    @staticmethod
    async def _write_file(arguments: Dict[str, Any]) -> str:
        """
        Write content to a file.

        Args:
            arguments: Dict with 'file_path', 'content', optional 'overwrite' and 'create_dirs'

        Returns:
            JSON string with operation result
        """
        file_path_str = arguments.get("file_path", "").strip()
        content = arguments.get("content", "")
        overwrite = arguments.get("overwrite", False)
        create_dirs = arguments.get("create_dirs", True)

        if not file_path_str:
            return json.dumps({
                "error": "file_path is required",
                "success": False
            })

        try:
            # Convert to Path object and resolve
            file_path = Path(file_path_str).expanduser()

            # If relative path, make it relative to current working directory
            if not file_path.is_absolute():
                file_path = Path.cwd() / file_path

            # Safety check: prevent writing to sensitive system directories
            restricted_dirs = ['/etc', '/sys', '/proc', '/dev', '/boot']
            file_path_str_resolved = str(file_path.resolve())

            for restricted in restricted_dirs:
                if file_path_str_resolved.startswith(restricted):
                    return json.dumps({
                        "error": f"Cannot write to restricted system directory: {restricted}",
                        "success": False,
                        "file_path": file_path_str_resolved
                    })

            # Check if file exists
            if file_path.exists() and not overwrite:
                return json.dumps({
                    "error": f"File already exists: {file_path}. Set overwrite=true to replace it.",
                    "success": False,
                    "file_path": str(file_path),
                    "file_exists": True
                })

            # Create parent directories if needed
            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created directory: {file_path.parent}")

            # Write the file
            file_path.write_text(content, encoding='utf-8')

            # Get file info
            file_size = file_path.stat().st_size
            file_type = file_path.suffix or "no extension"

            logger.info(f"Successfully wrote file: {file_path} ({file_size} bytes)")

            return json.dumps({
                "success": True,
                "file_path": str(file_path),
                "file_size": file_size,
                "file_type": file_type,
                "message": f"Successfully wrote {file_size} bytes to {file_path.name}",
                "absolute_path": str(file_path.resolve())
            }, indent=2)

        except PermissionError as e:
            error_msg = f"Permission denied: Cannot write to {file_path_str}"
            logger.error(error_msg)
            return json.dumps({
                "error": error_msg,
                "success": False,
                "details": str(e)
            })
        except OSError as e:
            error_msg = f"OS error writing file: {str(e)}"
            logger.error(error_msg)
            return json.dumps({
                "error": error_msg,
                "success": False,
                "file_path": file_path_str
            })
        except Exception as e:
            error_msg = f"Unexpected error writing file: {str(e)}"
            logger.error(error_msg)
            return json.dumps({
                "error": error_msg,
                "success": False,
                "exception_type": type(e).__name__
            })

    @staticmethod
    async def _execute_command(arguments: Dict[str, Any]) -> str:
        """
        Execute a shell command safely.

        Args:
            arguments: Dict with 'command', optional 'working_dir' and 'timeout'

        Returns:
            JSON string with command output and return code
        """
        import subprocess
        import asyncio

        command = arguments.get("command", "").strip()
        working_dir = arguments.get("working_dir")
        timeout = min(arguments.get("timeout", 300), 600)  # Max 10 minutes

        if not command:
            return json.dumps({
                "error": "Command cannot be empty",
                "success": False
            })

        # Safety check: block dangerous commands
        dangerous_patterns = [
            'rm -rf /',
            'dd if=',
            'mkfs',
            '> /dev/',
            'chmod 777',
            'chown -R',
            'sudo rm',
            ':(){:|:&};:',  # fork bomb
        ]

        command_lower = command.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in command_lower:
                return json.dumps({
                    "error": f"Blocked dangerous command pattern: {pattern}",
                    "success": False,
                    "command": command
                })

        logger.info(f"Executing command: {command[:100]}... (working_dir: {working_dir}, timeout: {timeout}s)")

        try:
            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return json.dumps({
                    "error": f"Command timed out after {timeout} seconds",
                    "success": False,
                    "command": command,
                    "timeout": timeout
                })

            # Decode output
            stdout_str = stdout.decode('utf-8', errors='replace')
            stderr_str = stderr.decode('utf-8', errors='replace')
            return_code = process.returncode

            # Truncate very long output
            max_output_length = 50000
            if len(stdout_str) > max_output_length:
                stdout_str = stdout_str[:max_output_length] + f"\n... (truncated {len(stdout_str) - max_output_length} characters)"
            if len(stderr_str) > max_output_length:
                stderr_str = stderr_str[:max_output_length] + f"\n... (truncated {len(stderr_str) - max_output_length} characters)"

            result = {
                "success": return_code == 0,
                "return_code": return_code,
                "stdout": stdout_str,
                "stderr": stderr_str,
                "command": command,
                "working_dir": working_dir or os.getcwd()
            }

            if return_code == 0:
                logger.info(f"Command executed successfully (return code: 0)")
            else:
                logger.warning(f"Command failed with return code: {return_code}")

            return json.dumps(result, indent=2)

        except FileNotFoundError as e:
            error_msg = f"Command not found or working directory doesn't exist: {str(e)}"
            logger.error(error_msg)
            return json.dumps({
                "error": error_msg,
                "success": False,
                "command": command
            })
        except Exception as e:
            error_msg = f"Unexpected error executing command: {str(e)}"
            logger.error(error_msg)
            return json.dumps({
                "error": error_msg,
                "success": False,
                "exception_type": type(e).__name__,
                "command": command
            })
