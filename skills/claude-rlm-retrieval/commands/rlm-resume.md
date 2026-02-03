# RLM Resume

Load saved context and continue from the last session.

1. Read `.claude-memory/state.json`.
2. Read the most recent `.claude-memory/transcripts/YYYY-MM-DD.md` (if present).
3. Display a resumption summary:

```
🧠 Resuming Context
━━━━━━━━━━━━━━━━━━
⏰ Last update: <lastUpdated>
📍 Active Topics: <...>
🧵 Open Threads:
  • <id> (<status>) — <summary>
📋 Recent Decisions:
  • <date>: <decision>
```

Then ask: "What do you want to work on next?"
