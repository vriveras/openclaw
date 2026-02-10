#!/usr/bin/env python3
"""Install claude-rlm-retrieval skill globally for Claude Code.

Usage:
  python3 install.py [--copy] [--quiet]

This installs the skill into ~/.claude/skills/rlm-retrieval (symlink by default)
so commands/scripts can be referenced consistently.

Note: project-local wiring still matters:
- You typically copy this skill into <project>/skills/rlm-retrieval
- And enable Claude Code hooks in ~/.claude/settings.json
"""

import os
import shutil
import sys
from pathlib import Path


def log(msg: str, quiet: bool = False):
    if not quiet:
        print(msg)


def main() -> None:
    quiet = "--quiet" in sys.argv
    skill_dir = Path(__file__).parent.resolve()

    # Claude config directory
    if sys.platform == "win32":
        claude_dir = Path(os.environ.get("USERPROFILE", "")) / ".claude"
    else:
        claude_dir = Path.home() / ".claude"

    install_dir = claude_dir / "skills" / "rlm-retrieval"

    log("Installing claude-rlm-retrieval skill...", quiet)
    log(f"  From: {skill_dir}", quiet)
    log(f"  To:   {install_dir}", quiet)
    log("", quiet)

    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "skills").mkdir(exist_ok=True)

    # Remove existing
    if install_dir.exists() or install_dir.is_symlink():
        if install_dir.is_symlink():
            install_dir.unlink()
        else:
            shutil.rmtree(install_dir)
        log("Removed existing installation", quiet)

    use_copy = "--copy" in sys.argv

    if use_copy:
        shutil.copytree(skill_dir, install_dir)
        log(f"Copied to {install_dir}", quiet)
    else:
        try:
            install_dir.symlink_to(skill_dir, target_is_directory=True)
            log(f"Linked to {install_dir}", quiet)
        except OSError:
            log("Symlink failed, copying instead...", quiet)
            shutil.copytree(skill_dir, install_dir)
            log(f"Copied to {install_dir}", quiet)

    log("", quiet)
    log("Next steps (per project):", quiet)
    log("  1) Copy skill into your repo:", quiet)
    log("     cp -r ~/.claude/skills/rlm-retrieval <project>/skills/rlm-retrieval", quiet)
    log("  2) Create project memory dir:", quiet)
    log("     mkdir -p <project>/.claude-memory/transcripts", quiet)
    log("  3) Enable hooks:", quiet)
    log("     Copy ~/.claude/skills/rlm-retrieval/hooks/hooks.json into ~/.claude/settings.json", quiet)
    log("  4) Test:", quiet)
    log("     python3 <project>/skills/rlm-retrieval/scripts/temporal_search.py \"recent work\"", quiet)


if __name__ == "__main__":
    main()
