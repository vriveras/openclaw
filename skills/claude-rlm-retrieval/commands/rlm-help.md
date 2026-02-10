# RLM Help

Explain the RLM Retrieval workflow and available commands.

Display:

```
🧠 RLM Retrieval (Claude Code)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

COMMANDS
━━━━━━━━
/rlm-init [type]        Initialize per-project memory (.claude-memory/)
/rlm-state              Show memory status + transcript stats
/rlm-save [summary]     Save a checkpoint (topics, threads, decisions)
/rlm-resume             Resume from last checkpoint
/rlm-get <query>        Search transcripts (temporal + enhanced matching)

WHY IT WORKS
━━━━━━━━━━━━
Claude Code already saves full session transcripts automatically:
  ~/.claude/projects/<escaped-project-path>/*.jsonl

This skill adds:
- Per-project state: .claude-memory/state.json
- Fast narrowing index: .claude-memory/sessions-index.json
- Deterministic-ish freshness: Claude Code hooks (tool events)

INDICATORS
━━━━━━━━━━
🔮 semantic-only (if you add semantic search)
🔍 keyword/RLM search
🧠 both
```
