# RLM Init

Initialize memory for this project.

$ARGUMENTS can specify project type (e.g., "rust", "python", "typescript").

1. Create `.claude-memory/` directory.
2. Create `.claude-memory/state.json` (topics/threads/decisions).
3. Add `.claude-memory/` to `.gitignore` if present.
4. (Optional but recommended) Create/refresh the sessions index:
   - Run: `python3 skills/rlm-retrieval/scripts/index-sessions.py`

Confirm:
`✅ RLM memory initialized. Use /rlm-save to checkpoint, /rlm-get to retrieve.`
