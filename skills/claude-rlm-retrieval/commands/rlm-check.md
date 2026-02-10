# RLM Check

Validate that retrieval is working.

1. Run `python3 skills/rlm-retrieval/scripts/index-sessions.py`.
2. Run `python3 skills/rlm-retrieval/scripts/temporal_search.py "recent work"`.
3. If results are empty but you know you chatted recently:
   - verify Claude Code sessions exist under `~/.claude/projects/<escaped-path>/`.

Report success/failure and what to fix.
