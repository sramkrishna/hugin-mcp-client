# Multi-Agent Architecture for Hugin Ecosystem

## Vision

A flexible agent framework supporting multiple independent agents for different monitoring/automation tasks:
- **System monitoring**: CPU, memory, disk, performance
- **Mail monitoring**: New emails, important messages, inbox zero
- **Intrusion detection**: Failed logins, unusual network activity, firewall events
- **Calendar intelligence**: Upcoming meetings, preparation reminders
- **Task management**: Overdue tasks, deadline warnings
- **File system**: Large file changes, backup status
- **Network monitoring**: Connectivity issues, bandwidth usage
- **Application monitoring**: Crash detection, update availability

## Architecture Options

### Option A: Agent Framework in Hugin (Lightweight)

**Single orchestrator process managing multiple agents:**

```
┌─────────────────────────────────────────────────────────────┐
│               Hugin Agent Daemon (hugin-agentd)             │
│                                                             │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐ │
│  │ System Monitor │  │  Mail Monitor  │  │  Intrusion   │ │
│  │   Agent        │  │     Agent      │  │   Detection  │ │
│  │                │  │                │  │    Agent     │ │
│  │ • Poll every   │  │ • Check IMAP   │  │ • Watch      │ │
│  │   10s          │  │ • Parse new    │  │   journald   │ │
│  │ • Query        │  │   messages     │  │ • Monitor    │ │
│  │   Ratatoskr    │  │ • Priority     │  │   auth.log   │ │
│  │ • Alert on     │  │   detection    │  │ • Track IPs  │ │
│  │   anomaly      │  │                │  │              │ │
│  └────────────────┘  └────────────────┘  └──────────────┘ │
│         │                    │                    │        │
│         └────────────────────┴────────────────────┘        │
│                              │                             │
│                    ┌─────────▼─────────┐                   │
│                    │  Notification Hub │                   │
│                    │  • Desktop notify  │                   │
│                    │  • Log to Muninn  │                   │
│                    │  • Queue for UI   │                   │
│                    └───────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  MCP Servers      │
                    │  • Ratatoskr      │
                    │  • Muninn         │
                    │  • Mail (new?)    │
                    └───────────────────┘
```

**Pros:**
- Single service to manage (`systemctl --user start hugin-agentd`)
- Shared notification infrastructure
- Agents can cooperate (e.g., "meeting in 5min + high CPU = warn user")
- Centralized logging and configuration

**Cons:**
- Single point of failure (if daemon crashes, all monitoring stops)
- Need to restart all agents to update one
- More complex to develop

**Installation:**
```bash
# Install and enable
pip install hugin-mcp-client
systemctl --user enable hugin-agentd
systemctl --user start hugin-agentd

# Configure
~/.config/hugin/agents.toml

# View status
hugin agents status
```

### Option B: Separate MCP Servers (Modular)

**Each monitoring domain gets its own MCP server with built-in agents:**

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Ratatoskr MCP   │  │   Mail MCP       │  │  Security MCP    │
│                  │  │                  │  │                  │
│ • System tools   │  │ • IMAP/SMTP      │  │ • Auth logs      │
│ • Monitoring     │  │   tools          │  │ • Firewall logs  │
│   agent (24/7)   │  │ • Mail monitor   │  │ • Intrusion      │
│                  │  │   agent          │  │   detection      │
└──────────────────┘  └──────────────────┘  └──────────────────┘
         │                     │                     │
         └─────────────────────┴─────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │      Hugin        │
                    │  (When running)   │
                    │ • Connects to all │
                    │ • Receives alerts │
                    │ • Queries on ask  │
                    └───────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │      Muninn       │
                    │  (Shared memory)  │
                    └───────────────────┘
```

**Pros:**
- Independent lifecycle (restart mail server without affecting system monitor)
- Isolation (mail server crash doesn't affect security monitoring)
- Easier to develop/test individually
- Can be developed by different people/teams
- Each server can have its own dependencies

**Cons:**
- More systemd services to manage
- Harder for agents to cooperate
- More resource usage (multiple Python processes)

**Installation:**
```bash
# Install each separately
pip install ratatoskr-mcp-server
pip install mail-mcp-server
pip install security-mcp-server

# Enable services
systemctl --user enable ratatoskr
systemctl --user enable mail-mcp
systemctl --user enable security-mcp

# Hugin config
~/.config/hugin/config.toml:
[[mcp_servers]]
name = "ratatoskr"
command = "ratatoskr-server"

[[mcp_servers]]
name = "mail"
command = "mail-mcp-server"

[[mcp_servers]]
name = "security"
command = "security-mcp-server"
```

### Option C: Hybrid (Recommended)

**MCP servers for domain logic + Hugin orchestration layer for cooperation:**

```
┌─────────────────────────────────────────────────────────────┐
│                    Hugin Orchestrator                        │
│                    (hugin-agentd)                           │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         High-Level Agent Coordination                │  │
│  │                                                      │  │
│  │  • Meeting Prep: Check calendar + CPU + email       │  │
│  │  • Daily Summary: Aggregate all agent reports       │  │
│  │  • Intelligent Routing: "slow" → system + security  │  │
│  │  • Context Awareness: Night mode, DND, work hours   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
┌────────▼─────────┐  ┌───────▼──────────┐  ┌─────▼──────────┐
│  Ratatoskr MCP   │  │   Mail MCP       │  │  Security MCP  │
│                  │  │                  │  │                │
│ • System metrics │  │ • IMAP client    │  │ • Log parsing  │
│ • Background     │  │ • Email parsing  │  │ • IP tracking  │
│   monitoring     │  │ • Monitor agent  │  │ • Alert rules  │
│ • Stores to      │  │ • Stores to      │  │ • Stores to    │
│   Muninn         │  │   Muninn         │  │   Muninn       │
└──────────────────┘  └──────────────────┘  └────────────────┘
         │                    │                    │
         └────────────────────┴────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │      Muninn       │
                    │  (Unified memory) │
                    │                   │
                    │ • System events   │
                    │ • Email metadata  │
                    │ • Security events │
                    │ • Patterns        │
                    └───────────────────┘
```

**This gives you:**
1. **Independent MCP servers**: Each domain expert handles its own monitoring
2. **Hugin orchestrator**: Coordinates between domains for intelligent behavior
3. **Muninn as shared memory**: All agents store events in one place for correlation

## Specific Agent Designs

### 1. System Monitoring Agent (in Ratatoskr)

**Already designed in PROACTIVE_MONITORING_DESIGN.md**

```python
# Runs in Ratatoskr server process
class SystemMonitorAgent:
    interval = 10  # seconds

    async def collect():
        - CPU, memory, disk
        - Store to Muninn
        - Alert if threshold exceeded
```

### 2. Mail Monitoring Agent

**Option 2A: New MCP Server** (Recommended)

```
mail-mcp-server/
├── src/mail_mcp_server/
│   ├── server.py              # MCP server
│   ├── mail_client.py         # IMAP/SMTP wrapper
│   ├── monitor.py             # Background email checker
│   ├── parsers/
│   │   ├── importance.py      # Detect important emails
│   │   ├── calendar.py        # Extract calendar invites
│   │   └── tracking.py        # Detect read receipts
│   └── tools/
│       ├── check_mail.py      # Get new messages
│       ├── search_mail.py     # Search inbox
│       └── send_mail.py       # Send email
```

**Features:**
```python
# Tools
- check_new_mail() -> List of new emails since last check
- search_mail(query, folder="INBOX") -> Search results
- get_important_mail() -> Priority inbox
- mark_read(message_id)
- send_mail(to, subject, body)
- get_unread_count() -> Number by folder

# Agent behavior
class MailMonitorAgent:
    interval = 60  # Check every minute

    async def check():
        new_emails = await imap_client.get_new()

        for email in new_emails:
            # Store in Muninn
            await muninn.store_event({
                "type": "email_received",
                "from": email.sender,
                "subject": email.subject,
                "timestamp": email.date,
                "importance": classify_importance(email)
            })

            # Alert if important
            if email.importance == "high":
                await notify(f"Important email from {email.sender}")
```

**Configuration:**
```toml
# ~/.config/hugin/mail.toml
[imap]
server = "imap.gmail.com"
port = 993
username = "sri@example.com"
# Use system keyring for password
use_keyring = true

[monitoring]
enabled = true
interval_seconds = 60
notify_on_importance = ["high", "urgent"]

[filters]
important_senders = ["boss@work.com", "team@project.com"]
important_keywords = ["URGENT", "ACTION REQUIRED", "DEADLINE"]
mute_senders = ["noreply@", "notifications@"]
```

**Option 2B: Tool in Ratatoskr** (Lighter)

Just add mail checking tools to Ratatoskr, no background monitoring:
```python
# User asks: "Do I have any important emails?"
# Hugin calls: ratatoskr_check_mail(importance="high")
# Returns: List of important unread emails
```

### 3. Intrusion Detection Agent

**New Security MCP Server:**

```
security-mcp-server/
├── src/security_mcp_server/
│   ├── server.py              # MCP server
│   ├── monitors/
│   │   ├── auth_monitor.py    # Watch /var/log/auth.log
│   │   ├── journal_monitor.py # systemd journal security events
│   │   ├── firewall_monitor.py # UFW/firewalld logs
│   │   └── network_monitor.py # Unusual connections
│   ├── analyzers/
│   │   ├── brute_force.py     # Detect brute force attempts
│   │   ├── geo_ip.py          # GeoIP lookup for suspicious IPs
│   │   └── anomaly.py         # Unusual login times/locations
│   └── tools/
│       ├── get_failed_logins.py
│       ├── get_active_connections.py
│       ├── check_open_ports.py
│       └── analyze_suspicious_ips.py
```

**Features:**
```python
# Tools
- get_failed_logins(since="1h") -> Failed SSH/sudo attempts
- get_active_connections() -> Current network connections
- check_open_ports() -> Open ports and services
- analyze_suspicious_ips(ip) -> GeoIP, reputation, history
- get_firewall_blocks() -> Recently blocked IPs
- check_unusual_activity() -> Login at odd hours, new locations

# Agent behavior
class SecurityMonitorAgent:

    async def watch_auth_log():
        """Monitor /var/log/auth.log in real-time."""
        async for line in tail_file("/var/log/auth.log"):
            if "Failed password" in line:
                ip = extract_ip(line)

                # Store in Muninn
                await muninn.store_event({
                    "type": "failed_login",
                    "ip": ip,
                    "timestamp": now(),
                    "service": "ssh"
                })

                # Check for brute force
                recent_failures = await muninn.query_events(
                    type="failed_login",
                    ip=ip,
                    since="5m"
                )

                if len(recent_failures) >= 5:
                    await notify(
                        f"⚠️ Possible brute force attack from {ip}",
                        severity="critical"
                    )

    async def detect_anomalies():
        """Check for unusual patterns."""
        # Login from new country
        # Login at 3am (user normally inactive)
        # Sudo access from unusual user
        # New service opened port
```

**Configuration:**
```toml
# ~/.config/hugin/security.toml
[monitoring]
enabled = true
watch_auth_log = true
watch_journal = true
watch_firewall = true

[thresholds]
failed_login_threshold = 5
failed_login_window_minutes = 5
unusual_hour_start = "23:00"
unusual_hour_end = "06:00"

[alerting]
notify_on_brute_force = true
notify_on_new_connection = false
notify_on_unusual_login = true

[whitelist]
trusted_ips = ["192.168.1.0/24", "10.0.0.0/8"]
known_vpn_ips = ["203.0.113.1"]
```

**Example Scenarios:**

```
Scenario 1: Brute Force Detection
→ Security agent sees 10 failed SSH logins from 45.76.123.45
→ Stores in Muninn
→ Checks pattern: Same IP, 5 minutes
→ Alerts: "⚠️ Brute force attack from 45.76.123.45 (Russia)"
→ User asks: "What should I do?"
→ Hugin: "This IP has tried to login 10 times. Consider:
   1. Block IP: sudo ufw deny from 45.76.123.45
   2. Disable password auth (use keys only)
   3. Check if your password is compromised"

Scenario 2: Unusual Login
→ Security agent sees successful sudo at 3:24 AM
→ Queries Muninn: User's normal active hours are 9am-11pm
→ Alerts: "⚠️ Unusual activity: sudo access at 3:24 AM"
→ User wakes up: "Was that you?"
→ User: "Yes, I couldn't sleep and was fixing something"
→ Hugin learns: Occasionally active at night is normal

Scenario 3: New Open Port
→ Security agent detects new listening port 8080
→ Checks: Started by process "python3" (user sri)
→ Queries Muninn: Never seen port 8080 before
→ Notification: "New service listening on port 8080 (python3)"
→ User: "Oh right, I'm testing a web server"
→ Stores pattern: User sometimes runs dev servers
```

## Unified Agent Framework

**Common infrastructure for all agents:**

```python
# hugin_mcp_client/agents/base.py

class BaseAgent(ABC):
    """Base class for all monitoring agents."""

    name: str
    interval: int  # seconds between checks
    enabled: bool = True

    def __init__(self, muninn_client, notification_hub):
        self.muninn = muninn_client
        self.notifications = notification_hub
        self._running = False

    async def start(self):
        """Start the agent loop."""
        self._running = True
        while self._running:
            try:
                await self.check()
            except Exception as e:
                logger.error(f"{self.name} error: {e}")

            await asyncio.sleep(self.interval)

    async def stop(self):
        """Stop the agent."""
        self._running = False

    @abstractmethod
    async def check(self):
        """Main agent logic - override in subclass."""
        pass

    async def store_event(self, event_type: str, data: dict):
        """Store event in Muninn."""
        await self.muninn.store_event({
            "event_type": event_type,
            "agent": self.name,
            "timestamp": datetime.now().isoformat(),
            "data": data
        })

    async def notify(self, message: str, severity: str = "info"):
        """Send notification to user."""
        await self.notifications.send({
            "source": self.name,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        })
```

**Agent Manager:**

```python
# hugin_mcp_client/agents/manager.py

class AgentManager:
    """Manages lifecycle of all agents."""

    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.muninn = MuninnClient()
        self.notifications = NotificationHub()

    def register(self, agent: BaseAgent):
        """Register a new agent."""
        self.agents[agent.name] = agent

    async def start_all(self):
        """Start all enabled agents."""
        tasks = []
        for agent in self.agents.values():
            if agent.enabled:
                logger.info(f"Starting agent: {agent.name}")
                tasks.append(agent.start())

        await asyncio.gather(*tasks)

    async def stop_all(self):
        """Stop all agents."""
        for agent in self.agents.values():
            await agent.stop()

    def get_status(self) -> Dict[str, Any]:
        """Get status of all agents."""
        return {
            name: {
                "running": agent._running,
                "enabled": agent.enabled,
                "interval": agent.interval
            }
            for name, agent in self.agents.items()
        }
```

**Configuration:**

```toml
# ~/.config/hugin/agents.toml

[agents.system_monitor]
enabled = true
interval = 10
thresholds = { cpu = 90, memory = 85 }

[agents.mail_monitor]
enabled = true
interval = 60
imap_server = "imap.gmail.com"

[agents.security_monitor]
enabled = true
watch_auth_log = true
brute_force_threshold = 5

[agents.calendar_intelligence]
enabled = true
interval = 300  # Check every 5 minutes
prep_time_minutes = 15  # Remind 15min before meeting

[notifications]
# How to deliver notifications
desktop_notify = true  # D-Bus desktop notifications
console = true  # Print to console if Hugin running
log_file = "~/.local/share/hugin/notifications.log"
```

## Development Workflow

### Create New Agent

```python
# Example: Battery monitor agent
# hugin_mcp_client/agents/battery.py

from agents.base import BaseAgent

class BatteryMonitorAgent(BaseAgent):
    name = "battery_monitor"
    interval = 60  # Check every minute

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_battery_percent = None

    async def check(self):
        """Check battery status."""
        # Get battery info (from Ratatoskr or directly via psutil)
        battery = await self.get_battery_info()

        # Low battery alert
        if battery.percent < 20 and not battery.charging:
            await self.notify(
                f"⚠️ Low battery: {battery.percent}%",
                severity="warning"
            )

        # Battery health degradation
        if battery.percent < self.last_battery_percent - 20:
            # Dropped more than 20% quickly
            await self.store_event("battery_drain", {
                "from": self.last_battery_percent,
                "to": battery.percent,
                "time": "1 minute"
            })

        self.last_battery_percent = battery.percent
```

### Register Agent

```python
# hugin_mcp_client/agents/__init__.py

from .system_monitor import SystemMonitorAgent
from .mail_monitor import MailMonitorAgent
from .security_monitor import SecurityMonitorAgent
from .battery import BatteryMonitorAgent

def create_agent_manager(config):
    manager = AgentManager()

    if config.agents.system_monitor.enabled:
        manager.register(SystemMonitorAgent(...))

    if config.agents.mail_monitor.enabled:
        manager.register(MailMonitorAgent(...))

    if config.agents.security_monitor.enabled:
        manager.register(SecurityMonitorAgent(...))

    if config.agents.battery.enabled:
        manager.register(BatteryMonitorAgent(...))

    return manager
```

## CLI Commands

```bash
# Start agent daemon
hugin agents start

# Stop all agents
hugin agents stop

# Status of all agents
hugin agents status
# Output:
# ✓ system_monitor    running (last check: 2s ago)
# ✓ mail_monitor      running (last check: 45s ago)
# ✓ security_monitor  running (last check: 1s ago)
# ✗ battery_monitor   disabled

# Enable/disable specific agent
hugin agents enable battery_monitor
hugin agents disable mail_monitor

# View recent notifications
hugin notifications list --last 10

# Test an agent manually (one-time check)
hugin agents test system_monitor
```

## Inter-Agent Cooperation Examples

### Example 1: Meeting Preparation

```python
class MeetingPrepAgent(BaseAgent):
    """Coordinates across calendar, system, and mail."""

    async def check(self):
        # Get upcoming meetings from calendar
        meetings = await ratatoskr.get_calendar_events(
            start=now(),
            end=now() + timedelta(minutes=15)
        )

        for meeting in meetings:
            # Check system load
            system = await ratatoskr.get_system_resources()

            # Check unread emails from attendees
            attendees = meeting.attendees
            unread = await mail.search_mail(
                from_addresses=attendees,
                unread=True
            )

            # Compose notification
            issues = []
            if system.cpu > 70:
                issues.append("High CPU - may affect video quality")
            if unread:
                issues.append(f"{len(unread)} unread emails from attendees")

            if issues:
                await self.notify(
                    f"📅 Meeting in 15min: {meeting.title}\n" +
                    "\n".join(f"⚠️ {issue}" for issue in issues)
                )
```

### Example 2: Daily Summary

```python
class DailySummaryAgent(BaseAgent):
    interval = 86400  # Once per day

    async def check(self):
        """Generate daily summary at 8am."""
        if datetime.now().hour != 8:
            return

        # Query Muninn for yesterday's events
        yesterday = datetime.now() - timedelta(days=1)

        system_events = await muninn.query_events(
            type="system_*",
            since=yesterday
        )

        emails = await muninn.query_events(
            type="email_received",
            since=yesterday
        )

        security_events = await muninn.query_events(
            type="security_*",
            since=yesterday
        )

        # Compose summary
        summary = f"""
        📊 Daily Summary for {yesterday.strftime('%A, %B %d')}

        💻 System:
        - Average CPU: 45%
        - Peak memory: 78%
        - 2 high load incidents (resolved)

        📧 Email:
        - {len(emails)} emails received
        - 3 marked as important
        - Inbox: 47 unread

        🔒 Security:
        - {len(security_events)} security events
        - 1 failed login attempt (normal)
        - No anomalies detected
        """

        await self.notify(summary)
```

## Recommendation

**For your use case (system + mail + security), I recommend:**

1. **Hybrid Architecture (Option C)**:
   - Separate MCP servers for each domain (Ratatoskr, Mail, Security)
   - Hugin agent daemon for coordination
   - Muninn as unified memory

2. **Phase 1**: Start with Ratatoskr system monitoring (already designed)

3. **Phase 2**: Add mail-mcp-server as separate project
   - Can develop independently
   - Easy to test in isolation
   - Run as systemd service

4. **Phase 3**: Add security-mcp-server
   - Another independent service
   - Reuses patterns from mail server

5. **Phase 4**: Build Hugin orchestration layer
   - Coordinates between all servers
   - High-level intelligence

This approach:
- ✅ Each agent runs independently (resilient)
- ✅ Easy to develop/test/deploy one at a time
- ✅ Can cooperate through Muninn memory
- ✅ Hugin provides unified interface
- ✅ Scales to many agent types

**Would you like me to create a detailed design for mail-mcp-server or security-mcp-server as the next step?**
