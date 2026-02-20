---
name: rlm-query-augment
description: Automatically detect context-seeking queries and pre-fetch relevant context before the agent processes the message. Works at the message pipeline level for seamless memory retrieval.
homepage: https://docs.openclaw.ai/hooks#rlm-query-augment
metadata:
  {
    "openclaw":
      {
        "emoji": "🧠",
        "events": ["message:received"],
        "requires": { "config": ["workspace.dir"] },
        "install": [{ "id": "bundled", "kind": "bundled", "label": "Bundled with OpenClaw" }],
      },
  }
---

# RLM Query Augment Hook

## Purpose

Intercepts incoming user messages, detects context-seeking patterns, and auto-fetches relevant context from sessions, memory, and state files. Injects retrieved context into the agent's view **before** processing.

## How It Works

```
User: "What did we decide about ChessRT?"
         ↓
[Hook: message:received]
         ↓
Detect pattern → Run rlm_context_search
         ↓
Inject results into agent context
         ↓
Agent sees: "🔍 Auto-retrieved context for: 'ChessRT decision'..."
```

## Trigger Patterns

| Pattern                       | Example                               | Query Extracted              |
| ----------------------------- | ------------------------------------- | ---------------------------- |
| "What did we do X?"           | "What did we do yesterday?"           | "yesterday"                  |
| "Status of X?"                | "Status of ChessRT?"                  | "ChessRT status"             |
| "Where did we leave off?"     | "Where did we leave off?"             | "yesterday left off"         |
| "What did we decide about X?" | "What did we decide about Glicko?"    | "Glicko decision conclusion" |
| "How did we fix X?"           | "How did we fix Redis?"               | "Redis fix solution"         |
| "Remember when we X?"         | "Remember when we talked about wlxc?" | "we talked about wlxc"       |
| "About X..."                  | "About that container issue..."       | "that container issue"       |

## Configuration

No configuration needed. Automatically enabled when `rlm-retrieval` skill is installed.

## Benefits

1. **Zero agent changes** — Agent just sees context, doesn't need to call tools
2. **Faster responses** — Context pre-fetched during message processing
3. **Works everywhere** — WhatsApp, Telegram, Discord, CLI
4. **Transparent** — User sees 🔍 indicator that context was retrieved

## Debugging

Enable verbose logging:

```bash
DEBUG=rlm-query-augment openclaw gateway start
```

Check hook status:

```bash
openclaw hooks list
```

## Dependencies

- `rlm-retrieval` skill must be installed in workspace
- `context-search.py` script must exist at `skills/rlm-retrieval/scripts/`
