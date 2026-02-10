---
name: claude-context-memory
description: Persistent per-project memory for Claude Code. Maintains context across sessions using external storage and semantic retrieval. Inspired by RLM paper (arxiv.org/abs/2512.24601).
version: 1.1.0
author: Vicente Rivera
---

# Context Memory for Claude Code

Never lose context between sessions. Based on [Recursive Language Models](https://arxiv.org/abs/2512.24601) — search raw transcripts, don't summarize them.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Claude Code already saves full transcripts automatically:      │
│                                                                 │
│  ~/.claude/projects/<project-path>/                             │
│  ├── <session-uuid>.jsonl    ← Every message, thinking, tools   │
│  └── ...                                                        │
│                                                                 │
│  This skill adds per-project state tracking:                    │
│                                                                 │
│  <project>/.claude-memory/                                      │
│  └── state.json              ← Topics, threads, decisions       │
│                                                                 │
│  RLM approach: Search raw transcripts with heuristics           │
│  (recency, topic matching, keywords) — no summarization.        │
└─────────────────────────────────────────────────────────────────┘
```

**Key insight:** Claude Code stores full transcripts. We just add structured state.

## What This Skill Adds

| Component                   | Purpose                                             |
| --------------------------- | --------------------------------------------------- |
| `.claude-memory/state.json` | Track active topics, threads, decisions per project |
| RLM search                  | Find relevant parts of raw transcripts              |
| 🧠 indicator                | Show when retrieval helped answer                   |

## RLM Indicator

When memory retrieval helps answer a question, show `🧠`:

```
🧠 (via 01-29) We decided to use PKCE for the OAuth flow because it's a public client.

🧠 The auth issue was two sessions ago — you fixed it by adding the Bearer header.
```

Only show when retrieval was meaningful, not for routine session boot.

## Commands

### Help

| Command         | Action                     |
| --------------- | -------------------------- |
| `/context-help` | Explain available commands |

### Recall (shows 🧠 indicator)

| Trigger                      | Action                                 |
| ---------------------------- | -------------------------------------- |
| "what did we decide about X" | Search state.json + transcripts        |
| "what did we change in X"    | Search transcripts for file changes    |
| "continue from yesterday"    | Load state + recent transcript context |
| "where were we"              | Show active threads                    |

### State Management

| Command              | Action                                        |
| -------------------- | --------------------------------------------- |
| `/context-init`      | Initialize `.claude-memory/` for this project |
| `/context-state`     | Show stats + active topics/threads/decisions  |
| `/context-save`      | Update state.json with current context        |
| `/context-resume`    | Load state and continue from last session     |
| `remember this: ...` | Add to state                                  |
| `/context-clear X`   | Mark thread as done                           |

### Search

| Trigger              | Action                        |
| -------------------- | ----------------------------- |
| "context search X"   | RLM search across transcripts |
| "find in sessions X" | Direct JSONL search           |

## Context State Output

When you run `/context-state`, show:

```
🧠 Project Memory Status
━━━━━━━━━━━━━━━━━━━━━━━━
📁 Project: wlxc (rust)

📊 System Stats
   • Session transcripts: 12
   • Total transcript size: 4.2 MB
   • State entries: 14 (3 topics, 4 threads, 7 decisions)
   • Oldest session: 2026-01-20
   • Latest session: 2026-01-30

📍 Active Topics: auth, api-design, containerd

🧵 Open Threads
   • oauth-flow (active) — Implementing OAuth2 PKCE
   • api-routes (active) — REST endpoint design

📋 Recent Decisions
   • 01-30: Use raw transcripts, not summaries
   • 01-29: Use refresh tokens with 7-day expiry
```

## Transcript Location

Claude Code stores transcripts at:

```
~/.claude/projects/<escaped-project-path>/*.jsonl
```

The project path is escaped (e.g., `/home/user/myproject` → `-home-user-myproject`).

### JSONL Format

Each line is a JSON object with:

- `type`: "user", "assistant", "file-history-snapshot", "summary"
- `message.role`: "user" or "assistant"
- `message.content[]`: Array with text/thinking blocks
- `timestamp`: ISO timestamp

### Quick Search

Find keyword in project sessions:

```bash
PROJECT_DIR=$(echo "$PWD" | sed 's|/|-|g; s|^-||')
rg -l "keyword" ~/.claude/projects/$PROJECT_DIR/*.jsonl
```

Extract text from a session:

```bash
jq -r 'select(.type=="user" or .type=="assistant") |
       .message.content[]? | select(.type=="text") | .text' <session>.jsonl
```

## State Schema

```json
{
  "lastUpdated": "2026-01-30T06:35:00Z",
  "activeTopics": ["auth", "api-design"],
  "openThreads": [
    {
      "id": "oauth-flow",
      "status": "active",
      "summary": "Implementing OAuth2 PKCE"
    }
  ],
  "decisions": [
    {
      "date": "2026-01-30",
      "decision": "Use raw transcripts, not summaries",
      "context": "True to RLM paper approach"
    }
  ],
  "projectContext": {
    "type": "rust",
    "framework": "axum"
  }
}
```

## Workflow

### Session Start

1. Check for `.claude-memory/state.json`
2. If exists, load and announce context
3. If user references past context → search transcripts

### During Work

1. Track new topics/decisions mentally
2. When user asks about history → search JSONL with RLM heuristics
3. Show 🧠 when retrieval helped

### Before End

1. Run `/context-save` to update state:
   - Add new topics to activeTopics
   - Update thread statuses
   - Record decisions made
2. Transcripts are already saved automatically

## RLM Search Heuristics

From [arxiv.org/abs/2512.24601](https://arxiv.org/abs/2512.24601):

1. **Score by recency**: Today +3, yesterday +2, this week +1
2. **Score by topic**: Match against active topics +2
3. **Search top candidates only**: Don't scan everything
4. **Constant-size output**: Return top 5 results

## Why Raw Transcripts > Summaries

- **No information loss** — summaries lose detail
- **Automatic** — Claude Code already saves transcripts
- **Flexible** — search for anything, not just what was "curated"
- **True to RLM** — the paper's approach
