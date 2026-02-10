#!/bin/bash
# One-liner installer for Claude RLM Retrieval
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/vriveras/claude-rlm-retrieval/master/install.sh | bash

set -e

REPO="https://github.com/vriveras/claude-rlm-retrieval.git"
SKILL_DIR="${HOME}/.claude/skills/rlm-retrieval"

echo "🧠 Installing Claude RLM Retrieval..."

# Clone or update
if [ -d "$SKILL_DIR" ]; then
  echo "📦 Updating existing installation..."
  cd "$SKILL_DIR"
  git pull --quiet
else
  echo "📦 Cloning repository..."
  mkdir -p "$(dirname "$SKILL_DIR")"
  git clone --quiet "$REPO" "$SKILL_DIR"
  cd "$SKILL_DIR"
fi

# Run Python installer (best effort)
if [ -f "install.py" ]; then
  python3 install.py --quiet 2>/dev/null || true
fi

echo ""
echo "✅ Installed to: $SKILL_DIR"
echo ""
echo "Next: enable hooks (recommended)"
echo "  Copy hooks from: $SKILL_DIR/hooks/hooks.json"
echo "  Into: ~/.claude/settings.json"
echo ""
echo "Per project:"
echo "  cp -r $SKILL_DIR <project>/skills/rlm-retrieval"
echo "  mkdir -p <project>/.claude-memory/transcripts"
