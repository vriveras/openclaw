#!/usr/bin/env python3
"""Dump current Claude Code session transcript to project memory (append mode).

Works with both:
- Claude Code: ~/.claude/projects/<escaped-project-path>/*.jsonl
- OpenClaw: ~/.openclaw/agents/<agentId>/sessions/*.jsonl
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

def get_claude_code_sessions_dir():
    """Find Claude Code sessions directory for current project."""
    cwd = os.getcwd()
    # Claude Code escapes paths: /home/user/project → -home-user-project
    # Claude Code uses a leading '-' in its escaping ("/a/b" -> "-a-b").
    escaped = cwd.replace("/", "-")
    sessions_dir = Path.home() / ".claude" / "projects" / escaped
    if sessions_dir.exists():
        return sessions_dir
    return None

def get_openclaw_sessions_dir(agent_id="main"):
    """Find OpenClaw sessions directory."""
    # Try both possible locations
    for base in [".openclaw", ".clawdbot"]:
        sessions_dir = Path.home() / base / "agents" / agent_id / "sessions"
        if sessions_dir.exists():
            return sessions_dir
    return None

def get_output_dir():
    """Get output directory based on environment."""
    # Claude Code: project-local
    if Path(".claude-memory").exists() or Path("CLAUDE.md").exists():
        return Path(".claude-memory/transcripts")
    # OpenClaw: workspace memory
    return Path("memory/transcripts")

STATE_FILE_NAME = ".state.json"

def load_state(output_dir):
    """Load last dump state."""
    state_file = output_dir / STATE_FILE_NAME
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except:
            pass
    return {}

def save_state(output_dir, state):
    """Save dump state."""
    output_dir.mkdir(parents=True, exist_ok=True)
    state_file = output_dir / STATE_FILE_NAME
    state_file.write_text(json.dumps(state, indent=2))

def extract_text(content):
    """Extract text from message content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif item.get("type") == "tool_use":
                    texts.append(f"[tool: {item.get('name', 'unknown')}]")
                elif item.get("type") == "tool_result":
                    # Skip verbose tool results
                    continue
            elif isinstance(item, str):
                texts.append(item)
        return " ".join(texts)
    return str(content)

def dump_transcript(session_id=None, output_dir=None, full=False, agent_id="main"):
    """Dump session transcript to markdown file (incremental append)."""
    
    # Find sessions directory (Claude Code or OpenClaw)
    sessions_dir = get_claude_code_sessions_dir()
    if not sessions_dir:
        sessions_dir = get_openclaw_sessions_dir(agent_id)
    
    if not sessions_dir or not sessions_dir.exists():
        print(f"❌ No sessions directory found")
        print(f"   Tried Claude Code: ~/.claude/projects/...")
        print(f"   Tried OpenClaw: ~/.openclaw/agents/{agent_id}/sessions/")
        return
    
    # Output directory
    output_dir = Path(output_dir) if output_dir else get_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find most recent session if not specified
    if not session_id:
        sessions = sorted(sessions_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not sessions:
            print("No sessions found")
            return
        session_file = sessions[0]
        session_id = session_file.stem
    else:
        session_file = sessions_dir / f"{session_id}.jsonl"
    
    if not session_file.exists():
        print(f"Session not found: {session_file}")
        return
    
    # Load state
    state = load_state(output_dir)
    session_state = state.get(session_id, {"last_line": 0, "last_ts": None})
    last_line = 0 if full else session_state.get("last_line", 0)
    
    # Parse session from last position
    messages = []
    current_line = 0
    with open(session_file) as f:
        for line in f:
            current_line += 1
            if current_line <= last_line:
                continue
            try:
                msg = json.loads(line.strip())
                # Handle both Claude Code and OpenClaw formats
                if "message" in msg:
                    m = msg["message"]
                    role = m.get("role", "unknown")
                    content = extract_text(m.get("content", ""))
                    ts = msg.get("timestamp", "")
                elif msg.get("type") in ["user", "assistant"]:
                    # Claude Code format
                    role = msg.get("type")
                    content = extract_text(msg.get("message", {}).get("content", ""))
                    ts = msg.get("timestamp", "")
                else:
                    continue
                    
                if content.strip():  # Skip empty messages
                    messages.append({
                        "role": role, 
                        "content": content,  # Full content, no truncation
                        "ts": ts,
                        "line": current_line
                    })
            except json.JSONDecodeError:
                continue
    
    if not messages and not full:
        print(f"✓ No new messages since line {last_line}")
        return
    
    # Get date from session
    today = datetime.now().strftime("%Y-%m-%d")
    output_file = output_dir / f"{today}.md"
    
    # Write/append transcript
    mode = "w" if full or not output_file.exists() else "a"
    with open(output_file, mode) as f:
        if mode == "w":
            f.write(f"# Transcript {today}\n\n")
            f.write(f"Session: {session_id}\n")
            f.write(f"Source: {sessions_dir}\n")
            f.write(f"Started: {datetime.now().isoformat()}\n\n")
            f.write("---\n\n")
        else:
            f.write(f"\n<!-- append {datetime.now().isoformat()} -->\n\n")
        
        for msg in messages:
            role_icon = "👤" if msg["role"] == "user" else "🤖"
            ts_short = msg["ts"][:19] if msg["ts"] else ""
            f.write(f"**{role_icon} {msg['role']}** ({ts_short})\n")
            f.write(f"{msg['content']}\n\n")
    
    # Update state
    state[session_id] = {
        "last_line": current_line,
        "last_ts": datetime.now().isoformat()
    }
    save_state(output_dir, state)
    
    print(f"✅ Appended {len(messages)} messages to {output_file}")
    print(f"   Total lines processed: {current_line}")

if __name__ == "__main__":
    import sys
    full = "--full" in sys.argv
    agent_id = "main"
    session_id = None
    
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--agent-id" and i < len(sys.argv) - 1:
            agent_id = sys.argv[i + 1]
        elif not arg.startswith("--"):
            session_id = arg
    
    dump_transcript(session_id, full=full, agent_id=agent_id)
