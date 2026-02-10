#!/bin/bash
# RLM-style search over Clawdbot session transcripts
# Usage: ./search-transcripts.sh "query" [agent_id]

set -e

QUERY="$1"
AGENT_ID="${2:-main}"
SESSIONS_DIR="$HOME/.clawdbot/agents/$AGENT_ID/sessions"

if [ -z "$QUERY" ]; then
    echo "Usage: $0 <query> [agent_id]"
    echo "Example: $0 'authentication flow' main"
    exit 1
fi

# Normalize query: convert spaces to regex that matches space, hyphen, or underscore
# "terminal relay" -> "terminal[-_ ]?relay"
normalize_query() {
    local q="$1"
    # Replace spaces with pattern that matches space/hyphen/underscore/nothing
    echo "$q" | sed 's/ /[-_ ]\\?/g'
}

NORM_QUERY=$(normalize_query "$QUERY")

if [ ! -d "$SESSIONS_DIR" ]; then
    echo "❌ Sessions directory not found: $SESSIONS_DIR"
    exit 1
fi

echo "🔍 Searching for: $QUERY"
echo "📁 Sessions: $SESSIONS_DIR"
echo ""

# Find sessions containing the query (use normalized pattern for flexibility)
MATCHES=$(rg -l -i -e "$NORM_QUERY" "$SESSIONS_DIR"/*.jsonl 2>/dev/null || true)

# Fallback to literal if no matches with pattern
if [ -z "$MATCHES" ]; then
    MATCHES=$(rg -l -i "$QUERY" "$SESSIONS_DIR"/*.jsonl 2>/dev/null || true)
fi

if [ -z "$MATCHES" ]; then
    echo "No matches found."
    exit 0
fi

# Score and sort by recency (newest first)
echo "📋 Matching sessions (newest first):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for f in $MATCHES; do
    DATE=$(head -1 "$f" | jq -r '.timestamp' 2>/dev/null | cut -dT -f1)
    SIZE=$(ls -lh "$f" | awk '{print $5}')
    NAME=$(basename "$f" .jsonl)
    echo "$DATE  $SIZE  $NAME"
done | sort -r | head -10

echo ""
echo "📝 Relevant excerpts:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Extract relevant text from top 3 matches
for f in $(echo "$MATCHES" | head -3); do
    NAME=$(basename "$f" .jsonl)
    echo ""
    echo "── Session: $NAME ──"
    jq -r 'select(.message.role == "assistant" or .message.role == "user") |
           .message.content[]? | 
           select(.type == "text") | 
           .text' "$f" 2>/dev/null | \
        rg -i -e "$NORM_QUERY" -C 1 2>/dev/null | head -10
done
