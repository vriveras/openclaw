#!/usr/bin/env python3
"""Claude Code hook helper: refresh index with debounce/cooldown.

Claude Code hooks run on tool events (Bash/Edit/Write). This script makes
index freshness closer to OpenClaw's transcript-driven hooks without thrashing.

Behavior:
- Detect current project's Claude sessions dir: ~/.claude/projects/<escaped-cwd>
- If sessions changed since last refresh AND cooldown passed, run index-sessions.py
- Stores state in .claude-memory/.index-refresh.json

Safe: never raises (best effort); exits 0.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

COOLDOWN_SECONDS = 5 * 60      # 5 minutes
DEBOUNCE_SECONDS = 60          # 60 seconds


def _project_sessions_dir(cwd: Path) -> Path:
    # Claude Code uses a leading '-' in its escaping ("/a/b" -> "-a-b").
    escaped = str(cwd).replace("/", "-")
    return Path.home() / ".claude" / "projects" / escaped


def _memory_root(cwd: Path) -> Path:
    # Keep everything project-local for Claude Code.
    return cwd / ".claude-memory"


def _state_path(mem_root: Path) -> Path:
    return mem_root / ".index-refresh.json"


def main() -> int:
    try:
        cwd = Path.cwd()
        sessions_dir = _project_sessions_dir(cwd)
        if not sessions_dir.exists():
            return 0

        mem_root = _memory_root(cwd)
        mem_root.mkdir(parents=True, exist_ok=True)

        sp = _state_path(mem_root)
        state = {}
        if sp.exists():
            try:
                state = json.loads(sp.read_text())
            except Exception:
                state = {}

        now = time.time()
        last_run = float(state.get("lastRun", 0))
        last_mtime = float(state.get("lastSessionsMtime", 0))

        # Debounce: if we ran very recently, do nothing.
        if now - last_run < DEBOUNCE_SECONDS:
            return 0

        # Compute sessions_dir mtime (cheap)
        try:
            current_mtime = sessions_dir.stat().st_mtime
        except Exception:
            return 0

        # If nothing changed since last time, do nothing.
        if current_mtime <= last_mtime:
            return 0

        # Cooldown: avoid re-index thrash.
        if now - last_run < COOLDOWN_SECONDS:
            return 0

        indexer = cwd / "skills" / "rlm-retrieval" / "scripts" / "index-sessions.py"
        if not indexer.exists():
            return 0

        # Run indexer best-effort.
        subprocess.run([sys.executable, str(indexer)],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,
                       check=False,
                       timeout=60)

        state["lastRun"] = now
        state["lastSessionsMtime"] = current_mtime
        sp.write_text(json.dumps(state, indent=2))
        return 0

    except Exception:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
