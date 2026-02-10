# RLM State

Show the current memory system status.

1. Read `.claude-memory/state.json` if it exists.
2. Count Claude Code session transcripts for this project:
   - Sessions dir: `~/.claude/projects/<escaped-path>/*.jsonl`
3. If `.claude-memory/sessions-index.json` exists, show last updated time.

Output a compact status block:

```
🧠 Project Memory Status
━━━━━━━━━━━━━━━━━━━━━━━━
📁 Project: <type>
📊 Sessions: <count>
🗂️  Index: <present/absent + age>
📍 Active topics: <...>
🧵 Open threads: <...>
📋 Recent decisions: <...>
```
