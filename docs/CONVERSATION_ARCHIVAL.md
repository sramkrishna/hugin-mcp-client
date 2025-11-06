# Conversation Archival and Context Window Management

## Overview

Hugin now includes automatic conversation archival to prevent context window overflow errors. When conversations approach Claude's 200K token limit, old messages are automatically archived to Muninn for long-term semantic search while keeping recent messages in the active context.

## How It Works

### 1. Token-Based Sliding Window

- **Max Context**: 150,000 tokens (75% of Claude's 200K limit)
- **Pruning Trigger**: When conversation exceeds 150K tokens
- **Retention**: Keeps most recent ~75K tokens after pruning
- **Minimum Messages**: Always keeps at least 10 recent messages

### 2. Automatic Archival

When pruning occurs:
1. Old messages are queued for archival
2. Messages are stored in Muninn as `conversation_archive` events
3. Each archive includes:
   - Full message history
   - Metadata (timestamps, message counts, first user message)
   - Semantic description for search

### 3. Deferred Processing

- Archives are queued synchronously (no blocking)
- Processing happens asynchronously at start of next message
- Gracefully handles archival failures (prunes anyway to prevent overflow)

## Implementation Details

### Files Modified

#### `src/hugin_mcp_client/llm_provider.py`
- Added token estimation methods (`_estimate_tokens`, `_estimate_message_tokens`)
- Added `_estimate_conversation_tokens()` to calculate total context size
- Added `pending_archive` queue for deferred archival
- Enhanced `_prune_history()` with token-based sliding window
- Added `max_context_tokens` parameter (default: 150,000)
- Added `archive_callback` support

#### `src/hugin_mcp_client/orchestrator.py`
- Added `_archive_to_muninn()` async method
- Added `_process_pending_archives()` to process queue
- Modified `initialize()` to set up archive callback if Muninn available
- Modified `process_message()` to process archives before each message

### Configuration

No configuration needed! Archival is automatically enabled when:
- Muninn MCP server is configured in `config.toml`
- Conversation exceeds 150K tokens

### Logging

The system logs when:
- Context approaches limit
- Messages are queued for archival
- Archival succeeds or fails
- Conversation is pruned

Example log output:
```
INFO - Context window approaching limit: 152,341 / 150,000 tokens. Archiving and pruning old messages...
INFO - Queued 45 messages for archival
INFO - After pruning: 74,892 tokens remaining in context
INFO - Successfully archived 45 messages to Muninn
```

## Retrieving Archived Conversations

Archived conversations can be searched using Muninn's semantic search:

```python
# Search for past conversations about a topic
result = await muninn_client.call_tool("semantic_search", {
    "query": "conversations about calendar appointments",
    "search_type": "events",
    "limit": 10
})
```

Or query by type:
```python
# Get all archived conversations
result = await muninn_client.call_tool("query_events", {
    "event_type": "conversation_archive",
    "limit": 100
})
```

## Benefits

1. **No More Context Overflow**: Automatically prevents 200K token errors
2. **Conversation Continuity**: Keeps recent context while preserving history
3. **Semantic Search**: Find past conversations by meaning, not just keywords
4. **Zero Configuration**: Works out-of-the-box with Muninn
5. **Performance**: Deferred archival doesn't block conversation flow

## Testing

Run the test suite:
```bash
python test_archival.py
```

This tests:
- Token estimation accuracy
- Sliding window pruning
- Archive queue functionality

## Technical Notes

### Token Estimation

Uses a simple heuristic: **1 token ≈ 4 characters**

This is approximate but conservative (tends to over-estimate), which is good for preventing overflow.

### Async/Sync Coordination

The archival callback is called from sync context (`_prune_history`) but needs to perform async operations (MCP tool calls). This is solved by:
1. Queueing archives synchronously
2. Processing queue asynchronously in `process_message()`

### Memory Efficiency

Archived messages are removed from memory, keeping RAM usage bounded even for very long conversations.

## Future Enhancements

Potential improvements:
- Use actual token counting (via tiktoken or Claude API)
- Configurable token limits and retention policies
- Conversation summarization before archival
- Automatic retrieval of relevant archived context
- Archive compression for very large conversations
