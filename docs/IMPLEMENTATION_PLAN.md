# Hugin Ecosystem Implementation Plan

## Current Status
- ✅ Hugin: Basic client with file writing capability
- ✅ Ratatoskr: GNOME integration, calendar tools
- ✅ Muninn: Memory storage
- ✅ Using Anthropic Claude API for LLM

## Privacy Goal
**Don't leak behavioral patterns to external LLM providers**
- Work hours, query times, email patterns, system usage → training data
- Solution: Self-hosted LLM for personal/behavioral queries

## Phased Implementation Plan

### Phase 1: Current State (Working Now)
**Goal: Get system fully working with Claude API**

**Timeline: This month**

**Tasks:**
1. ✅ Add file writing to Hugin (completed)
2. ✅ Fix logging clutter from MCP servers (completed)
3. Add system monitoring tools to Ratatoskr (next session)
   - get_system_resources()
   - get_top_processes()
   - query_journald()
   - check_disk_space()
4. Test end-to-end: User asks "why slow?" → Hugin queries Ratatoskr → Claude synthesizes answer

**Infrastructure:**
- Hugin → Claude API (for all queries)
- Cost: ~$10-50/month
- Privacy: ⚠️ All queries go to Anthropic

**Deliverable:** Fully functional reactive system

---

### Phase 2: Background Monitoring (Rule-Based, No LLM)
**Goal: Add 24/7 monitoring agents using rules, not LLMs**

**Timeline: Month 2**

**Tasks:**
1. Add background monitoring to Ratatoskr
   - CPU/memory threshold detection
   - Store events in Muninn
   - Desktop notifications (D-Bus)
   - NO LLM needed - pure rule-based
2. Add basic mail monitoring (optional)
   - Check IMAP for new mail
   - Rule-based importance (sender whitelist, keywords)
   - NO LLM needed
3. Add basic security monitoring (optional)
   - Watch auth.log for failed logins
   - Count-based brute force detection
   - NO LLM needed

**Infrastructure:**
- Same as Phase 1 (Claude API for user queries)
- Agents run 24/7 with zero LLM cost
- Cost: ~$10-50/month (unchanged)
- Privacy: ⚠️ User questions still go to Claude, but monitoring is local

**Deliverable:** Proactive monitoring with desktop notifications

**Key Insight:** Most monitoring doesn't need an LLM!
- Alert: "CPU > 90%" → Simple rule
- Alert: "5 failed logins from IP" → Counting
- Only need LLM when user asks: "Why is this happening?"

---

### Phase 3: Research Self-Hosted LLM Options
**Goal: Find privacy-preserving, cost-effective LLM hosting**

**Timeline: Month 2-3 (in parallel with Phase 2)**

**Options to Research:**

#### Option A: Lunar Lake NPU (Your Laptop) ⭐ NEW!
```
Pros:
✅ Already have hardware (Lunar Lake laptop)
✅ Zero ongoing cost
✅ Power efficient (3-5W vs 20W GPU)
✅ Perfect for vision tasks (screenshots)
✅ On-device, instant, private
✅ OpenVINO Model Server = OpenAI-compatible API
✅ GGUF support (use llamafile models!)

Cons:
❌ Limited to smaller models (3-7B)
❌ Tool calling less reliable than 70B models
❌ Slower (10-40 tok/s)

Models to try:
- Phi-3-Vision 4.2B (vision/screenshots)
- Qwen 2.5 7B (text queries)
- Phi-3-mini 3.8B (lightweight)

Cost: $0 (included in laptop)
Best for: Vision tasks, simple queries, on-battery

See: OPENVINO_NPU_SETUP.md
```

#### Option B: Remote GPU (Your 10.0.0.100 machine)
```
Pros:
✅ Already have hardware
✅ Zero ongoing cost (just electricity ~$20/month)
✅ Total privacy
✅ Ollama already set up

Cons:
❌ Only available when machine is on
❌ Slower CPU inference (~20-40 tok/s)
❌ If on GPU: ~100-150 tok/s (good!)

Models to try:
- Qwen 2.5 72B (very good reasoning)
- DeepSeek V3 (excellent quality)
- Llama 3.3 70B

Cost: ~$20/month electricity
Best for: Complex queries, multi-tool workflows
```

#### Option C: Hetzner Dedicated GPU Server
```
Pros:
✅ 24/7 availability
✅ RTX 4090 (excellent performance)
✅ EU data residency
✅ Predictable cost
✅ Fast inference (~100-150 tok/s for 70B models)

Cons:
❌ €150/month (~$165/month)

Link: https://www.hetzner.com/dedicated-rootserver/gpu

Cost: ~$165/month
```

#### Option D: Lambda Labs GPU Cloud
```
Pros:
✅ On-demand (start/stop as needed)
✅ Various GPU options
✅ Cheaper than AWS

Cons:
❌ Still ~$0.60-1.10/hour
❌ Cold start delays if on-demand

Link: https://lambdalabs.com/service/gpu-cloud

Cost: ~$0.60/hour A10 ($432/month 24/7, or on-demand)
```

#### Option E: Vast.ai (Marketplace)
```
Pros:
✅ Very cheap (~$0.20-0.40/hour for RTX 4090)
✅ Many options
✅ Good for experimentation

Cons:
❌ Less reliable (community providers)
❌ Not for production

Link: https://vast.ai

Cost: ~$0.20-0.40/hour (~$150-290/month 24/7)
```

#### Option F: RunPod
```
Pros:
✅ Serverless option (auto-scale)
✅ Decent pricing
✅ vLLM templates available

Cons:
❌ Cold start for serverless
❌ Still ~$0.40-0.80/hour

Link: https://www.runpod.io

Cost: ~$0.40/hour+ (~$290/month 24/7)
```

**Action Items for Month 2-3:**
- [ ] **Set up OpenVINO Model Server on Lunar Lake NPU** (highest priority!)
  - Install OpenVINO Model Server
  - Convert Phi-3-Vision for screenshots
  - Test vision queries: "What's in this screenshot?"
  - Benchmark power usage (should be 3-5W)
- [ ] Test larger models on remote GPU (10.0.0.100)
  - Benchmark: Qwen 2.5 72B vs DeepSeek V3 quality
  - Measure actual tokens/sec on your hardware
- [ ] Compare NPU vs GPU vs Claude API
  - Tool calling reliability
  - Quality of responses
  - Power consumption
  - Decide routing strategy

---

### Phase 4: Deploy Self-Hosted LLM
**Goal: Move personal queries to self-hosted, keep Claude for generic**

**Timeline: Month 3-4**

**Configuration:**
```toml
# ~/.config/hugin/llm.toml

[primary]
# Your self-hosted LLM
provider = "vllm"  # or "ollama" if using local
endpoint = "http://your-server:8000/v1"
model = "deepseek-ai/DeepSeek-V3"

[routing]
# Route based on data sensitivity
route_by_context = true

# Personal queries → self-hosted only
personal_contexts = [
    "system_metrics",
    "email",
    "calendar",
    "security",
    "muninn_data"
]

[fallback]
# Optional: Claude for generic queries only
enabled = true
provider = "anthropic"
model = "claude-sonnet-4-20250514"
only_for_generic = true  # No personal context
```

**Tasks:**
1. Deploy chosen self-hosted solution
2. Implement privacy-aware query router
3. Test with real queries
4. Monitor costs and performance
5. Gradually shift traffic from Claude to self-hosted

**Infrastructure:**
- Personal queries → Self-hosted LLM
- Generic queries → Claude (optional fallback)
- Monitoring → Rule-based (no LLM)
- Cost: Depends on chosen option ($20-165/month)
- Privacy: ✅ Personal data stays local

**Deliverable:** Privacy-preserving LLM setup

---

### Phase 5: Advanced Agent Coordination
**Goal: Multi-agent cooperation and intelligence**

**Timeline: Month 4+**

**Tasks:**
1. Implement Hugin orchestration layer
   - Meeting prep agent (calendar + CPU + email)
   - Daily summary agent
   - Context-aware routing
2. Build mail-mcp-server (if needed)
3. Build security-mcp-server (if needed)
4. Implement Muninn pattern learning
   - Baselines by time of day
   - Incident correlation
   - Resolution tracking

**Infrastructure:**
- Multiple MCP servers (Ratatoskr, Mail, Security)
- Hugin orchestrator coordinates them
- All use self-hosted LLM for personal data
- Cost: Same as Phase 4
- Privacy: ✅ Complete

**Deliverable:** Intelligent multi-agent system

---

## Decision Points

### After Phase 1:
**Question:** Is the system useful with just reactive queries?
- Yes → Continue to Phase 2
- No → Rethink approach

### After Phase 2:
**Question:** Are rule-based agents sufficient?
- Yes → Maybe don't need Phase 3 (save money!)
- No → Need LLM for more complex analysis → Phase 3

### After Phase 3 Research:
**Question:** What's the self-hosted approach?

**Recommended: Hybrid NPU + Remote GPU** ⭐
- **NPU (Lunar Lake)**: Vision tasks, simple queries, on-battery
  - OpenVINO Model Server
  - Phi-3-Vision, Qwen 2.5 7B
  - Cost: $0
  - Power: 3-5W
- **Remote GPU (10.0.0.100)**: Complex queries, tool calling
  - vLLM or Ollama
  - Qwen 2.5 72B or DeepSeek V3
  - Cost: ~$20/month electricity
- **Claude API**: Fallback for highest quality
  - Cost: ~$10-50/month

**Total cost: ~$20-70/month**
**Privacy: ✅ Personal data stays local**
**UX: ✅ Excellent (instant on NPU, <1s on GPU)**

**Alternative approaches:**

**If local GPU not sufficient:**
- Hetzner dedicated: ~$165/month
- Best for: Always-on, privacy-first, no local hardware

**If want to minimize costs:**
- NPU only + Claude API fallback
- Cost: ~$10-50/month
- Accept: Limited to small models locally

---

## Cost Summary by Phase

| Phase | Infrastructure | Monthly Cost | Privacy Level |
|-------|---------------|--------------|---------------|
| 1 | Claude API only | $10-50 | ⚠️ Low |
| 2 | Claude API + local agents | $10-50 | ⚠️ Medium |
| 3 | Research only | $10-50 | ⚠️ Medium |
| 4a | Local GPU + Claude fallback | $20-30 | ✅ High |
| 4b | Hetzner + Claude fallback | $165-175 | ✅ High |
| 4c | On-demand cloud + Claude | $50-150 | ✅ High |
| 5 | Same as 4 (chosen option) | $20-175 | ✅ High |

---

## Current Next Steps

**This Week:**
1. ✅ File writing capability added to Hugin
2. ✅ Logging fixed for MCP servers
3. Use separate Claude session to add system monitoring tools to Ratatoskr
4. Test reactive system: "why is my computer slow?"

**Next Week:**
- Continue with Phase 1 tasks
- Get comfortable with the system
- Understand what queries you actually make

**This Month:**
- Complete Phase 1
- Start thinking about Phase 2 (background monitoring)

**No Rush:** Take time to validate each phase before moving to next.

---

## Key Principles

1. **Privacy First**: Personal data should never leave your infrastructure
2. **Incremental**: Each phase delivers value independently
3. **Cost Conscious**: Understand costs before committing
4. **Practical**: Start simple (rules), add LLM only when needed
5. **User Control**: You decide what data goes where

---

## Questions to Answer During Phase 3 Research

- [ ] What's your actual query volume? (affects cost analysis)
- [ ] Can you tolerate 2-5 min cold starts?
- [ ] Is 24/7 availability important?
- [ ] What's your privacy/cost tradeoff?
- [ ] How much do you value inference speed (tok/s)?
- [ ] Local GPU sufficient or need cloud?

---

## References

- [PROACTIVE_MONITORING_DESIGN.md](./PROACTIVE_MONITORING_DESIGN.md) - Detailed monitoring design
- [MULTI_AGENT_ARCHITECTURE.md](./MULTI_AGENT_ARCHITECTURE.md) - Agent framework design
- Ratatoskr repository: `/var/home/sri/Projects/ratatoskr-mcp-server`
- Muninn repository: `/var/home/sri/Projects/muninn-mcp-server`
- Hugin repository: `/var/home/sri/Projects/hugin-mcp-client`

---

**Remember:** Most monitoring doesn't need an LLM. Rule-based agents are free, fast, and private!
