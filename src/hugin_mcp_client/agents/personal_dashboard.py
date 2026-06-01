"""
Personal Dashboard Agent — inbox intelligence + contact tracking + todo generation.

Purpose:
    Runs 2x/day (morning/evening) to pull recent email conversations,
    summarize per-thread, track new contacts, flag pending action items,
    and maintain a running context file the assistant can reference.

Design:
    - Scheduled via cron/systemd timer (not a daemon)
    - Configurable backend: ratatoskr (Evolution) or gmail (MCP servers)
    - Stateless by default; state lives in Muninn (semantic memory)
    - Falls back to flat JSON files if Muninn is unavailable
    - Output is a markdown briefing and a todo list

Configuration (config.toml):
    [dashboard]
    backend = "gmail"           # "ratatoskr" or "gmail"

    # Gmail backend requires MCP servers configured :
    [servers.gmail]
    command = "npx"
    args = ["-y", "@modelcontextprotocol/server-gmail"]

    [servers.gcal]
    command = "npx"
    args = ["-y", "@googleapis/calendar-mcp-server"]

Dependencies:
    ratatoskr MCP server (for Evolution email + calendar + Planify tasks)
    gmail MCP server      (for Gmail API — community or official)
    gcal MCP server       (for Google Calendar — official or community)
    muninn MCP server     (for persistent memory across runs)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import aiohttp
except ImportError:
    aiohttp = None  # Telegram notification won't work without it
    import warnings
    warnings.warn("aiohttp not installed. Install with: pip install aiohttp")

logger = logging.getLogger("personal_dashboard")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class EmailThread:
    """A single email conversation thread."""
    subject: str
    participants: list[str]
    latest_from: str  # who sent the most recent message
    snippet: str
    has_attachment: bool = False
    is_unread: bool = False
    date: str = ""

@dataclass
class ActionItem:
    """Something the user needs to follow up on."""
    description: str
    source: str          # e.g. "email: thread subject"
    priority: str = "medium"  # high / medium / low
    due: str = ""
    status: str = "open"

@dataclass
class ContactUpdate:
    """A person who appeared in recent conversations."""
    name: str
    email: str = ""
    context: str = ""     # what was discussed
    last_contact: str = "" # date

@dataclass
class DashboardReport:
    """Full briefing output for a single run."""
    timestamp: str
    run_type: str  # "morning" or "evening"
    threads: list[EmailThread] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    new_contacts: list[ContactUpdate] = field(default_factory=list)
    calendar_today: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

# ---------------------------------------------------------------------------
# Backend configuration
# ---------------------------------------------------------------------------

@dataclass
class DashboardConfig:
    """Dashboard backend configuration, read from config.toml."""
    backend: str = "ratatoskr"  # "ratatoskr" or "gmail"
    telegram_token: str = ""     # bot token from @BotFather
    telegram_chat_id: str = ""   # your chat ID (message the bot once to get it)
    gmail_user: str = ""         # Gmail address (used when backend="gmail")
    gmail_app_password: str = "" # Gmail App Password (no Cloud Console needed)


def load_dashboard_config() -> DashboardConfig:
    """Read dashboard configuration from Hugin's config.toml."""
    config = DashboardConfig()

    try:
        import tomllib
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "config.toml"
        )
        if not os.path.exists(config_path):
            return config

        with open(config_path, "rb") as f:
            raw = tomllib.load(f)

        dashboard_cfg = raw.get("dashboard", {})
        backend = dashboard_cfg.get("backend", "ratatoskr")
        if backend in ("ratatoskr", "gmail"):
            config.backend = backend

        config.telegram_token = dashboard_cfg.get("telegram_token", "")
        config.telegram_chat_id = dashboard_cfg.get("telegram_chat_id", "")
        config.gmail_user = dashboard_cfg.get("gmail_user", "")
        config.gmail_app_password = dashboard_cfg.get("gmail_app_password", "")

        if config.telegram_token:
            logger.info("Telegram notifications configured")
        logger.info(f"Dashboard config: backend={config.backend}")
    except Exception as e:
        logger.warning(f"Could not load dashboard config: {e}")

    return config


# ---------------------------------------------------------------------------
# Phase 1: Gather data from MCP servers
# ---------------------------------------------------------------------------

async def fetch_recent_email(
    hours: int = 24,
    backend: str = "ratatoskr",
    cfg: DashboardConfig | None = None,
) -> list[EmailThread]:
    """
    Fetch recent email from the configured backend.

    Supports:
      ratatoskr — Evolution Data Server via Ratatoskr MCP
      gmail     — Gmail IMAP (App Password, no Cloud Console needed)
    """
    if backend == "gmail" and cfg and cfg.gmail_user and cfg.gmail_app_password:
        return await _fetch_gmail_imap(cfg.gmail_user, cfg.gmail_app_password, hours)
    elif backend == "ratatoskr":
        logger.info(f"Would fetch email from last {hours}h via Ratatoskr")
    else:
        logger.info(f"No credentials for backend={backend}")

    return []


async def _fetch_gmail_imap(
    user: str,
    app_password: str,
    hours: int = 24,
) -> list[EmailThread]:
    """
    Fetch recent email via Gmail IMAP, no Cloud Console needed.
    Requires Gmail App Password (Settings → Security → App Passwords).
    """
    import imaplib
    import email as email_parser
    from email.utils import parsedate_to_datetime

    threads: list[EmailThread] = []

    try:
        logger.info(f"Connecting to Gmail IMAP as {user}")

        # Run IMAP in a thread to avoid blocking
        def _fetch():
            conn = imaplib.IMAP4_SSL("imap.gmail.com")
            conn.login(user, app_password)
            conn.select("INBOX")

            # Search for mail from the last N hours
            import time
            since = int(time.time()) - hours * 3600
            _, message_ids = conn.search(
                None, f"(SINCE {time.strftime('%d-%b-%Y', time.gmtime(since))})"
            )

            results: list[EmailThread] = []
            for mid in message_ids[0].split()[-20:]:  # last 20
                _, msg_data = conn.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                if not msg_data or not msg_data[0]:
                    continue
                raw_header = msg_data[0][1]
                msg = email_parser.message_from_bytes(raw_header)

                subject = msg.get("Subject", "(no subject)")
                from_addr = msg.get("From", "unknown")
                date_str = msg.get("Date", "")

                results.append(EmailThread(
                    subject=subject,
                    participants=[from_addr],
                    latest_from=from_addr,
                    snippet=subject,
                    date=date_str,
                ))

            conn.logout()
            return results

        threads = await asyncio.to_thread(_fetch)
        logger.info(f"Fetched {len(threads)} threads from Gmail")

    except Exception as e:
        logger.error(f"Gmail IMAP fetch failed: {e}")

    return threads


async def fetch_calendar_today(backend: str = "ratatoskr", cfg: DashboardConfig | None = None) -> list[str]:
    """
    Pull today's events from the configured backend.

    Supports:
      ratatoskr — Evolution calendar via Ratatoskr MCP
      gmail     — Google Calendar requires either:
                  - Google Calendar MCP server (needs Cloud Console OAuth)
                  - Or use Ratatoskr with Evolution connected to the same account
                  Calendar is skipped for now if only Gmail IMAP is configured.
    """
    if backend == "gmail":
        logger.info("Calendar: Gmail IMAP backend doesn't support calendar. Set up Evolution + Ratatoskr for calendar.")
    else:
        logger.info("Would fetch today's calendar via Ratatoskr")

    return []


async def fetch_tasks() -> list[str]:
    """Pull Planify tasks via Ratatoskr."""
    logger.info("Would fetch Planify tasks via Ratatoskr")
    return []


async def fetch_memory_context() -> dict[str, Any]:
    """
    Pull relevant memory from Muninn — last run's action items,
    recently contacted people, pending todos.
    """
    logger.info("Would fetch memory context via Muninn")
    return {}

# ---------------------------------------------------------------------------
# Phase 2: Summarize and extract action items
# ---------------------------------------------------------------------------

def extract_action_items(
    threads: list[EmailThread],
    prior_items: list[dict],
) -> list[ActionItem]:
    """
    Scan threads for pending requests, questions, commitments.
    Cross-reference with prior action items to carry forward unfinished ones.
    """
    items: list[ActionItem] = []

    # Carry forward unfinished prior items
    for prior in prior_items:
        if prior.get("status") == "open":
            items.append(ActionItem(
                description=prior["description"],
                source=prior.get("source", "carried forward"),
                priority=prior.get("priority", "medium"),
                status="open",
            ))

    # Scan threads for new action items
    for thread in threads:
        subject_lower = thread.subject.lower()
        snippet_lower = thread.snippet.lower()

        # Heuristic: questions, requests, "let me know", "thoughts?"
        action_triggers = [
            "let me know", "thoughts?", "what do you think",
            "can you", "could you", "please review", "need your input",
            "action item", "todo", "to do",
        ]
        for trigger in action_triggers:
            if trigger in snippet_lower or trigger in subject_lower:
                items.append(ActionItem(
                    description=thread.snippet[:200],
                    source=f"email: {thread.subject}",
                    priority="medium",
                    status="open",
                ))
                break

    return items


def extract_contacts(
    threads: list[EmailThread],
    known_contacts: dict[str, str],
) -> list[ContactUpdate]:
    """Identify new people in recent conversations."""
    new_contacts: list[ContactUpdate] = []
    seen = set(known_contacts.keys())

    for thread in threads:
        for person in thread.participants:
            if person not in seen:
                new_contacts.append(ContactUpdate(
                    name=person,
                    context=thread.subject,
                    last_contact=thread.date,
                ))
                seen.add(person)

    return new_contacts

# ---------------------------------------------------------------------------
# Phase 3: Generate briefing
# ---------------------------------------------------------------------------

def generate_briefing(
    report: DashboardReport,
    state_path: str = "",
) -> str:
    """Produce the human-readable markdown briefing."""
    lines = [
        f"# Personal Dashboard — {report.run_type.title()} Briefing",
        f"",
        f"**{report.timestamp}**",
        f"",
    ]

    # Calendar
    if report.calendar_today:
        lines.extend([
            "## 📅 Today's Schedule",
            "",
        ])
        for event in report.calendar_today:
            lines.append(f"- {event}")
        lines.append("")

    # Action items
    open_items = [a for a in report.action_items if a.status == "open"]
    if open_items:
        lines.extend([
            "## ✅ Action Items",
            "",
        ])
        for item in open_items:
            priority_mark = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            mark = priority_mark.get(item.priority, "🟡")
            lines.append(f"{mark} **{item.description}**")
            lines.append(f"   _Source: {item.source}_")
            if item.due:
                lines.append(f"   Due: {item.due}")
            lines.append("")

    # Recent email threads
    if report.threads:
        lines.extend([
            "## 📧 Recent Conversations",
            "",
        ])
        for t in report.threads[:10]:
            unread_mark = "🔵 " if t.is_unread else ""
            lines.append(f"{unread_mark}**{t.subject}** — {t.latest_from}")
            lines.append(f"   {t.snippet[:100]}...")
            lines.append("")

    # New contacts
    if report.new_contacts:
        lines.extend([
            "## 👤 New Contacts",
            "",
        ])
        for c in report.new_contacts:
            lines.append(f"- **{c.name}** — {c.context}")
        lines.append("")

    # Errors
    if report.errors:
        lines.extend([
            "## ⚠️ Notes",
            "",
        ])
        for e in report.errors:
            lines.append(f"- {e}")
        lines.append("")

    # Footer with state info
    lines.extend([
        "---",
        f"_Dashboard auto-generated. State stored at: {state_path or 'in-memory only'}_",
        f"_Next run triggers re-evaluation of all action items._",
        "",
    ])

    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Telegram notification
# ---------------------------------------------------------------------------

async def send_telegram(
    token: str,
    chat_id: str,
    briefing: str,
    report: DashboardReport,
) -> None:
    """
    Send a condensed briefing as a Telegram message.
    Falls back to sending just a summary if the full briefing is too long.
    Telegram has a 4096-char limit per message.
    """
    if not token or not chat_id:
        return

    # Build a condensed version for Telegram
    lines = [f"📋 **{report.run_type.title()} Briefing**"]

    if report.calendar_today:
        lines.append(f"\n📅 **Today**")
        for ev in report.calendar_today[:5]:
            lines.append(f"  • {ev}")

    open_items = [a for a in report.action_items if a.status == "open"]
    if open_items:
        lines.append(f"\n✅ **Action Items ({len(open_items)})**")
        for item in open_items[:8]:
            mark = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(item.priority, "🟡")
            lines.append(f"  {mark} {item.description[:120]}")

    if report.threads:
        lines.append(f"\n📧 **Recent**")
        for t in report.threads[:5]:
            lines.append(f"  • {t.subject} — {t.latest_from}")

    if report.new_contacts:
        lines.append(f"\n👤 **New contacts**")
        for c in report.new_contacts:
            lines.append(f"  • {c.name}")

    if report.errors:
        lines.append(f"\n⚠️ {len(report.errors)} error(s)")

    body = "\n".join(lines)
    body = body[:4000]  # stay under Telegram's limit

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": body,
        "parse_mode": "Markdown",
        "disable_notification": False,
    }

    if aiohttp is None:
        logger.warning("aiohttp not installed — skipping Telegram notification")
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    logger.warning(f"Telegram send failed: {resp.status} — {(await resp.text())[:200]}")
                else:
                    logger.info("Briefing sent via Telegram")
    except Exception as e:
        logger.warning(f"Telegram send error: {e}")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

STATE_DIR = Path(os.environ.get("HUGIN_STATE_DIR", os.path.expanduser("~/.hugin/state")))

async def run_dashboard(run_type: str = "morning", cfg: DashboardConfig | None = None) -> tuple[DashboardReport, DashboardConfig]:
    """
    Full pipeline: gather → summarize → brief → save state.
    Returns (report, config) so the caller can send notifications.
    """
    logger.info(f"Starting {run_type} dashboard run")

    if cfg is None:
        cfg = load_dashboard_config()

    report = DashboardReport(
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        run_type=run_type,
    )

    # Phase 1: Gather in parallel
    threads_task = fetch_recent_email(backend=cfg.backend, cfg=cfg)
    calendar_task = fetch_calendar_today(backend=cfg.backend, cfg=cfg)
    tasks_task = fetch_tasks()
    memory_task = fetch_memory_context()

    threads, calendar, _, memory = await asyncio.gather(
        threads_task, calendar_task, tasks_task, memory_task,
        return_exceptions=True,
    )

    if isinstance(threads, Exception):
        report.errors.append(f"Email fetch: {threads}")
        threads = []
    if isinstance(calendar, Exception):
        report.errors.append(f"Calendar fetch: {calendar}")
        calendar = []
    if isinstance(memory, Exception):
        memory = {}

    report.threads = threads or []
    report.calendar_today = calendar or []

    # Phase 2: Extract intelligence
    prior_items = memory.get("action_items", []) if isinstance(memory, dict) else []
    known_contacts = memory.get("contacts", {}) if isinstance(memory, dict) else {}

    report.action_items = extract_action_items(report.threads, prior_items)
    report.new_contacts = extract_contacts(report.threads, known_contacts)

    return report, cfg


def save_state(report: DashboardReport) -> str:
    """Persist current state to a JSON file for next run."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = {
        "last_run": report.timestamp,
        "action_items": [
            {"description": a.description, "source": a.source,
             "priority": a.priority, "status": a.status}
            for a in report.action_items
        ],
        "contacts": {
            c.name: c.context for c in report.new_contacts
        },
    }
    state_path = STATE_DIR / "dashboard_state.json"
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)
    logger.info(f"State saved to {state_path}")
    return str(state_path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def main():
    logging.basicConfig(
        level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper()),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Auto-detect: morning before 12PM, evening after
    if len(sys.argv) > 1:
        run_type = sys.argv[1]
    else:
        hour = datetime.now().hour
        run_type = "morning" if hour < 12 else "evening"

    if run_type not in ("morning", "evening"):
        print("Usage: hugin-dashboard [morning|evening]")
        print("       (omitted = auto-detect from current time)")
        sys.exit(1)

    print(f"\n📋 Personal Dashboard — {run_type.title()} Briefing\n")

    report, cfg = await run_dashboard(run_type)
    state_path = save_state(report)
    briefing = generate_briefing(report, state_path)

    # Write briefing to user-facing location
    briefing_path = Path(os.environ.get(
        "HUGIN_BRIEFING_PATH",
        os.path.expanduser("~/.hugin/briefing.md"),
    ))
    briefing_path.parent.mkdir(parents=True, exist_ok=True)
    with open(briefing_path, "w") as f:
        f.write(briefing)

    # Send via Telegram if configured
    if cfg.telegram_token and cfg.telegram_chat_id:
        await send_telegram(cfg.telegram_token, cfg.telegram_chat_id, briefing, report)

    print(briefing)
    print(f"📄 Briefing saved to {briefing_path}")
    print(f"💾 State saved to {state_path}")


def cli():
    """Synchronous entry point for console_scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
