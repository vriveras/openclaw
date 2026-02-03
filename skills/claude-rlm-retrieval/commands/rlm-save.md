# RLM Save

Update `.claude-memory/state.json` with current context.

$ARGUMENTS contains optional notes about this session.

1. Read existing `.claude-memory/state.json` or create if missing.
2. Update:
   - lastUpdated (ISO)
   - activeTopics
   - openThreads (id/status/summary)
   - decisions (date/decision/context)
   - projectContext.type + notes
3. Write `.claude-memory/state.json`.

Confirm:
`✅ State saved. Active: [topics]. Open threads: [count].`

Note: Claude Code saves raw transcripts automatically. This is only structured state.
