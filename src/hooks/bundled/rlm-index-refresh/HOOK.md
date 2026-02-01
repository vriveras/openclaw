---
name: rlm-index-refresh
description: "Keep RLM session index fresh on transcript updates"
homepage: https://docs.openclaw.ai/hooks#rlm-index-refresh
metadata:
  {
    "openclaw":
      {
        "emoji": "🔄",
        "events": ["session:transcript:update"],
        "requires": { "config": ["workspace.dir"] },
        "install": [{ "id": "bundled", "kind": "bundled", "label": "Bundled with OpenClaw" }],
      },
  }
---

# RLM Index Refresh Hook

Keeps the RLM session index up-to-date whenever a session transcript changes.

## What It Does

When a session transcript updates:

1. **Debounces rapid updates** (avoid reindexing every message)
2. **Extracts agentId from session file**
3. **Runs index refresh**:
   ```bash
   python3 skills/rlm-retrieval/scripts/index-sessions.py --agent-id <agentId>
   ```

## Why It Matters

- Ensures **fresh context retrieval**
- Eliminates manual index refresh steps
- Enables reliable compaction recovery

## Behavior

- Debounce: 60s (default)
- Cooldown: 5 minutes per agent
- Silent failure if skill is missing

## Disable

```bash
openclaw hooks disable rlm-index-refresh
```
