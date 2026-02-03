#!/usr/bin/env python3
"""
Save a conversation chunk to memory/conv-*.md
Usage: save-chunk.py [summary]

Works on Windows, macOS, and Linux.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Clawdbot workspace memory directory
SCRIPT_DIR = Path(__file__).parent
MEMORY_DIR = SCRIPT_DIR.parent.parent.parent / "memory"
STATE_FILE = MEMORY_DIR / "context-state.json"


def main():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    tz_str = now.astimezone().tzname() or "UTC"
    timestamp = now.isoformat()
    
    # Find next chunk number for today
    existing = list(MEMORY_DIR.glob(f"conv-{date_str}-*.md"))
    next_num = len(existing) + 1
    
    conv_file = MEMORY_DIR / f"conv-{date_str}-{next_num:03d}.md"
    summary = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Session work"
    
    content = f"""# Conversation: {date_str} Session {next_num}

**Time:** {time_str} {tz_str}
**Topics:** (fill in)
**Channel:** (fill in)

## Summary
{summary}

## Key Exchanges
(Extract important exchanges here)

## Decisions Made
(List any decisions)

## Artifacts Created
(Files, commits, etc.)

## Open Threads
- [ ] (active items)

---
*Saved at {timestamp}*
"""
    
    with open(conv_file, "w") as f:
        f.write(content)
    
    print(f"Created: {conv_file}")
    print("Edit to add conversation details.")
    
    # Update state timestamp
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            state = json.load(f)
        state["lastUpdated"] = timestamp
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
        print("Updated context-state.json timestamp")


if __name__ == "__main__":
    main()
