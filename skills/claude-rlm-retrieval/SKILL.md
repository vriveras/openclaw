---
name: claude-rlm-retrieval
description: RLM retrieval for Claude Code (rlm-get, rlm-state, rlm-check). Enhanced matching (substring, compound, fuzzy, concepts). Compaction survival via transcript dump + debounced index refresh hooks.
version: 3.1.0
author: Vicente Rivera
---

# RLM Retrieval for Claude Code

This skill makes Claude Code *actually usable across long sessions and compaction* by treating Claude’s own transcripts as the source of truth and adding:

- **RLM-style transcript search** (`temporal_search.py`)
- **Per-project state** (`.claude-memory/state.json`)
- **Session index** (`.claude-memory/sessions-index.json`) for fast narrowing
- **Claude Code hooks** (tool-event based) for "deterministic-ish" freshness

> Claude Code already saves full transcripts automatically under:
> `~/.claude/projects/<escaped-project-path>/*.jsonl`

---

## Quick Setup (Per Project)

### 1) Copy skill into your repo

```bash
cp -r ~/.claude/skills/rlm-retrieval <project>/skills/rlm-retrieval
cd <project>
mkdir -p .claude-memory/transcripts
```

### 2) Add project instructions (CLAUDE.md)

Add this to your project’s `CLAUDE.md`:

```markdown
## RLM Retrieval (mandatory for history/status)

YOU MUST run /rlm-get before answering questions like:
- where are we with…
- did you already…
- what happened to…
- status of…

If context seems missing/compacted:
1) python3 skills/rlm-retrieval/scripts/dump_transcript.py --full
2) read .claude-memory/transcripts/YYYY-MM-DD.md
3) python3 skills/rlm-retrieval/scripts/temporal_search.py "<query>"
4) do not guess
```

### 3) Enable Claude Code hooks (recommended)

Copy hooks from:
- `skills/rlm-retrieval/hooks/hooks.json`

Into:
- `~/.claude/settings.json` (merge the `hooks` object)

These hooks:
- refresh the index after tool usage (debounced)
- dump transcript + refresh index on Stop

### 4) Test

```bash
python3 skills/rlm-retrieval/scripts/index-sessions.py
python3 skills/rlm-retrieval/scripts/temporal_search.py "recent work"
```

---

## Commands (Claude Code)

Primary:
- `/rlm-get <query>`
- `/rlm-state`
- `/rlm-save [summary]`
- `/rlm-resume`
- `/rlm-check`

Legacy aliases (still supported):
- `/context-*` (maps to `/rlm-*`)

---

## Files

Project-local:
- `.claude-memory/state.json`
- `.claude-memory/transcripts/YYYY-MM-DD.md` (from `dump_transcript.py`)
- `.claude-memory/sessions-index.json` (from `index-sessions.py`)

Global (Claude Code):
- `~/.claude/projects/<escaped-project-path>/*.jsonl` (raw truth)

---

## Notes on “Determinism” in Claude Code

Claude Code hooks fire on **tool events** (Bash/Edit/Write/Stop), not on "model is about to answer".

So the pattern is:
- use hooks to keep **indexes fresh** without relying on the model’s mood
- use `/rlm-get` as the *canonical* retrieval entrypoint

If you want OpenClaw-level determinism (hooking into `memory_search` itself), that’s where MCP is a natural next step.
