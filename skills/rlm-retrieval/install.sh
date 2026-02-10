#!/bin/bash
# One-liner installer for Context Memory (Clawdbot)
# Usage: curl -fsSL https://raw.githubusercontent.com/vriveras/clawdbot-context-memory/master/install.sh | bash

set -e

REPO="https://github.com/vriveras/clawdbot-context-memory.git"

# Find Clawdbot workspace (check common locations)
if [ -n "$CLAWDBOT_WORKSPACE" ]; then
    WORKSPACE="$CLAWDBOT_WORKSPACE"
elif [ -d "$HOME/clawd/skills" ]; then
    WORKSPACE="$HOME/clawd"
elif [ -d "$HOME/clawdbot/skills" ]; then
    WORKSPACE="$HOME/clawdbot"
elif [ -d "./skills" ]; then
    WORKSPACE="."
else
    echo "❌ Could not find Clawdbot workspace."
    echo "   Set CLAWDBOT_WORKSPACE or run from your workspace directory."
    exit 1
fi

SKILL_DIR="$WORKSPACE/skills/context-memory"

echo "🧠 Installing Context Memory for Clawdbot..."
echo "   Workspace: $WORKSPACE"

# Clone or update
if [ -d "$SKILL_DIR" ]; then
    echo "📦 Updating existing installation..."
    cd "$SKILL_DIR"
    git pull --quiet
else
    echo "📦 Cloning repository..."
    git clone --quiet "$REPO" "$SKILL_DIR"
fi

echo ""
echo "✅ Installed to: $SKILL_DIR"
echo ""
echo "🚀 Restart Clawdbot to load the skill."
echo ""
echo "📖 Commands:"
echo "   context help     — Show available commands"
echo "   context state    — Show memory status"
echo "   context save     — Save conversation checkpoint"
echo "   where were we    — Resume from last session"
