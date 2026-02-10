#!/usr/bin/env python3
"""
Load context from .claude-memory/
Usage: resume.py

Works on Windows, macOS, and Linux.
"""

import json
from pathlib import Path

MEMORY_DIR = Path(".claude-memory")

def main():
    if not MEMORY_DIR.exists():
        print("No memory found. Run 'python init.py' to initialize.")
        return
    
    print("=" * 50)
    print("PROJECT CONTEXT")
    print("=" * 50)
    print()
    
    # Show state
    state_file = MEMORY_DIR / "state.json"
    if state_file.exists():
        with open(state_file) as f:
            state = json.load(f)
        
        print(f"Last updated: {state.get('lastUpdated', 'unknown')}")
        print()
        
        print("Active Topics:")
        topics = state.get("activeTopics", [])
        if topics:
            for t in topics:
                print(f"  - {t}")
        else:
            print("  (none)")
        print()
        
        print("Open Threads:")
        threads = state.get("openThreads", [])
        if threads:
            for t in threads:
                status = t.get("status", "?")
                tid = t.get("id", "?")
                summary = t.get("summary", "")
                print(f"  - [{status}] {tid}: {summary}")
        else:
            print("  (none)")
        print()
        
        print("Recent Decisions:")
        decisions = state.get("decisions", [])[-3:]  # Last 3
        if decisions:
            for d in decisions:
                date = d.get("date", "?")
                decision = d.get("decision", "?")
                print(f"  - {date}: {decision}")
        else:
            print("  (none)")
        print()
        
        print("Project:")
        ctx = state.get("projectContext", {})
        print(f"  Type: {ctx.get('type', 'unknown')}")
        if ctx.get("notes"):
            print(f"  Notes: {ctx.get('notes')}")
    else:
        print("No state.json found.")
    
    print()
    print("=" * 50)
    print("RECENT CONVERSATIONS")
    print("=" * 50)
    print()
    
    # Show last 3 conversation chunks
    chunks = sorted(MEMORY_DIR.glob("conv-*.md"), reverse=True)[:3]
    if chunks:
        for chunk in chunks:
            print(f"--- {chunk.name} ---")
            with open(chunk) as f:
                lines = f.readlines()[:20]
                print("".join(lines))
            if len(lines) >= 20:
                print("...")
            print()
    else:
        print("(no conversation history)")

if __name__ == "__main__":
    main()
