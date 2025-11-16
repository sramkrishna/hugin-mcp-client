# Code Execution Mode Integration

**Status:** Planning / Not Implemented

**Goal:** Reduce token usage by 95% through lazy tool discovery and code execution.

## Problem

Current MCP setup sends all tool schemas in every request:
- ~30,000 tokens for 75+ tools (Ratatoskr, Muninn, Yggdrasil, builtins)
- Context consumed before user query even processed
- Limits how many MCP servers can be added

## Solution

Implement [mcp-server-code-execution-mode](https://github.com/elusznik/mcp-server-code-execution-mode) pattern:
- Only expose 2-3 discovery tools initially (~200 token overhead)
- Claude writes Python code that runs in isolated container
- Code accesses MCP servers via proxy objects
- Tool schemas loaded on-demand only when needed

## Benefits

- **95% token reduction**: 30k → 200 tokens base overhead
- **Unlimited MCP servers**: Add GitHub, Slack, Jira without context explosion
- **Secure execution**: Rootless containers, network isolation
- **Better performance**: Persistent MCP connections

## Integration Approaches

### Option 1: Standalone MCP Server
Run code execution bridge as separate MCP server:
```toml
[servers.code-execution]
command = "mcp-code-execution-server"
args = ["--config", "~/.config/hugin/mcp-servers.json"]
```

Pros: Non-invasive, can test alongside current setup
Cons: Need to route queries appropriately

### Option 2: Hybrid Mode
- Simple queries → Direct MCP tools (current approach)
- Complex workflows → Code execution mode
- Orchestrator decides routing based on query complexity

Pros: Best of both worlds, gradual migration
Cons: More complex orchestrator logic

### Option 3: Full Migration
Replace current orchestrator with code execution bridge:
- All queries go through code execution
- All MCP servers accessed via Python code
- Maximum token savings

Pros: Maximum efficiency, simplified architecture
Cons: Larger change, need to rewrite orchestrator

## Implementation Plan

### Phase 1: Setup and Testing
- [ ] Install mcp-server-code-execution-mode
- [ ] Configure with existing MCP servers
- [ ] Test token usage with sample queries
- [ ] Benchmark vs current approach

### Phase 2: Integration
- [ ] Choose integration approach (Standalone/Hybrid/Full)
- [ ] Implement routing logic if needed
- [ ] Update config files
- [ ] Test with real workloads

### Phase 3: Migration
- [ ] Migrate common query patterns
- [ ] Update documentation
- [ ] Performance tuning
- [ ] Production deployment

## Questions to Answer

- [ ] What's actual token savings with our MCP servers?
- [ ] Does code execution add latency?
- [ ] How to handle errors in sandbox?
- [ ] Can we maintain streaming responses?
- [ ] Impact on existing tool integrations?

## References

- Upstream: https://github.com/elusznik/mcp-server-code-execution-mode
- Anthropic docs: Code Execution with MCP pattern
- Related: Reducing context usage strategies

---

**Created:** 2025-11-15
**Branch:** `feature/code-execution-mode`
**Priority:** Medium (after v1.0 release)
