#!/usr/bin/env python3
"""
Save current context to .claude-memory/
Usage: save.py [summary]

Works on Windows, macOS, and Linux.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path(".claude-memory")

def main():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    timestamp = now.isoformat()
    
    # Find next chunk number for today
    existing = list(MEMORY_DIR.glob(f"conv-{date_str}-*.md"))
    next_num = len(existing) + 1
    
    conv_file = MEMORY_DIR / f"conv-{date_str}-{next_num:03d}.md"
    summary = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Session work"
    
    content = f"""# Session: {date_str} #{next_num}

**Time:** {time_str}
**Summary:** {summary}

## Key Changes
(List files modified and what changed)

## Decisions Made
(Document important decisions and reasoning)

## Open Items
- [ ] (Remaining work)

---
*Saved at {timestamp}*
"""
    
    with open(conv_file, "w") as f:
        f.write(content)
    
    print(f"Saved: {conv_file}")
    print("Edit to add session details.")
    
    # Update state timestamp
    state_file = MEMORY_DIR / "state.json"
    if state_file.exists():
        with open(state_file) as f:
            state = json.load(f)
        state["lastUpdated"] = timestamp
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
        print("Updated state.json timestamp")
    else:
        # Create initial state
        state = {
            "lastUpdated": timestamp,
            "activeTopics": [],
            "openThreads": [],
            "decisions": [],
            "projectContext": {"type": "unknown", "notes": ""}
        }
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
        print("Created initial state.json")

if __name__ == "__main__":
    main()
