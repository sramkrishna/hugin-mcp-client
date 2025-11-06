# Odinson Demo Script - Hacking AI Agents PDX
**Thursday, November 6, 2025 | 5:30 PM - 8:30 PM | Multnomah Athletic Club**

## Overview (2 min)
"This is **Odinson** - a Norse-powered personal AI system built on the Model Context Protocol (MCP)."

### The Norse Architecture:
- **Hugin** (Thought) - Main orchestrator, gathers information
- **Muninn** (Memory) - RAG system for semantic search of all your data
- **Ratatoskr** (Messenger) - GNOME desktop integration (calendar, email, contacts)
- **Yggdrasil** (World Tree) - Connections to external systems (GitLab, GitHub)

---

## Demo 1: Calendar Intelligence (3 min)

```bash
cd /var/home/sri/Projects/hugin-mcp-client
bash run-local.sh
```

### Query 1: Today's Schedule
```
What's on my calendar today?
```
*Shows: Hacking AI Agents event at 9:30 AM*

### Query 2: Meeting Analytics
```
Who have I met with most in the past 3 months?
```
*Demonstrates: Ratatoskr analyzing your calendar patterns*

### Query 3: Date Intelligence
```
Show me all meetings from the past 4 weeks
```
*Demonstrates: Smart date calculation (builtin tool)*

---

## Demo 2: Email + Semantic Memory (3 min)

### Query 1: Email Search
```
Find emails from PyCoders Weekly about machine learning projects
```
*Demonstrates: Ratatoskr querying Thunderbird + semantic filtering*

### Query 2: Memory Recall
```
Search my memory for notes about fundraising campaigns
```
*Demonstrates: Muninn RAG retrieving past conversations/notes*

### Query 3: Cross-Reference
```
What did we discuss about the Giving Monday fundraiser in our last meeting?
```
*Demonstrates: Combining calendar + email + memory*

---

## Demo 3: GitLab Integration (3 min)

### Show the Architecture
```bash
# Show config
cat config.toml | grep -A 3 "servers.yggdrasil"

# Direct glab commands work:
glab repo list --member --per-page 5
```

### Live GitLab Query
```bash
# Show your actual fundraising issues
glab issue list --repo Teams/FundraisingCommittee/IssueTracker --per-page 5
```

**Your Open Issues:**
1. #4: Define Fundraising Committee responsibilities and goals
2. #3: Blog post about success of donation notification
3. #2: Mail to donors on what we accomplished
4. #1: Giving Monday Fundraiser campaign

*Note: Full Hugin integration has an env variable bug - showing the tool exists!*

---

## Demo 4: Multi-Provider Support (2 min)

### Show Config
```toml
[llm]
provider = "anthropic"  # Currently using Claude
model = "claude-sonnet-4-20250514"

# Can switch to:
# provider = "ollama"
# model = "qwen2.5-coder:14b"
# base_url = "http://10.0.0.100:11434"
```

**Key Point:** "Not locked to one provider - works with Claude, Ollama, OpenAI, vLLM"

---

## Demo 5: The MCP Architecture (3 min)

### Show the Ecosystem
```bash
# Show connected servers
hugin  # When it starts, shows:
# ✓ Connected to 3 MCP server(s)
# ✓ Loaded 62 tool(s)
```

### Explain MCP Benefits:
1. **Open Standard** - Not proprietary
2. **Extensible** - Anyone can add servers
3. **Tool-Based** - LLM calls tools, not hardcoded logic
4. **Provider Agnostic** - Same tools work with any LLM

### Show a Tool Definition
```bash
# Example: Calendar tool definition in Ratatoskr
cat /var/home/sri/Projects/ratatoskr-mcp-server/src/ratatoskr_mcp_server/server.py | grep -A 10 "query_calendar_events"
```

---

## Key Talking Points

### What Makes Odinson Different:

1. **Privacy-First**
   - All data stays local
   - Muninn stores YOUR data in YOUR vector DB
   - Can run 100% offline with Ollama

2. **Norse Mythology = Elegant Architecture**
   - Hugin gathers (orchestrates)
   - Muninn remembers (RAG)
   - Ratatoskr delivers (integrations)
   - Yggdrasil connects (external systems)

3. **Built on Open Standards**
   - MCP protocol (Anthropic, but open)
   - Works with any MCP server
   - Community can contribute

4. **Real-World Use**
   - Managing GNOME fundraising campaigns
   - Tracking meetings and decisions
   - Email analysis and organization
   - Project management

---

## Q&A Topics to Cover

### "Why not just use ChatGPT?"
- ChatGPT has no memory between sessions
- Can't access your calendar, email, GitLab
- No semantic search of YOUR historical data
- Odinson remembers everything with context

### "What about Langchain/LlamaIndex?"
- Those are frameworks, Odinson is a complete system
- MCP provides clean server/tool abstraction
- Easier to add new data sources

### "Can I use this?"
- Yes! GitHub: (mention your repo)
- Requires: Python 3.9+, MCP servers
- Works best on Linux (GNOME integration)
- Can adapt for Mac/Windows

### "What's next?"
- v1.0 release planning
- More MCP servers (GitHub, Slack, Jira)
- Event linking (associate notes with meetings)
- Fine-tuned models for specific domains
- Web search integration

---

## Backup: Manual Demonstrations

If live demos fail, show these:

### 1. Architecture Diagram
```
User Query
    ↓
Hugin (Orchestrator)
    ├→ Muninn (Memory/RAG)
    ├→ Ratatoskr (Desktop)
    │   ├→ Calendar
    │   ├→ Email
    │   └→ Contacts
    └→ Yggdrasil (External)
        ├→ GitLab
        └→ GitHub (planned)
```

### 2. Config File
Show `config.toml` - clean, simple MCP server definitions

### 3. Example Tool Output
Show JSON from a glab command - clean structured data

---

## Closing (1 min)

"Odinson shows what's possible when you:
1. Use open standards (MCP)
2. Keep data local and private
3. Build extensible architecture
4. Apply elegant metaphors (Norse mythology)

The future is personal AI that works FOR you, with YOUR data, on YOUR terms."

**Thank you!**

---

## Technical Notes for You

### What Works:
- ✅ Calendar queries (Ratatoskr)
- ✅ Email queries (Ratatoskr)
- ✅ Semantic search (Muninn)
- ✅ Date calculations (builtin)
- ✅ GitLab via direct glab (Yggdrasil concept)

### Known Issues (Don't Demo):
- ⚠️ Web search (HTML parsing broken)
- ⚠️ GitLab in Hugin (GITLAB_HOST env conflict)
- ⚠️ Conversation archival (not tested end-to-end)

### If Asked About Issues:
"This is alpha software - we're actively developing and fixing bugs. The architecture is solid, implementation is ongoing."
