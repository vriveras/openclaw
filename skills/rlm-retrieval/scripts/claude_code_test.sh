#!/bin/bash
# Automated Claude Code testing via tmux
# Usage: ./claude_code_test.sh <query>

SESSION="claude-test"
QUERY="$1"
TIMEOUT="${2:-30}"

if [ -z "$QUERY" ]; then
    echo "Usage: $0 <query> [timeout_seconds]"
    exit 1
fi

# Clear any pending input and send query
tmux send-keys -t "$SESSION" C-c
sleep 1
tmux send-keys -t "$SESSION" "$QUERY" Enter

# Wait for response
echo "Sent: $QUERY"
echo "Waiting ${TIMEOUT}s for response..."
sleep "$TIMEOUT"

# Capture output
OUTPUT=$(tmux capture-pane -t "$SESSION" -p -S -100)
echo "$OUTPUT"
