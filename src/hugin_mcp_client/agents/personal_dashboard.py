"""
Personal Dashboard Agent — inbox intelligence + contact tracking + todo generation.

Purpose:
    Runs 2x/day (morning/evening) to pull recent email conversations,
    summarize per-thread, track new contacts, flag pending action items,
    and maintain a running context file the assistant can reference.

Design:
    - Scheduled via cron/systemd timer (not a daemon)
    - Stateless by default; state lives in Muninn (semantic memory)
    - Falls back to flat JSON files if Muninn is unavailable
    - Output is a markdown briefing and a todo list

Dependencies:
    ratatoskr MCP server (for email + calendar + Planify tasks)
    muninn MCP server (for persistent memory across runs)
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
# Phase 1: Gather data from MCP servers
# ---------------------------------------------------------------------------

async def fetch_recent_email(
    hours: int = 24,
) -> list[EmailThread]:
    """
    Search Ratatoskr for email from the last N hours.
    Returns simplified thread summaries.
    """
    # This phase requires the Ratatoskr MCP server running.
    # For now, return a placeholder — real integration needs the MCP client.
    logger.info(f"Would fetch email from last {hours}h via Ratatoskr")
    return []


async def fetch_calendar_today() -> list[str]:
    """Pull today's events via Ratatoskr calendar integration."""
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
# Orchestrator
# ---------------------------------------------------------------------------

STATE_DIR = Path(os.environ.get("HUGIN_STATE_DIR", os.path.expanduser("~/.hugin/state")))

async def run_dashboard(run_type: str = "morning") -> DashboardReport:
    """
    Full pipeline: gather → summarize → brief → save state.
    """
    logger.info(f"Starting {run_type} dashboard run")

    report = DashboardReport(
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        run_type=run_type,
    )

    # Phase 1: Gather in parallel
    threads_task = fetch_recent_email()
    calendar_task = fetch_calendar_today()
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

    return report


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

    report = await run_dashboard(run_type)
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

    print(briefing)
    print(f"📄 Briefing saved to {briefing_path}")
    print(f"💾 State saved to {state_path}")


def cli():
    """Synchronous entry point for console_scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
