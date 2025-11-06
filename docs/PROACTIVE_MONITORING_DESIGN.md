# Proactive System Monitoring Design

## Overview

A proactive monitoring system that learns normal system behavior patterns and alerts users to anomalies. The system integrates across Ratatoskr (data collection), Muninn (pattern learning/memory), and Hugin (user interaction).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Hugin (Client)                       │
│  - Receives notifications from Ratatoskr                     │
│  - Queries Muninn for historical patterns                    │
│  - Presents insights to user                                 │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ MCP Notifications
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Ratatoskr (Monitor)                       │
│  - Collects system metrics (CPU, memory, disk, journal)      │
│  - Background monitoring thread                              │
│  - Threshold-based anomaly detection                         │
│  - Sends notifications to connected MCP clients              │
│  - Stores events in Muninn                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ Store Events
┌─────────────────────────────────────────────────────────────┐
│                     Muninn (Memory)                          │
│  - Stores system metrics over time                           │
│  - Learns patterns: "Normal" vs "Abnormal"                   │
│  - Baseline establishment (e.g., idle vs work hours)         │
│  - Semantic search for similar past incidents                │
│  - Provides context for alerts                               │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Ratatoskr: System Monitor

#### New Components

**A. System Metrics Collector** (`ratatoskr_mcp_server/monitors/system_monitor.py`)
```python
class SystemMetricsCollector:
    """Collects system metrics periodically."""

    def collect_metrics(self) -> SystemMetrics:
        - CPU usage (overall + per-core)
        - Memory usage (used, available, swap)
        - Disk I/O (read/write rates)
        - Network I/O (rx/tx rates)
        - Load averages (1m, 5m, 15m)
        - Top processes by CPU/memory
        - Journald recent errors/warnings
        - Temperature sensors (if available)
```

**B. Background Monitor Thread** (`ratatoskr_mcp_server/monitors/background_monitor.py`)
```python
class BackgroundSystemMonitor:
    """Runs in background, collects metrics every N seconds."""

    - Configurable collection interval (default: 10 seconds)
    - Configurable alert thresholds (CPU, memory, disk)
    - Anomaly detection logic
    - MCP notification sending
    - Integration with Muninn for pattern storage
```

**C. Anomaly Detection** (`ratatoskr_mcp_server/utils/anomaly_detection.py`)
```python
class AnomalyDetector:
    """Detects abnormal system behavior."""

    Strategies:
    1. Threshold-based (immediate):
       - CPU > 90% for 1 minute
       - Memory > 85% for 30 seconds
       - Disk space < 10%
       - Sudden spike: CPU jumps >40% in 10 seconds

    2. Pattern-based (via Muninn):
       - Compare current metrics to historical baselines
       - Context-aware: weekday 9am-5pm vs weekend
       - Learn user-specific patterns
       - Detect unusual process combinations
```

**D. MCP Notifications** (`ratatoskr_mcp_server/notifications.py`)
```python
class NotificationManager:
    """Send notifications to connected MCP clients."""

    Types:
    - system/resource_alert: High CPU/memory/disk
    - system/performance_degradation: System slow
    - system/error: Critical journal errors
    - system/anomaly: Unusual behavior detected

    Format:
    {
        "type": "system/resource_alert",
        "severity": "warning" | "critical",
        "timestamp": "2025-11-02T12:00:00Z",
        "message": "High memory usage: 87% (7.2GB/8GB)",
        "details": {
            "metric": "memory",
            "current_value": 87,
            "threshold": 85,
            "top_processes": [...]
        },
        "muninn_context": {
            "similar_incidents": 3,
            "last_occurrence": "2025-10-30T14:00:00Z",
            "baseline_at_this_time": 45
        }
    }
```

#### New MCP Tools

```python
# Reactive queries (for when user asks "why is it slow?")
- get_system_resources() -> Current snapshot
- get_top_processes(sort_by="cpu"|"memory") -> Top N processes
- query_journald(since="1h", severity="error") -> Recent logs
- get_system_load() -> Load averages, uptime
- check_disk_space() -> Disk usage per mount

# Proactive monitoring control
- start_monitoring(config: MonitorConfig) -> Start background monitoring
- stop_monitoring() -> Stop background monitoring
- get_monitoring_status() -> Is monitoring running, last alert
- set_alert_thresholds(cpu=90, memory=85, disk=90) -> Configure
```

### 2. Muninn: Pattern Learning & Memory

#### New Components

**A. System Metrics Storage** (`muninn_mcp_server/storage/metrics_store.py`)
```python
class MetricsStore:
    """Time-series storage for system metrics."""

    Schema:
    - timestamp
    - cpu_percent
    - memory_percent
    - disk_read_mb_s
    - disk_write_mb_s
    - network_rx_mb_s
    - network_tx_mb_s
    - load_1m, load_5m, load_15m
    - top_process_name
    - top_process_cpu
    - top_process_memory

    Indexing:
    - By timestamp (for time-range queries)
    - By hour-of-day (for baseline calculation)
    - By day-of-week (for pattern recognition)
```

**B. Baseline Calculator** (`muninn_mcp_server/analysis/baseline.py`)
```python
class BaselineCalculator:
    """Establishes normal behavior baselines."""

    Methods:
    - calculate_baseline(metric, timeframe="weekday_9-5") -> avg, stddev
    - get_contextual_baseline(metric, time=now()) -> expected range
    - is_anomalous(metric, value, time=now()) -> bool, z_score

    Contexts:
    - Weekday work hours (9am-5pm)
    - Weekday off hours
    - Weekend
    - Night time
    - First hour after boot

    Example:
    - "Normal" CPU during work hours: 45% ± 15%
    - "Normal" CPU at night: 5% ± 3%
    - Alert if: current > (baseline + 2*stddev)
```

**C. Incident Correlation** (`muninn_mcp_server/analysis/incidents.py`)
```python
class IncidentCorrelator:
    """Find patterns in system issues."""

    - Store incidents: {timestamp, type, metrics, resolution}
    - Semantic search: Find similar past incidents
    - Pattern extraction: "High CPU always happens after Chrome opens"
    - Resolution suggestions: "Last time: closed Firefox tabs"

    Vector embedding includes:
    - Metric values at time of incident
    - Active processes
    - Recent journal entries
    - User's recent activities (from Ratatoskr app launch data)
```

#### New MCP Tools

```python
- store_system_metrics(metrics: SystemMetrics) -> Store snapshot
- get_baseline(metric, context="current") -> Expected baseline
- query_similar_incidents(current_state) -> Past similar situations
- get_system_patterns(days=7) -> Daily/hourly patterns
- store_incident(incident: Incident) -> Save for learning
- get_incident_resolution(incident_id) -> How was it resolved
```

### 3. Hugin: User Interaction

#### New Components

**A. Notification Handler** (`hugin_mcp_client/notifications.py`)
```python
class NotificationHandler:
    """Handle incoming notifications from MCP servers."""

    - Register for MCP server notifications
    - Queue notifications for processing
    - Display to user (rich console formatting)
    - Optionally trigger automatic queries to Muninn

    Display Format:
    ⚠️  System Alert [12:34 PM]
    High memory usage: 87% (7.2GB/8GB)

    Top consumers:
    • Firefox: 2.3GB (28%)
    • Chrome: 1.8GB (22%)
    • Code: 1.1GB (13%)

    💡 Context: This is 42% higher than your usual
    Saturday afternoon baseline (45%).

    Similar incident on Oct 30 - Resolved by: Closed Firefox tabs

    [Ask me "what should I do?" for suggestions]
```

**B. Proactive Insights** (`hugin_mcp_client/insights.py`)
```python
class ProactiveInsights:
    """Generate insights from Muninn patterns."""

    - Daily summary: "Your system was slower than usual yesterday"
    - Pattern alerts: "Firefox has crashed 3 times this week"
    - Recommendations: "Consider upgrading RAM (at 90% during work)"
    - Predictive: "Disk will be full in ~14 days at current rate"
```

## Data Flow Examples

### Example 1: High Memory Alert

```
1. [Ratatoskr] Background monitor collects metrics every 10s
2. [Ratatoskr] Detects: memory = 87% > threshold (85%)
3. [Ratatoskr] Queries top processes, gets Firefox=2.3GB, Chrome=1.8GB
4. [Ratatoskr] Stores event in Muninn:
   store_system_metrics({
     timestamp: now,
     memory_percent: 87,
     top_process: "Firefox",
     context: {...}
   })

5. [Ratatoskr] Queries Muninn for context:
   baseline = get_baseline("memory", context="saturday_afternoon")
   # Returns: 45% ± 10%
   similar = query_similar_incidents(current_state)
   # Returns: [Incident from Oct 30, resolved by closing tabs]

6. [Ratatoskr] Sends MCP notification to Hugin:
   {
     type: "system/resource_alert",
     severity: "warning",
     message: "High memory usage: 87%",
     details: {top_processes: [...]},
     muninn_context: {baseline: 45, similar_incidents: [...]}
   }

7. [Hugin] Receives notification, formats and displays to user
8. [Hugin] User asks: "What should I do?"
9. [Hugin] Queries Muninn: get_incident_resolution(similar_incident_id)
10. [Hugin] Suggests: "Based on Oct 30, try closing Firefox tabs"
```

### Example 2: "Why is my computer slow?"

```
1. [User] Asks Hugin: "Why is my computer slow?"
2. [Hugin] Calls multiple tools in parallel:
   - ratatoskr_get_system_resources()
   - ratatoskr_get_top_processes(sort_by="cpu")
   - ratatoskr_query_journald(since="5m", severity="warning")
   - muninn_get_baseline("cpu", context="current")
   - muninn_query_similar_incidents({slow: true})

3. [Hugin] Receives data:
   - CPU: 78% (baseline: 40%)
   - Top: gnome-software 65%
   - Journal: "packagekit: updating system packages"
   - Muninn: Similar incident last week, resolved after updates finished

4. [Hugin] Synthesizes response:
   "Your system is running software updates in the background
   (gnome-software using 65% CPU). This is normal and should
   finish in ~5-10 minutes. Last week this took 8 minutes."
```

## Implementation Phases

### Phase 1: Reactive Tools ✅ (Week 1)
- Add system monitoring tools to Ratatoskr
- User can query "why slow?" and get diagnostics
- No background monitoring yet

### Phase 2: Basic Proactive Monitoring (Week 2-3)
- Background monitoring thread in Ratatoskr
- Simple threshold-based alerts (>85% memory, >90% CPU)
- MCP notifications to Hugin
- Store metrics in Muninn (time-series)

### Phase 3: Pattern Learning (Week 4-5)
- Baseline calculation in Muninn
- Context-aware baselines (time of day, day of week)
- Anomaly detection using baselines
- Store incidents with metadata

### Phase 4: Intelligent Insights (Week 6+)
- Incident correlation and similarity search
- Resolution tracking and suggestions
- Predictive alerts (disk will fill in N days)
- Daily/weekly summaries

## Technical Challenges & Solutions

### Challenge 1: MCP Notifications
**Problem**: MCP 1.0 spec has limited support for server-initiated notifications

**Solution**:
- Option A: Use MCP sampling (Hugin periodically checks for new alerts)
- Option B: Extend MCP with custom notification channel
- Option C: Use Ratatoskr's notification system with callback handlers
- **Recommended**: Start with Option A (polling), migrate to B when MCP spec stabilizes

### Challenge 2: Resource Usage of Monitoring
**Problem**: Don't want the monitor to slow down the system

**Solution**:
- Lightweight collection (psutil is efficient)
- Configurable interval (default: 10s, adjustable to 60s)
- Smart sampling: More frequent when anomaly detected
- Pause monitoring if system is very slow (>95% CPU for 5min)

### Challenge 3: False Positives
**Problem**: Alert fatigue from spurious alerts

**Solution**:
- Adaptive thresholds based on learned patterns
- Require sustained high usage (30s-1min) before alerting
- User feedback: "Dismiss and don't alert for this again"
- Learning: User ignored 5 "Firefox high memory" alerts → stop alerting

### Challenge 4: Cold Start Problem
**Problem**: No baselines when first installed

**Solution**:
- Use reasonable defaults first week
- "Learning mode" banner: "Learning your patterns (6 days left)"
- Require minimum data: 3 days before enabling pattern-based alerts
- Option to import patterns from similar systems

### Challenge 5: Privacy & Security
**Problem**: System monitoring data is sensitive

**Solution**:
- All data stored locally (Muninn SQLite/ChromaDB)
- No telemetry or cloud uploads
- Configurable: User can disable specific metrics
- Anonymize process names option (for screenshots/sharing)

## Configuration Example

```toml
# config.toml for Hugin

[monitoring]
enabled = true
interval_seconds = 10
enable_notifications = true

[monitoring.thresholds]
cpu_percent = 90
memory_percent = 85
disk_percent = 90
sustained_duration_seconds = 30

[monitoring.baselines]
enabled = true
learning_period_days = 7
min_samples_required = 100

[monitoring.contexts]
# Different thresholds for different times
weekday_work_hours = { start = "09:00", end = "17:00", cpu_threshold = 80 }
night_time = { start = "22:00", end = "06:00", cpu_threshold = 95 }

[monitoring.privacy]
collect_process_names = true
collect_journal_logs = true
anonymize_on_export = true

[notifications]
display_in_console = true
save_to_muninn = true
min_severity = "warning"  # "info" | "warning" | "critical"
```

## API Examples

### Ratatoskr Tools

```python
# Reactive queries
ratatoskr_get_system_resources()
# Returns:
{
  "cpu_percent": 45.2,
  "memory_percent": 62.1,
  "memory_used_gb": 5.0,
  "memory_total_gb": 8.0,
  "disk_percent": 78.5,
  "load_1m": 2.3,
  "load_5m": 1.8,
  "load_15m": 1.5,
  "uptime_hours": 48.2
}

ratatoskr_get_top_processes(limit=5, sort_by="memory")
# Returns:
[
  {"name": "Firefox", "pid": 12345, "cpu": 12.3, "memory_mb": 2300},
  {"name": "Chrome", "pid": 12346, "cpu": 8.1, "memory_mb": 1800},
  ...
]

ratatoskr_query_journald(since="1h", severity="error", limit=10)
# Returns:
[
  {
    "timestamp": "2025-11-02T12:34:56Z",
    "severity": "error",
    "unit": "NetworkManager.service",
    "message": "Connection timeout"
  },
  ...
]

# Proactive monitoring
ratatoskr_start_monitoring(config={
  "interval_seconds": 10,
  "thresholds": {"cpu": 90, "memory": 85}
})

ratatoskr_get_monitoring_status()
# Returns:
{
  "running": true,
  "started_at": "2025-11-02T12:00:00Z",
  "samples_collected": 360,
  "last_alert": "2025-11-02T12:30:00Z",
  "last_alert_type": "high_memory"
}
```

### Muninn Tools

```python
muninn_store_system_metrics(metrics={
  "timestamp": "2025-11-02T12:34:56Z",
  "cpu_percent": 45.2,
  "memory_percent": 62.1,
  ...
})

muninn_get_baseline(metric="cpu", context="current")
# Returns:
{
  "metric": "cpu",
  "context": "weekday_afternoon",
  "baseline_mean": 42.5,
  "baseline_stddev": 12.3,
  "expected_range": [30.2, 54.8],
  "samples": 250
}

muninn_query_similar_incidents(state={
  "cpu": 85,
  "memory": 70,
  "top_process": "gnome-software"
})
# Returns:
[
  {
    "incident_id": "abc123",
    "timestamp": "2025-10-28T14:00:00Z",
    "similarity_score": 0.92,
    "description": "High CPU during system updates",
    "resolution": "Completed after 8 minutes",
    "metrics": {...}
  },
  ...
]

muninn_get_system_patterns(days=7, metric="cpu")
# Returns:
{
  "hourly_pattern": {
    "00": 5.2, "01": 4.8, ... "23": 6.1
  },
  "daily_pattern": {
    "monday": 45.2, "tuesday": 48.1, ...
  },
  "peak_hours": ["10:00", "14:00", "16:00"],
  "quiet_hours": ["02:00", "03:00", "04:00"]
}
```

## Future Enhancements

1. **GPU Monitoring**: Detect GPU usage for gaming/ML workloads
2. **Network Analysis**: Alert on unusual network traffic
3. **Process Lifecycle**: Track process startup/crash patterns
4. **System Health Score**: Daily 0-100 health rating
5. **Predictive Maintenance**: "SSD showing signs of wear"
6. **Integration with Calendar**: "High CPU expected - you have a video call scheduled"
7. **Multi-Machine**: Compare across multiple systems
8. **Mobile App**: Push notifications to phone for critical alerts

## Success Metrics

- **Reactive**: User asks "why slow?" → Gets actionable answer in <3s
- **Proactive**: Alert user before they notice slowness (>70% success rate)
- **Learning**: Reduce false positives by 50% after 2 weeks
- **Helpfulness**: User finds resolutions helpful (track "dismiss" vs "follow suggestion" rate)
- **Performance**: Monitor uses <1% CPU, <50MB RAM on average

## Conclusion

This design provides a comprehensive proactive monitoring system that:
- Learns user-specific patterns
- Provides contextual alerts with historical insights
- Suggests resolutions based on past incidents
- Scales from reactive queries to proactive intelligence

The phased approach allows incremental implementation while delivering value at each step.
