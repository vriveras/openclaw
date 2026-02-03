# HEARTBEAT.md

## Periodic Tasks

### Transcript Dump (CRITICAL - every heartbeat)
Dump current session transcript to survive compaction:
```bash
python3 skills/rlm-retrieval/scripts/dump_transcript.py
```
Output: `memory/transcripts/YYYY-MM-DD.md` (full conversation log)

After compaction, READ this file to recover full context!

### Session Index Refresh (every few hours)
Check if session index is stale and refresh:
```bash
# Only if >2 hours since last update
python skills/rlm-retrieval/scripts/index-sessions.py --agent-id main
```
Last indexed: check `skills/rlm-retrieval/memory/sessions-index.json` → `lastUpdated`

**CRITICAL:** Also run index refresh BEFORE any compaction to ensure context isn't lost!

### Context State Update (after significant work)
If we've done meaningful work since last update, refresh `memory/context-state.json`:
- Add new decisions made
- Update active topics
- Track new entities/projects
- Mark threads as done/active

Check `lastUpdated` field - if >4 hours stale AND work was done, update it.

### Other Checks (rotate through)
- Email inbox (if configured)
- Calendar events
- Urgent mentions
