---
name: rlm-retrieval
description: Hybrid memory system with RLM retrieval (rlm-get, rlm-state, rlm-check). Enhanced matching (substring, compound, fuzzy, concepts). Achieves 99.8% accuracy on 2000 tests. Uses both semantic search (embeddings) and RLM keyword search for maximum recall.
version: 3.0.0
author: Vicente Rivera
---

# RLM Retrieval for OpenClaw

## Quick Setup (Full Vicente Config)

To replicate the complete setup with compaction survival:

### 1. Copy skill to your workspace
```bash
cp -r skills/rlm-retrieval ~/your-workspace/skills/
```

### 2. Add transcript dump cron job (every 5 min)
```bash
# Via OpenClaw chat or cron tool
openclaw cron add --name "Transcript dump" \
  --every 5m \
  --session main \
  --payload '{"kind":"systemEvent","text":"TRANSCRIPT_DUMP: Run python3 skills/rlm-retrieval/scripts/dump_transcript.py silently."}'
```

### 3. Update HEARTBEAT.md
Add to your workspace `HEARTBEAT.md`:
```markdown
### Transcript Dump (CRITICAL - every heartbeat)
Dump current session transcript to survive compaction:
\`\`\`bash
python3 skills/rlm-retrieval/scripts/dump_transcript.py
\`\`\`
Output: `memory/transcripts/YYYY-MM-DD.md`

After compaction, READ this file to recover full context!

### Session Index Refresh (every few hours)
\`\`\`bash
python3 skills/rlm-retrieval/scripts/index-sessions.py --agent-id main
\`\`\`
```

### 4. Update AGENTS.md compaction protocol
Add to your `AGENTS.md`:
```markdown
### ⚠️ Compaction Protocol (CRITICAL)
When you notice context has been compacted:

**IMMEDIATELY (MANDATORY on first response after compaction):**
1. Run session indexer:
   \`\`\`bash
   python3 skills/rlm-retrieval/scripts/index-sessions.py --agent-id main
   \`\`\`
2. Search for lost context using RLM retrieval:
   \`\`\`bash
   python3 skills/rlm-retrieval/scripts/temporal_search.py "what were we working on"
   \`\`\`
3. Read today's transcript: `memory/transcripts/YYYY-MM-DD.md`
4. **DO NOT guess** what you were doing — USE RLM-GET to retrieve it

**Signs of compaction:**
- Summary says "Summary unavailable due to context limits"
- You have no memory of recent conversation
- First message looks like continuation of unknown work
```

### 5. Test it
```bash
# Dump current transcript
python3 skills/rlm-retrieval/scripts/dump_transcript.py

# Search for context (rlm-get)
python3 skills/rlm-retrieval/scripts/temporal_search.py "recent work"

# Check stats
python3 skills/rlm-retrieval/scripts/temporal_search.py --stats
```

---

Never lose conversation context. Combines multiple complementary approaches:
1. **Enhanced RLM search** — substring, compound splitting, fuzzy (Levenshtein), concepts
2. **Semantic search** (OpenClaw's built-in `memory_search`) — catches paraphrases
3. **Temporal filtering** — understands "yesterday", "last week", filters sessions

## Commands

| Command | Alias | Purpose |
|---------|-------|---------|
| `rlm-get` | **primary** | Mandatory state retrieval before answering history questions |
| `rlm-state` | alias | Show context state, active topics, threads |
| `rlm-check` | alias | Validate retrieval accuracy |

**Accuracy: 99.8%** on 2000 test cases (see [README](README.md) for benchmarks).

## Core Principle

> "Long content should not be fed into the neural network directly but treated as part of the environment the LLM can symbolically interact with." — RLM Paper

## Enhanced Matching (v2.0)

The skill uses four matching strategies that combine for 99.8% accuracy:

### 1. Substring Matching
Query word contained in content word:
```
"Glicko" matches "Glicko-2 rating system"
"App" matches "AppData folder"
```

### 2. Compound Splitting
Splits camelCase, kebab-case, snake_case:
```
"ReadMessageItem" → read, message, item
"context-memory" → context, memory
"HostWindowsContainer" → host, windows, container
```

### 3. Fuzzy Matching (Levenshtein ≤ 2)
Catches typos and close variants:
```
"postgres" ≈ "PostgreSQL"
"javascrpt" ≈ "javascript" (typo)
```

### 4. Concept Index
Related terms expansion:
```
"glicko" → rating, chess, elo, leaderboard
"oauth" → auth, authentication, token, security
"wlxc" → container, windows, linux, containerd
```

### Latency Tradeoff

| Metric | Basic | Enhanced | 
|--------|-------|----------|
| Latency | 0.02ms | 14.78ms |
| Recall | 74% | **100%** |

+26% recall for +14.76ms — worth it for accurate retrieval.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       HYBRID RETRIEVAL                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Query arrives                                                  │
│       ↓                                                         │
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │ 🔮 Semantic Search  │    │ 🔍 RLM Keyword      │            │
│  │ (memory_search)     │    │ (JSONL grep/jq)    │            │
│  │                     │    │                     │            │
│  │ • Paraphrases       │    │ • Exact matches     │            │
│  │ • Conceptual sim    │    │ • Code blocks       │            │
│  │ • Fuzzy intent      │    │ • URLs, names       │            │
│  └──────────┬──────────┘    └──────────┬──────────┘            │
│             └──────────┬───────────────┘                       │
│                        ↓                                        │
│              Merge & dedupe results                             │
│                        ↓                                        │
│              Return with source indicator                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ~/.clawdbot/agents/<agentId>/sessions/                         │
│  ├── sessions.json          ← Index of all sessions             │
│  ├── <session-id>.jsonl     ← Raw transcript (AUTOMATIC)        │
│  └── ...                                                        │
│                                                                 │
│  memory/                                                        │
│  ├── context-state.json     ← Structured state (THIS SKILL)     │
│  ├── MEMORY.md              ← Long-term curated (existing)      │
│  └── YYYY-MM-DD.md          ← Daily logs (existing)             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## What This Skill Adds

| Component | Purpose |
|-----------|---------|
| `context-state.json` | Track active topics, threads, decisions |
| `sessions-index.json` | Pre-indexed session metadata for fast lookup |
| Hybrid search | Semantic + RLM for maximum recall |
| Temporal parsing | Understands "yesterday", "last week", etc. |
| Source indicators | 🔮 semantic, 🔍 RLM, 🧠 both |

## Retrieval Indicators

Show which retrieval method found the answer:

| Indicator | Meaning |
|-----------|---------|
| 🔮 | Found via **semantic search** (memory_search embeddings) |
| 🔍 | Found via **RLM retrieval** (rlm-get / keyword search) |
| 🧠 | Found via **both methods** (highest confidence) |

**Examples:**
```
🔮 (semantic) We discussed authentication patterns yesterday.

🔍 (RLM) The exact error was: `ECONNREFUSED 127.0.0.1:5432`

🧠 (both) We decided to use tmux because it handles WSL well.
```

Only show indicators when retrieval was meaningful, not for routine session boot.

## MANDATORY: Temporal-Aware Retrieval

**When user asks about history, ALWAYS do this first:**

```bash
# 1. Parse temporal intent (run in your head or exec)
python3 scripts/temporal_parser.py "user's query"

# 2. If temporal found → filter sessions by date
#    Load memory/sessions-index.json
#    Filter to sessions matching date range

# 3. Search ONLY filtered sessions, not all
```

**Example:**
```
User: "what did we work on yesterday?"

1. Parse: "yesterday" → 2026-01-29
2. Load index → find sessions with date=2026-01-29
3. Search only those 5 sessions (not all 106)
4. Return with 🧠 (01-29) prefix
```

**If no temporal reference found:** Fall back to recency (most recent 5-10 sessions).

## Triggers & Commands

### Help
| Trigger | Action |
|---------|--------|
| "context help" | Explain available commands |

### Recall (shows indicator) — USE TEMPORAL FILTERING
| Trigger | Action |
|---------|--------|
| "what did we decide about X" | **Parse temporal** → filter sessions → search |
| "what did we discuss about X" | **Parse temporal** → filter sessions → search |
| "when did we X" | **Parse temporal** → search for timeline/dates |
| "continue from yesterday" | **Parse "yesterday"** → load those sessions |
| "where were we" | Show active threads (recent sessions) |

### State Management
| Trigger | Action |
|---------|--------|
| "context state" | Show stats + active topics/threads/decisions |
| "context save" | Update state.json with current topics/threads |
| "remember this: ..." | Add to state (decision, entity, or followup) |
| "context clear X" | Mark thread as done |

### Search
| Trigger | Action |
|---------|--------|
| "context search X" | RLM search across transcripts |
| "find in sessions X" | Direct JSONL search |

## Context State Output

When you run `context state`, show:

```
🧠 Context Memory Status
━━━━━━━━━━━━━━━━━━━━━━━━
📊 System Stats
   • Session transcripts: 47
   • Total transcript size: 12.3 MB
   • State entries: 12 (4 topics, 3 threads, 5 decisions)
   • Oldest session: 2026-01-15
   • Latest session: 2026-01-30

📍 Active Topics: context-memory, terminal-relay, wlxc

🧵 Open Threads
   • rlm-indicator (active) — Adding subtle 🧠 indicator
   • context-memory-skill (active) — Refactoring to use raw transcripts

📋 Recent Decisions
   • 01-30: Use raw JSONL transcripts, not curated chunks
   • 01-30: Use 🧠 emoji as RLM indicator
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
      "summary": "Implementing OAuth2 PKCE",
      "sessionId": "abc123"
    }
  ],
  "recentDecisions": [
    {
      "date": "2026-01-30",
      "decision": "Use raw transcripts, not summaries",
      "context": "True to RLM paper approach"
    }
  ],
  "entities": {
    "wlxc": "Windows/Linux container runtime"
  }
}
```

## Temporal-Aware Retrieval

As the transcript set grows, smart session selection becomes critical. Don't search everything — use temporal parsing and the session index to narrow down candidates.

### Session Index

Build/update the index (run periodically or before heavy retrieval):

```bash
python scripts/index-sessions.py --agent-id main --output memory/sessions-index.json
```

**Index structure (`memory/sessions-index.json`):**
```json
{
  "lastUpdated": "2026-01-30T09:30:00Z",
  "agentId": "main",
  "stats": {
    "totalSessions": 47,
    "totalMessages": 2340,
    "dateRange": {"oldest": "2026-01-15", "newest": "2026-01-30"}
  },
  "sessions": {
    "abc123": {
      "date": "2026-01-29",
      "time": "14:30",
      "topics": ["auth", "oauth", "wlxc"],
      "messageCount": 47
    }
  }
}
```

### Temporal Query Parsing

The skill recognizes natural language time references:

| Query | Parsed As |
|-------|-----------|
| "what did we do yesterday?" | 2026-01-29 |
| "last week's discussions" | 2026-01-20 to 2026-01-26 |
| "3 days ago" | 2026-01-27 |
| "on Monday" | Most recent Monday |
| "in January" | 2026-01-01 to 2026-01-31 |
| "recently" | Last 7 days |

**Test temporal parsing:**
```bash
python scripts/temporal_parser.py "what did we work on yesterday?"
```

### Retrieval Flow with Temporal Awareness

```
┌─────────────────────────────────────────────────────────────────┐
│                  TEMPORAL-AWARE RETRIEVAL                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Parse query for temporal intent                             │
│     "what did we discuss yesterday about auth?"                 │
│           ↓                                                     │
│     temporal: yesterday (2026-01-29)                           │
│     topic: auth                                                 │
│                                                                 │
│  2. Load session index                                          │
│     memory/sessions-index.json                                  │
│                                                                 │
│  3. Filter sessions                                             │
│     - By date if temporal found: sessions from 2026-01-29       │
│     - By topic if mentioned: sessions with "auth" in topics     │
│     - By recency as fallback                                    │
│                                                                 │
│  4. Search only filtered sessions                               │
│     Instead of 47 sessions → search 3 sessions                  │
│                                                                 │
│  5. Return results with context                                 │
│     🧠 (01-29) We decided to use OAuth2 PKCE for the auth flow │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### When Handling History Queries

Follow this process:

1. **Check for temporal references:**
   ```
   Query: "what did we work on last week?"
   → Temporal: last week (2026-01-20 to 2026-01-26)
   → Filter sessions by date range
   ```

2. **Check for topic references:**
   ```
   Query: "what did we decide about authentication?"
   → Topic: authentication
   → Filter sessions with "auth" in topics
   ```

3. **Use conversation context:**
   ```
   Current topic: wlxc containers
   Query: "what was the error we saw?"
   → Boost sessions with "wlxc" topic
   ```

4. **Fall back to recency:**
   ```
   Query: "where were we?"
   → No temporal/topic hints
   → Search most recent 5 sessions
   ```

### Maintaining the Index

**On heartbeat (recommended):**
```python
# In HEARTBEAT.md or periodic task
# Re-index if >1 hour since last update
if sessions_index_stale():
    run("python scripts/index-sessions.py")
```

**Manual refresh:**
```bash
python scripts/index-sessions.py --agent-id main
```

## RLM Search Over Transcripts

### How It Works

```python
# 1. Parse temporal intent + load index
temporal = parse_temporal_query(query)
index = load_sessions_index()

# 2. Filter sessions
if temporal:
    candidates = filter_by_date(index, temporal.start, temporal.end)
elif topic_hint:
    candidates = filter_by_topic(index, topic_hint)
else:
    candidates = get_recent_sessions(index, limit=10)

# 3. Score remaining by relevance
for session in candidates:
    score = 0
    if session.age_days == 0: score += 3.0   # Today
    if session.age_days == 1: score += 2.0   # Yesterday
    if topic in session.topics: score += 2.0  # Topic match

# 4. Search only top candidates
top_sessions = sorted(candidates, key=score)[:5]

# 5. Extract relevant messages
for session in top_sessions:
    messages = search_jsonl(session, query)
    results.extend(messages[:3])

# 6. Return constant-size output
return results[:5]
```

### Quick JSONL Search

Find keyword in all sessions:
```bash
AGENT_ID="main"  # from Runtime line in system prompt
rg -l "keyword" ~/.clawdbot/agents/$AGENT_ID/sessions/*.jsonl
```

Extract matching messages:
```bash
jq -r 'select(.message.role == "assistant") | 
       select(.message.content[]?.text | contains("keyword")) |
       .message.content[]? | select(.type == "text") | .text' \
    ~/.clawdbot/agents/$AGENT_ID/sessions/<session>.jsonl
```

Search sessions from a specific date (using index):
```bash
# With jq and the index
jq -r '.sessions | to_entries[] | select(.value.date == "2026-01-29") | .key' \
    memory/sessions-index.json
```

## Hybrid Retrieval Workflow

### When User Asks About History

```python
def hybrid_search(query):
    results = []
    
    # 1. Semantic search (built-in memory_search)
    semantic = memory_search(query)
    for r in semantic:
        results.append({"text": r, "source": "semantic", "score": r.score})
    
    # 2. RLM keyword search (direct JSONL)
    rlm = jsonl_search(query, recency_weighted=True)
    for r in rlm:
        results.append({"text": r, "source": "rlm", "score": r.score})
    
    # 3. Merge and dedupe
    merged = dedupe_by_content(results)
    
    # 4. Boost items found by both methods
    for item in merged:
        if item.found_by_both:
            item.source = "both"
            item.score *= 1.5
    
    return sorted(merged, key=lambda x: x.score, reverse=True)[:5]
```

### Session Start
1. Load `memory/context-state.json`
2. Announce active topics and open threads
3. If user references past context → **hybrid search** (semantic + RLM)

### During Conversation
1. Track new topics/decisions mentally
2. When user asks about history → **hybrid search**
3. Show indicator (🔮/🔍/🧠) based on which method found the answer

### Before Compaction / End
1. Update `context-state.json`:
   - Add new topics to activeTopics
   - Update thread statuses
   - Record decisions made
2. State persists; transcripts are already saved automatically

## Validation Modes

For benchmarking and continuous improvement, run tests with different modes:

```bash
# Test RLM only (keyword search)
python tests/run-baseline-1000.py --mode rlm

# Test semantic only (memory_search embeddings)
python tests/run-baseline-1000.py --mode semantic

# Test hybrid (both methods combined)
python tests/run-baseline-1000.py --mode hybrid

# Compare all modes
python tests/run-baseline-1000.py --mode compare
```

**Mode comparison output:**
```
Mode       | Accuracy | Strengths
-----------|----------|------------------------------------------
rlm        | 81%      | Exact matches, code, URLs, names
semantic   | ??%      | Paraphrases, conceptual similarity
hybrid     | ??%      | Best of both (expected highest)
```

This allows continued iteration on the RLM approach while measuring hybrid gains.

## Compaction Survival: Transcript Dump

OpenClaw/Claude may compact (truncate) long sessions. When this happens, earlier context is lost. This skill includes a **transcript dump** system to survive compaction.

### How It Works

The `dump_transcript.py` script:
1. Reads the current session from `~/.openclaw/agents/<agentId>/sessions/`
2. Appends new messages to `memory/transcripts/YYYY-MM-DD.md`
3. Tracks state in `memory/transcripts/.state.json` to only append new content
4. Full messages preserved — no truncation

### Setup (OpenClaw)

**1. Add cron job for automatic dumps every 5 minutes:**
```bash
# Via chat or cron tool
openclaw cron add --name "Transcript dump" \
  --every 5m \
  --session main \
  --text "TRANSCRIPT_DUMP: Run python3 skills/context-memory/scripts/dump_transcript.py silently."
```

**2. Add to HEARTBEAT.md:**
```markdown
### Transcript Dump (CRITICAL - every heartbeat)
Dump current session transcript to survive compaction:
\`\`\`bash
python3 skills/context-memory/scripts/dump_transcript.py
\`\`\`
Output: `memory/transcripts/YYYY-MM-DD.md` (full conversation log)

After compaction, READ this file to recover full context!
```

**3. Add to AGENTS.md compaction protocol:**
```markdown
### ⚠️ Compaction Protocol (CRITICAL)
When you notice context has been compacted:

**IMMEDIATELY:**
1. Run transcript dump to capture any recent context
2. Read `memory/transcripts/YYYY-MM-DD.md` for today's full conversation
3. Run session indexer: `python3 skills/context-memory/scripts/index-sessions.py --agent-id main`
4. Search for lost context if needed

**Signs of compaction:**
- Summary says "Summary unavailable due to context limits"
- You have no memory of recent conversation
- First message looks like continuation of unknown work
```

### Manual Usage

```bash
# Append new messages since last dump
python3 scripts/dump_transcript.py

# Full re-dump (overwrites, starts fresh)
python3 scripts/dump_transcript.py --full

# Specific session
python3 scripts/dump_transcript.py <session-id>
```

### Recovery After Compaction

When you wake up with truncated context:
```python
# 1. Read today's transcript
with open("memory/transcripts/2026-01-31.md") as f:
    full_context = f.read()

# 2. You now have the full conversation to pick up from
```

The transcript file is append-only markdown — easy to read and search.

---

## Benchmarking & Performance

Measure search performance and compare methods:

### Quick Benchmark

Run 100 test queries and measure latency:

```bash
python scripts/benchmark-search.py --queries 100 --test-queries
```

**Output:**
```
📊 Benchmark Report: scan
============================================================
Queries: 100/100 successful

⏱️  Latency Statistics
   Mean:    517.02 ms
   Median:  466.36 ms
   P50:     466.36 ms
   P95:    1156.07 ms
   P99:    1422.10 ms
```

### Compare Methods (A/B Testing)

Compare OLD (scan) vs NEW (indexed) search:

```bash
# Full comparison with 50 queries
python scripts/compare-search.py --queries 50 --test-queries

# Single query comparison
python scripts/compare-search.py --query "rlm retrieval latency"

# Save detailed results
python scripts/compare-search.py --queries 100 --output comparison.json
```

**Output:**
```
📊 Comparison Report: OLD (scan) vs NEW (indexed)
============================================================
🚀 Speedup Factor: 7.5x
🎯 Quality Metrics
   Recall:        100.00%
   Precision:     100.00%
   F1 Score:      100.00%
✅ QUALITY CHECK PASSED: No significant regression
```

### Benchmark Options

| Option | Description |
|--------|-------------|
| `--queries N` | Number of queries to run (default: 100) |
| `--method {scan,indexed,both}` | Which method to benchmark |
| `--test-queries` | Use predefined test query set |
| `--query-file FILE` | Load queries from file (one per line) |
| `--warmup N` | Number of warmup runs before timing |
| `--output FILE` | Save JSON results to file |
| `--verbose` | Show per-query details |

### Test Query Set

The benchmark includes 100+ test queries covering:
- Technical terms: "rlm retrieval latency", "Glicko chess rating"
- Temporal: "what did we do yesterday"
- Compound: "OpenClaw fork changes", "context memory skill"
- Fuzzy/adversarial: "SEO fixes blog page"
- Projects: "wlxc container runtime", "compaction survival"

---

## Why Raw Transcripts > Summaries

From the RLM paper:

1. **No information loss** — summaries lose detail
2. **Search is cheap** — RLM heuristics find relevant parts fast
3. **Automatic** — Clawdbot already saves transcripts
4. **Flexible** — search for anything, not just what was "summarized"

The only thing we add is `context-state.json` — a small structured index of what's active.
