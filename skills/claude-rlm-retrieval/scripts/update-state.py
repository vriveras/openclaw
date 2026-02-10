#!/usr/bin/env python3
"""
Update .claude-memory/state.json with current context.

Usage:
    python update-state.py                          # Show help
    python update-state.py --show                   # Show current state
    python update-state.py --topic "new-topic"      # Add a topic
    python update-state.py --decision "We chose X"  # Add a decision
    python update-state.py --entity "X=description" # Add an entity
    python update-state.py --thread "id:status:summary" # Add/update thread
    python update-state.py --init                   # Initialize memory dir

Cross-platform: works on Linux, macOS, Windows.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Claude Code uses .claude-memory in project root
MEMORY_DIR = Path(".claude-memory")
STATE_FILE = MEMORY_DIR / "state.json"


def load_state() -> dict:
    """Load existing state or create default."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "lastUpdated": None,
        "activeTopics": [],
        "openThreads": [],
        "recentDecisions": [],
        "entities": {},
        "pendingFollowups": [],
        "projectContext": {"type": "unknown", "notes": ""}
    }


def save_state(state: dict):
    """Save state with updated timestamp."""
    state["lastUpdated"] = datetime.now().astimezone().isoformat()
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)
    print(f"✅ Saved to {STATE_FILE}")


def show_state(state: dict):
    """Display current state."""
    print("\n🧠 Context Memory State")
    print("━" * 40)
    print(f"Last updated: {state.get('lastUpdated', 'never')}")
    
    print(f"\n📍 Active Topics: {', '.join(state.get('activeTopics', [])) or 'none'}")
    
    threads = state.get('openThreads', [])
    if threads:
        print(f"\n🧵 Threads ({len(threads)}):")
        for t in threads[:5]:
            status = "✅" if t.get('status') == 'done' else "🔄"
            print(f"   {status} {t.get('id', '?')}: {t.get('summary', '')[:50]}")
    
    decisions = state.get('recentDecisions', [])
    if decisions:
        print(f"\n📋 Recent Decisions ({len(decisions)}):")
        for d in decisions[:5]:
            print(f"   • {d.get('date', '?')}: {d.get('decision', '')[:60]}")
    
    entities = state.get('entities', {})
    if entities:
        print(f"\n📦 Entities ({len(entities)}):")
        for name, desc in list(entities.items())[:5]:
            print(f"   • {name}: {desc[:50]}")
    
    followups = state.get('pendingFollowups', [])
    if followups:
        print(f"\n⏳ Pending ({len(followups)}):")
        for f in followups[:3]:
            print(f"   • {f}")
    
    ctx = state.get('projectContext', {})
    if ctx.get('type') != 'unknown' or ctx.get('notes'):
        print(f"\n📂 Project: {ctx.get('type', 'unknown')}")
        if ctx.get('notes'):
            print(f"   {ctx.get('notes')[:100]}")
    
    print()


def add_topic(state: dict, topic: str):
    """Add a topic to active topics."""
    topics = state.setdefault('activeTopics', [])
    if topic not in topics:
        topics.insert(0, topic)
        topics[:] = topics[:10]  # Keep max 10
        print(f"➕ Added topic: {topic}")
    else:
        print(f"ℹ️  Topic already exists: {topic}")


def add_decision(state: dict, decision: str, context: str = None):
    """Add a decision."""
    decisions = state.setdefault('recentDecisions', [])
    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "decision": decision,
        "reversible": True
    }
    if context:
        entry["context"] = context
    decisions.insert(0, entry)
    # Keep only last 20 decisions
    state['recentDecisions'] = decisions[:20]
    print(f"➕ Added decision: {decision[:60]}")


def add_entity(state: dict, name: str, description: str):
    """Add or update an entity."""
    entities = state.setdefault('entities', {})
    entities[name] = description
    print(f"➕ Added entity: {name} = {description[:50]}")


def add_thread(state: dict, thread_id: str, status: str, summary: str):
    """Add or update a thread."""
    threads = state.setdefault('openThreads', [])
    
    # Update existing or add new
    for t in threads:
        if t.get('id') == thread_id:
            t['status'] = status
            t['summary'] = summary
            t['lastTouchedAt'] = datetime.now().astimezone().isoformat()
            print(f"✏️  Updated thread: {thread_id}")
            return
    
    threads.append({
        "id": thread_id,
        "status": status,
        "summary": summary,
        "startedAt": datetime.now().astimezone().isoformat(),
        "lastTouchedAt": datetime.now().astimezone().isoformat()
    })
    print(f"➕ Added thread: {thread_id}")


def add_followup(state: dict, followup: str):
    """Add a pending followup."""
    followups = state.setdefault('pendingFollowups', [])
    followups.append(followup)
    followups[:] = followups[-10:]  # Keep last 10
    print(f"➕ Added followup: {followup[:50]}")


def set_project(state: dict, ptype: str = None, notes: str = None):
    """Set project context."""
    ctx = state.setdefault('projectContext', {"type": "unknown", "notes": ""})
    if ptype:
        ctx['type'] = ptype
        print(f"📂 Project type: {ptype}")
    if notes:
        ctx['notes'] = notes
        print(f"📝 Project notes updated")


def main():
    parser = argparse.ArgumentParser(description="Update .claude-memory/state.json")
    parser.add_argument('--show', '-s', action='store_true', help="Show current state")
    parser.add_argument('--init', '-i', action='store_true', help="Initialize memory directory")
    parser.add_argument('--topic', '-t', action='append', help="Add an active topic")
    parser.add_argument('--decision', '-d', action='append', help="Add a decision")
    parser.add_argument('--context', '-c', type=str, help="Context for decision")
    parser.add_argument('--entity', '-e', action='append', help="Add entity as 'name=description'")
    parser.add_argument('--thread', '-r', action='append', help="Add thread as 'id:status:summary'")
    parser.add_argument('--followup', '-f', action='append', help="Add pending followup")
    parser.add_argument('--remove-topic', '-T', action='append', help="Remove a topic")
    parser.add_argument('--project-type', '-p', type=str, help="Set project type")
    parser.add_argument('--project-note', '-n', type=str, help="Set project notes")
    
    args = parser.parse_args()
    state = load_state()
    modified = False
    
    if args.show:
        show_state(state)
        return
    
    if args.init:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        save_state(state)
        print(f"✅ Initialized {MEMORY_DIR}/")
        print("💡 Add to .gitignore: .claude-memory/")
        return
    
    if args.topic:
        for t in args.topic:
            add_topic(state, t)
        modified = True
    
    if args.decision:
        for d in args.decision:
            add_decision(state, d, args.context)
        modified = True
    
    if args.entity:
        for e in args.entity:
            if '=' in e:
                name, desc = e.split('=', 1)
                add_entity(state, name.strip(), desc.strip())
                modified = True
            else:
                print(f"❌ Entity format: name=description")
    
    if args.thread:
        for t in args.thread:
            parts = t.split(':', 2)
            if len(parts) >= 2:
                tid = parts[0]
                status = parts[1]
                summary = parts[2] if len(parts) > 2 else ""
                add_thread(state, tid, status, summary)
                modified = True
            else:
                print("❌ Thread format: id:status[:summary]")
    
    if args.followup:
        for f in args.followup:
            add_followup(state, f)
        modified = True
    
    if args.remove_topic:
        topics = state.get('activeTopics', [])
        for t in args.remove_topic:
            if t in topics:
                topics.remove(t)
                print(f"➖ Removed topic: {t}")
                modified = True
    
    if args.project_type or args.project_note:
        set_project(state, args.project_type, args.project_note)
        modified = True
    
    if modified:
        save_state(state)
        show_state(state)
    elif not args.show and not args.init:
        parser.print_help()
        print("\n💡 Quick examples:")
        print('  python update-state.py --show')
        print('  python update-state.py --init')
        print('  python update-state.py --topic "auth-refactor"')
        print('  python update-state.py --decision "Use OAuth2 PKCE"')
        print('  python update-state.py --entity "wlxc=Container runtime"')


if __name__ == "__main__":
    main()
