#!/usr/bin/env python3
"""
Update context-state.json with current context.

Usage:
    python update-state.py                          # Interactive - prompts for updates
    python update-state.py --topic "new-topic"      # Add a topic
    python update-state.py --decision "We chose X"  # Add a decision
    python update-state.py --entity "X=description" # Add an entity
    python update-state.py --thread "id:status:summary" # Add/update thread
    python update-state.py --show                   # Just show current state

Cross-platform: works on Linux, macOS, Windows.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
MEMORY_DIR = SCRIPT_DIR.parent.parent.parent / "memory"
STATE_FILE = MEMORY_DIR / "context-state.json"


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
        "pendingFollowups": []
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
    
    print()


def add_topic(state: dict, topic: str):
    """Add a topic to active topics."""
    topics = state.setdefault('activeTopics', [])
    if topic not in topics:
        topics.append(topic)
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
    # Keep only last 10 decisions
    state['recentDecisions'] = decisions[:10]
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


def main():
    parser = argparse.ArgumentParser(description="Update context-state.json")
    parser.add_argument('--show', action='store_true', help="Show current state")
    parser.add_argument('--topic', type=str, help="Add an active topic")
    parser.add_argument('--decision', type=str, help="Add a decision")
    parser.add_argument('--context', type=str, help="Context for decision")
    parser.add_argument('--entity', type=str, help="Add entity as 'name=description'")
    parser.add_argument('--thread', type=str, help="Add thread as 'id:status:summary'")
    parser.add_argument('--remove-topic', type=str, help="Remove a topic")
    
    args = parser.parse_args()
    state = load_state()
    modified = False
    
    if args.show:
        show_state(state)
        return
    
    if args.topic:
        add_topic(state, args.topic)
        modified = True
    
    if args.decision:
        add_decision(state, args.decision, args.context)
        modified = True
    
    if args.entity:
        if '=' in args.entity:
            name, desc = args.entity.split('=', 1)
            add_entity(state, name.strip(), desc.strip())
            modified = True
        else:
            print("❌ Entity format: name=description")
    
    if args.thread:
        parts = args.thread.split(':', 2)
        if len(parts) == 3:
            add_thread(state, parts[0], parts[1], parts[2])
            modified = True
        else:
            print("❌ Thread format: id:status:summary")
    
    if args.remove_topic:
        topics = state.get('activeTopics', [])
        if args.remove_topic in topics:
            topics.remove(args.remove_topic)
            print(f"➖ Removed topic: {args.remove_topic}")
            modified = True
    
    if modified:
        save_state(state)
        show_state(state)
    elif not args.show:
        # No args - show help
        parser.print_help()
        print("\n💡 Quick examples:")
        print('  python update-state.py --show')
        print('  python update-state.py --topic "auth-refactor"')
        print('  python update-state.py --decision "Use OAuth2 PKCE"')
        print('  python update-state.py --entity "wlxc=Windows/Linux container runtime"')


if __name__ == "__main__":
    main()
