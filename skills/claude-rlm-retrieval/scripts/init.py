#!/usr/bin/env python3
"""
Initialize .claude-memory/ in current project
Usage: init.py [project-type]

Works on Windows, macOS, and Linux.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path(".claude-memory")

def main():
    project_type = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    
    if MEMORY_DIR.exists():
        print(f"{MEMORY_DIR}/ already exists")
        return
    
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    
    state = {
        "lastUpdated": datetime.now().isoformat(),
        "activeTopics": [],
        "openThreads": [],
        "decisions": [],
        "projectContext": {
            "type": project_type,
            "notes": ""
        }
    }
    
    state_file = MEMORY_DIR / "state.json"
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)
    
    print(f"Created {MEMORY_DIR}/")
    print()
    print(json.dumps(state, indent=2))
    print()
    print("Add to .gitignore: .claude-memory/")
    print()
    print("Usage:")
    print("  python save.py 'summary'   - Save conversation chunk")
    print("  python resume.py           - Load context")
    print("  python update-state.py -h  - Update state")

if __name__ == "__main__":
    main()
