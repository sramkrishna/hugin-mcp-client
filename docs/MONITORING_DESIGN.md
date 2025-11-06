# Hugin Automated Monitoring System

## Design Overview

A systemd-timer-based automation system that enables Hugin to proactively monitor calendars, emails, and other data sources, triggering actions based on events or schedules.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  systemd timer                          │
│              (runs every N minutes)                      │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│            hugin --monitor                              │
│   (batch mode, non-interactive)                         │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│            Monitor Orchestrator                         │
│   • Loads monitoring config from config.toml            │
│   • Loads state from Muninn                             │
│   • Executes each monitoring task                       │
│   • Saves updated state to Muninn                       │
└────────────────────┬────────────────────────────────────┘
                     │
                     ├──► Calendar Monitor
                     ├──► Email Monitor
                     ├──► Document Processor
                     └──► Custom Tasks
```

## Configuration Schema

Add to `config.toml`:

```toml
[monitoring]
enabled = true
log_file = "/var/home/sri/.local/share/hugin/monitor.log"

# Medical appointments workflow
[[monitoring.tasks]]
name = "neurosports_appointments"
type = "calendar_triggered"
description = "Monitor NeuroSports appointments and process related PDFs"

# Trigger: Check 48 hours after appointment
trigger.calendar_search = "NeuroSports"
trigger.delay_hours = 48

# Actions to perform
actions = [
    {type = "search_email", query = "NeuroSports", has_attachments = true},
    {type = "process_pdfs", save_to_contact = "aarti@example.com"},
    {type = "notify", message = "Processed {count} medical PDFs from NeuroSports"}
]

# Weekly summary
[[monitoring.tasks]]
name = "weekly_summary"
type = "scheduled"
description = "Send weekly calendar and task summary"

trigger.schedule = "Mon 08:00"

actions = [
    {type = "query_calendar", period = "this week"},
    {type = "query_tasks", filter = "uncompleted"},
    {type = "notify", message = "Weekly summary ready"}
]

# PyCoders tracking
[[monitoring.tasks]]
name = "pycoders_tracker"
type = "email_triggered"
description = "Track Python projects from PyCoders Weekly"

trigger.email_from = "pycoders"
trigger.email_subject = "PyCoders Weekly"

actions = [
    {type = "extract_links", pattern = "github.com"},
    {type = "store_memory", category = "interesting_projects"},
    {type = "notify", message = "New PyCoders projects tracked"}
]
```

## State Management

State stored in Muninn as events with `event_type = "monitor_state"`:

```json
{
  "event_type": "monitor_state",
  "data": {
    "task_name": "neurosports_appointments",
    "last_run": "2025-11-04T10:30:00",
    "processed_items": [
      {
        "type": "calendar_event",
        "id": "event_123",
        "date": "2025-11-02",
        "processed_at": "2025-11-04T10:30:00"
      },
      {
        "type": "email_pdf",
        "message_id": "msg_456",
        "filename": "lab_results.pdf",
        "processed_at": "2025-11-04T10:30:00"
      }
    ],
    "next_check": "2025-11-04T11:00:00"
  },
  "description": "Monitor state for neurosports_appointments task"
}
```

## Implementation Components

### 1. CLI Extension (`cli.py`)

Add `--monitor` mode:

```python
@click.command()
@click.option('--monitor', is_flag=True, help='Run monitoring tasks')
@click.option('--task', help='Run specific monitoring task')
def main(monitor, task):
    if monitor:
        run_monitor_mode(task_filter=task)
    else:
        run_interactive_mode()
```

### 2. Monitor Module (`monitor.py`)

```python
class MonitorOrchestrator:
    """Orchestrates monitoring tasks."""

    async def run_tasks(self, task_filter=None):
        """Run all enabled monitoring tasks."""

    async def load_state(self, task_name):
        """Load task state from Muninn."""

    async def save_state(self, task_name, state):
        """Save task state to Muninn."""

    async def execute_task(self, task_config):
        """Execute a single monitoring task."""
```

### 3. Task Types

**CalendarTriggeredTask**
- Monitors calendar for specific events
- Triggers actions after delay period
- Tracks processed events to avoid duplicates

**ScheduledTask**
- Runs at specific times (cron-like)
- Weekly summaries, daily digests, etc.

**EmailTriggeredTask**
- Monitors new emails matching criteria
- Processes attachments, extracts data
- Stores findings

**CustomTask**
- User-defined monitoring logic
- Python script or LLM prompt

### 4. Action Types

- `search_email`: Query emails with filters
- `process_pdfs`: Extract and save PDF content
- `query_calendar`: Get calendar events
- `query_tasks`: Get Planify tasks
- `store_memory`: Save to Muninn
- `notify`: Send desktop notification
- `run_prompt`: Execute LLM prompt with data

## Systemd Integration

### Service File: `~/.config/systemd/user/hugin-monitor.service`

```ini
[Unit]
Description=Hugin Monitoring Service
After=network.target

[Service]
Type=oneshot
WorkingDirectory=%h/Projects/hugin-mcp-client
Environment="PATH=%h/Projects/hugin-mcp-client/.venv/bin:/usr/bin"
ExecStart=%h/Projects/hugin-mcp-client/.venv/bin/hugin --monitor
StandardOutput=append:/var/home/sri/.local/share/hugin/monitor.log
StandardError=append:/var/home/sri/.local/share/hugin/monitor-error.log

[Install]
WantedBy=default.target
```

### Timer File: `~/.config/systemd/user/hugin-monitor.timer`

```ini
[Unit]
Description=Hugin Monitoring Timer
Requires=hugin-monitor.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=1h
Persistent=true

[Install]
WantedBy=timers.target
```

### Enable Timer

```bash
systemctl --user daemon-reload
systemctl --user enable hugin-monitor.timer
systemctl --user start hugin-monitor.timer
systemctl --user status hugin-monitor.timer
```

## Security Considerations

1. **Credentials**: Use environment variables or keyring
2. **File Permissions**: Restrict log files to user-only
3. **State Validation**: Validate state data from Muninn
4. **Rate Limiting**: Prevent excessive API calls
5. **Error Handling**: Graceful failures, no crashes

## Testing Strategy

1. **Unit Tests**: Test each task type independently
2. **Integration Tests**: Test with mock MCP servers
3. **Manual Testing**: Run `hugin --monitor --task neurosports_appointments`
4. **Timer Testing**: Use `systemd-analyze calendar` to verify schedule

## Monitoring and Debugging

```bash
# View monitoring logs
tail -f ~/.local/share/hugin/monitor.log

# Check timer status
systemctl --user list-timers hugin-monitor.timer

# Run manual test
hugin --monitor --task neurosports_appointments

# View state in Muninn
hugin
> Query monitor state from Muninn
```

## Future Enhancements

1. **Web Dashboard**: View monitoring status and history
2. **Email Notifications**: Send summaries via email
3. **Webhook Support**: Trigger external services
4. **Machine Learning**: Learn user patterns and suggest tasks
5. **Mobile App**: View notifications on phone
6. **Conditional Logic**: Complex trigger conditions
7. **Task Dependencies**: Chain tasks together

## Example Use Cases

### Medical Appointment Workflow

1. **Trigger**: 48 hours after NeuroSports appointment in calendar
2. **Action 1**: Search Gmail for emails from NeuroSports with PDFs
3. **Action 2**: Download and extract text from PDFs
4. **Action 3**: Save to Aarti's medical notes in Muninn
5. **Action 4**: Send desktop notification: "Processed 2 lab result PDFs"

### Weekly Planning Workflow

1. **Trigger**: Every Monday at 8:00 AM
2. **Action 1**: Get this week's calendar events
3. **Action 2**: Get uncompleted tasks from Planify
4. **Action 3**: Generate summary with LLM
5. **Action 4**: Send notification with summary

### Project Tracking Workflow

1. **Trigger**: New email from PyCoders Weekly
2. **Action 1**: Extract all GitHub project links
3. **Action 2**: Store projects in Muninn with tags
4. **Action 3**: Check if any projects match user interests
5. **Action 4**: Notify about relevant projects

## Implementation Timeline

- **Phase 1** (Day 1): Core monitor infrastructure
  - CLI `--monitor` mode
  - MonitorOrchestrator
  - State management
  - Basic task execution

- **Phase 2** (Day 2): Task types and actions
  - CalendarTriggeredTask
  - ScheduledTask
  - EmailTriggeredTask
  - All action types

- **Phase 3** (Day 3): Systemd integration
  - Service and timer files
  - Installation script
  - Testing and debugging

- **Phase 4** (Day 4): Documentation and polish
  - User documentation
  - Example configurations
  - Error handling improvements
