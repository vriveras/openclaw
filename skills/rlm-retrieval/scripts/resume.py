#!/usr/bin/env python3
"""
Load and display current context from memory/
Usage: resume.py

Works on Windows, macOS, and Linux.
"""

import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
MEMORY_DIR = SCRIPT_DIR.parent.parent.parent / "memory"
STATE_FILE = MEMORY_DIR / "context-state.json"


def main():
    if not MEMORY_DIR.exists():
        print(f"Memory directory not found: {MEMORY_DIR}")
        return
    
    print("=" * 60)
    print("CONTEXT MEMORY STATUS")
    print("=" * 60)
    print()
    
    # Load state
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            state = json.load(f)
        
        print(f"Last updated: {state.get('lastUpdated', 'unknown')}")
        print()
        
        # Active topics
        topics = state.get("activeTopics", [])
        print("Active Topics:")
        if topics:
            for t in topics:
                print(f"  • {t}")
        else:
            print("  (none)")
        print()
        
        # Open threads
        threads = state.get("openThreads", [])
        print("Open Threads:")
        if threads:
            for t in threads:
                status = t.get("status", "?")
                tid = t.get("id", "?")
                summary = t.get("summary", "")
                icon = "✓" if status == "done" else "○" if status == "active" else "?"
                print(f"  {icon} [{status}] {tid}")
                if summary:
                    print(f"      {summary}")
        else:
            print("  (none)")
        print()
        
        # Recent decisions
        decisions = state.get("recentDecisions", state.get("decisions", []))[-3:]
        print("Recent Decisions:")
        if decisions:
            for d in decisions:
                date = d.get("date", "?")
                decision = d.get("decision", "?")
                print(f"  • {date}: {decision}")
        else:
            print("  (none)")
        print()
        
        # Entities
        entities = state.get("entities", {})
        if entities:
            print("Known Entities:")
            for name, desc in list(entities.items())[:5]:
                print(f"  • {name}: {desc[:50]}...")
            print()
    else:
        print("No context-state.json found.")
        print()
    
    # Recent conversation chunks
    print("=" * 60)
    print("RECENT CONVERSATIONS")
    print("=" * 60)
    print()
    
    chunks = sorted(MEMORY_DIR.glob("conv-*.md"), reverse=True)[:3]
    if chunks:
        for chunk in chunks:
            print(f"📄 {chunk.name}")
            
            # Try to extract summary
            content = chunk.read_text()
            for line in content.split("\n"):
                if line.startswith("## Summary"):
                    idx = content.find(line)
                    summary_section = content[idx:idx+200]
                    lines = summary_section.split("\n")[1:4]
                    for l in lines:
                        if l.strip():
                            print(f"   {l.strip()}")
                    break
            print()
    else:
        print("(no conversation chunks)")


if __name__ == "__main__":
    main()
