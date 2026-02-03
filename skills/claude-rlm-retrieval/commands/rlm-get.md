# RLM Get

**Mandatory** retrieval before answering history/status questions.

Usage:
- `/rlm-get what did we decide about auth last week?`
- `/rlm-get where are we with wlxc?`

Steps:
1. Run the transcript dump (best effort):
   - `python3 skills/rlm-retrieval/scripts/dump_transcript.py`

2. Run temporal search:
   - `python3 skills/rlm-retrieval/scripts/temporal_search.py "$ARGUMENTS"`

3. Summarize results *with citations* (session/date + snippet) and answer the user.

Rules:
- If retrieval returns nothing, say so and ask a narrowing question.
- Do not guess.
- When you used retrieved evidence, prefix your answer with 🧠.
