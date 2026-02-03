#!/usr/bin/env python3
"""Session indexer for Claude Code transcripts (RLM retrieval).

Builds a lightweight per-project index from Claude Code session JSONL files:
  ~/.claude/projects/<escaped-project-path>/*.jsonl

Writes:
  .claude-memory/sessions-index.json

Why: temporal_search.py can cheaply narrow to ~N candidate sessions before doing
full-text keyword matching.

This is intentionally simple and portable.

Usage:
  python3 skills/rlm-retrieval/scripts/index-sessions.py
  python3 skills/rlm-retrieval/scripts/index-sessions.py --sessions-dir <path>
  python3 skills/rlm-retrieval/scripts/index-sessions.py --out .claude-memory/sessions-index.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def get_claude_sessions_dir(project_dir: Path) -> Path:
    # Claude Code uses a leading '-' in its escaping ("/a/b" -> "-a-b").
    escaped = str(project_dir).replace("/", "-")
    return Path.home() / ".claude" / "projects" / escaped


def get_memory_root(project_dir: Path) -> Path:
    return project_dir / ".claude-memory"


def extract_text_from_session(session_path: Path, max_lines: int = 800) -> Tuple[str, int, Optional[datetime], Optional[datetime]]:
    texts: List[str] = []
    message_count = 0
    session_start: Optional[datetime] = None
    session_last: Optional[datetime] = None

    try:
        with open(session_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # sample head+tail to avoid huge files
        if len(lines) > max_lines:
            sampled = lines[: max_lines // 2] + lines[-max_lines // 2 :]
        else:
            sampled = lines

        for line in sampled:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            # timestamps
            ts = rec.get("timestamp")
            if ts:
                try:
                    if isinstance(ts, str):
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    elif isinstance(ts, (int, float)):
                        dt = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts)
                    else:
                        dt = None
                    if dt:
                        session_start = session_start or dt
                        session_last = dt
                except Exception:
                    pass

            # Claude Code formats vary by version:
            # - Newer: {type:"message", message:{role, content:[...]}}
            # - Current (2.1.x): {type:"user"|"assistant", message:{role, content:"..."}}
            if rec.get("type") in ("message", "user", "assistant"):
                msg = rec.get("message", {})
                role = msg.get("role")
                if role not in ("user", "assistant"):
                    continue
                message_count += 1
                content = msg.get("content", [])
                if isinstance(content, str):
                    texts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            texts.append(block.get("text", ""))

    except Exception as e:
        print(f"⚠️  Warning: failed reading {session_path}: {e}", file=sys.stderr)

    return "\n".join(texts), message_count, session_start, session_last


def extract_topics(text: str, top_n: int = 12) -> List[str]:
    stop = {
        # ultra-common
        "the", "a", "an", "and", "or", "but", "if", "then", "so", "to", "of", "in", "for", "on", "with",
        "is", "are", "was", "were", "be", "been", "being",
        "i", "me", "my", "we", "our", "you", "your", "they", "their",
        "this", "that", "these", "those", "what", "when", "where", "why", "how",
        # transcript boilerplate
        "system", "message", "messages", "tool", "result", "timestamp",
    }

    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b", text)
    counts: Counter[str] = Counter()
    best_form: Dict[str, str] = {}

    for w in words:
        lw = w.lower()
        if lw in stop:
            continue
        # keep technical terms
        if len(lw) < 3:
            continue
        counts[lw] += 1
        # preserve nicer casing if present
        if lw not in best_form:
            best_form[lw] = w
        elif w.isupper() and not best_form[lw].isupper():
            best_form[lw] = w
        elif any(c.isdigit() for c in w) and not any(c.isdigit() for c in best_form[lw]):
            best_form[lw] = w

    # simple ranking: freq + technical bonus
    scored = []
    for lw, c in counts.items():
        bonus = 0
        orig = best_form[lw]
        if any(ch.isdigit() for ch in orig) or ("-" in orig) or ("_" in orig):
            bonus += 2
        if orig.isupper() and len(orig) <= 8:
            bonus += 2
        scored.append((c + bonus, best_form[lw]))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [w for _, w in scored[:top_n]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions-dir", help="Override Claude sessions dir")
    ap.add_argument("--out", help="Output path (default: .claude-memory/sessions-index.json)")
    args = ap.parse_args()

    project_dir = Path.cwd()
    sessions_dir = Path(args.sessions_dir) if args.sessions_dir else get_claude_sessions_dir(project_dir)

    if not sessions_dir.exists():
        print("❌ Claude Code sessions dir not found for this project", file=sys.stderr)
        print(f"   Expected: {sessions_dir}", file=sys.stderr)
        return 2

    mem_root = get_memory_root(project_dir)
    mem_root.mkdir(parents=True, exist_ok=True)

    out_path = Path(args.out) if args.out else (mem_root / "sessions-index.json")

    sessions: Dict[str, Dict] = {}
    files = sorted(sessions_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)

    for f in files:
        text, msg_count, start, last = extract_text_from_session(f)
        topics = extract_topics(text)
        ts = (last or start)
        sessions[f.stem] = {
            "timestamp": ts.isoformat() if ts else "",
            "date": ts.strftime("%Y-%m-%d") if ts else "",
            "messageCount": msg_count,
            "topics": topics,
        }

    payload = {
        "kind": "claude-code",
        "projectDir": str(project_dir),
        "sessionsDir": str(sessions_dir),
        "lastUpdated": datetime.now().isoformat(),
        "sessions": sessions,
    }

    out_path.write_text(json.dumps(payload, indent=2))
    print(f"✅ Indexed {len(sessions)} sessions → {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
