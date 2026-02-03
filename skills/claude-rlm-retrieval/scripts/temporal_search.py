#!/usr/bin/env python3
"""
Temporal-Aware Session Search

Combines temporal parsing + session filtering + keyword search in one command.
Use this for history queries.

Usage:
    python scripts/temporal_search.py "what did we discuss yesterday about auth?"
    python scripts/temporal_search.py --query "last week's work on wlxc"
    python scripts/temporal_search.py --stats   # Show usage statistics
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Tuple

# Import from sibling modules
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from temporal_parser import parse_temporal_query, filter_sessions_by_date
from enhanced_matching import enhanced_keyword_match, get_related_concepts

# Common words that should be weighted lower in search
COMMON_WORDS = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'can', 'need', 'want', 'like',
    'just', 'also', 'very', 'really', 'actually', 'basically', 'probably',
    'maybe', 'perhaps', 'seems', 'looks', 'think', 'know', 'see', 'get',
    'got', 'make', 'made', 'take', 'took', 'come', 'came', 'go', 'went',
    'say', 'said', 'tell', 'told', 'ask', 'asked', 'use', 'used', 'using',
    'work', 'working', 'worked', 'thing', 'things', 'something', 'anything',
    'everything', 'nothing', 'some', 'any', 'all', 'each', 'every', 'both',
    'few', 'more', 'most', 'other', 'new', 'old', 'good', 'great', 'nice',
    'bad', 'right', 'wrong', 'well', 'still', 'even', 'back', 'now', 'then',
    'here', 'there', 'when', 'where', 'what', 'which', 'who', 'how', 'why',
    'this', 'that', 'these', 'those', 'it', 'its', 'you', 'your', 'we', 'our',
    'they', 'their', 'he', 'she', 'him', 'her', 'his', 'my', 'me', 'i',
    'writing', 'write', 'wrote', 'written', 'read', 'reading',  # Common in transcripts
    'message', 'messages', 'file', 'files', 'code', 'data', 'system',
}

# Index staleness threshold (2 hours in seconds)
INDEX_STALE_THRESHOLD = 2 * 60 * 60

# Usage log file
def _memory_root() -> Path:
    """Prefer project-local .claude-memory when running inside a repo."""
    cwd = Path.cwd()
    if (cwd / ".claude-memory").exists() or (cwd / "CLAUDE.md").exists():
        return cwd / ".claude-memory"
    return SCRIPTS_DIR.parent / "memory"

USAGE_LOG_FILE = _memory_root() / "usage.log"


def log_usage(query: str, results_count: int, sessions_searched: int, exact_matches: int = 0):
    """Log skill usage to usage.log file."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        log_entry = f"{timestamp}\tquery={json.dumps(query)}\tresults={results_count}\tsessions={sessions_searched}\texact={exact_matches}\n"
        
        # Ensure directory exists
        USAGE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(USAGE_LOG_FILE, "a") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Warning: Failed to log usage: {e}", file=sys.stderr)


def show_stats():
    """Show usage statistics from the log file."""
    if not USAGE_LOG_FILE.exists():
        print("📊 No usage data yet (usage.log doesn't exist)")
        return
    
    try:
        with open(USAGE_LOG_FILE, "r") as f:
            lines = f.readlines()
        
        if not lines:
            print("📊 No usage data yet (usage.log is empty)")
            return
        
        total_searches = len(lines)
        total_results = 0
        total_exact = 0
        queries_today = 0
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Parse log entries
        for line in lines:
            try:
                parts = line.strip().split("\t")
                timestamp = parts[0]
                
                if timestamp.startswith(today):
                    queries_today += 1
                
                for part in parts[1:]:
                    if part.startswith("results="):
                        total_results += int(part.split("=")[1])
                    elif part.startswith("exact="):
                        total_exact += int(part.split("=")[1])
            except Exception:
                continue
        
        # Get first and last timestamps
        first_ts = lines[0].split("\t")[0] if lines else "N/A"
        last_ts = lines[-1].split("\t")[0] if lines else "N/A"
        
        print("📊 RLM Retrieval Skill Usage Stats")
        print("=" * 40)
        print(f"   Total searches:      {total_searches}")
        print(f"   Searches today:      {queries_today}")
        print(f"   Total results found: {total_results}")
        print(f"   Exact phrase hits:   {total_exact}")
        print(f"   First used:          {first_ts}")
        print(f"   Last used:           {last_ts}")
        print("=" * 40)
        
        # Show recent queries
        print("\n📜 Last 5 queries:")
        for line in lines[-5:]:
            try:
                parts = line.strip().split("\t")
                ts = parts[0].split("T")[1]  # Just time
                query_part = [p for p in parts if p.startswith("query=")][0]
                query = json.loads(query_part.split("=", 1)[1])
                results = [p for p in parts if p.startswith("results=")][0].split("=")[1]
                print(f"   {ts} | {results} results | {query[:40]}...")
            except Exception:
                continue
                
    except Exception as e:
        print(f"❌ Error reading usage stats: {e}")


def auto_create_index(skill_root: Path, agent_id: str = "main") -> Optional[Dict]:
    """Auto-create the sessions index if missing or stale.

    For Claude Code projects, we prefer `.claude-memory/sessions-index.json`.
    For other environments, we fall back to `<skill>/memory/sessions-index.json`.
    """
    index_path = _memory_root() / "sessions-index.json"
    
    # Check if index exists and is fresh
    needs_refresh = False
    if not index_path.exists():
        print("📝 Index missing, creating...", file=sys.stderr)
        needs_refresh = True
    else:
        # Check staleness
        try:
            mtime = index_path.stat().st_mtime
            age = datetime.now().timestamp() - mtime
            if age > INDEX_STALE_THRESHOLD:
                print(f"📝 Index stale ({age/3600:.1f}h old), refreshing...", file=sys.stderr)
                needs_refresh = True
        except Exception:
            needs_refresh = True
    
    if needs_refresh:
        # Run the indexer
        indexer = SCRIPTS_DIR / "index-sessions.py"
        try:
            result = subprocess.run(
                [sys.executable, str(indexer)],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                print(f"⚠️  Indexer failed: {result.stderr}", file=sys.stderr)
                return None
            print("✅ Index created/refreshed", file=sys.stderr)
        except subprocess.TimeoutExpired:
            print("⚠️  Indexer timed out", file=sys.stderr)
            return None
        except Exception as e:
            print(f"⚠️  Indexer error: {e}", file=sys.stderr)
            return None
    
    # Load the index
    try:
        with open(index_path) as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  Failed to load index: {e}", file=sys.stderr)
        return None


def load_sessions_index(skill_root: Path, agent_id: str = "main", auto_create: bool = True) -> Optional[Dict]:
    """Load the pre-built sessions index, optionally auto-creating if missing."""
    index_path = _memory_root() / "sessions-index.json"
    
    if not index_path.exists():
        if auto_create:
            return auto_create_index(skill_root, agent_id)
        print(f"⚠️  Index not found: {index_path}", file=sys.stderr)
        print(f"   Run: python scripts/index-sessions.py", file=sys.stderr)
        return None
    
    # Check if stale and auto-refresh
    if auto_create:
        try:
            mtime = index_path.stat().st_mtime
            age = datetime.now().timestamp() - mtime
            if age > INDEX_STALE_THRESHOLD:
                return auto_create_index(skill_root, agent_id)
        except Exception:
            pass
    
    with open(index_path) as f:
        return json.load(f)


def get_word_weight(word: str) -> float:
    """Get weight for a word - rare/specific words weighted higher."""
    word_lower = word.lower()
    
    # Very common words get low weight
    if word_lower in COMMON_WORDS:
        return 0.3
    
    # Short words (likely common) get medium weight
    if len(word_lower) <= 3:
        return 0.5
    
    # Technical-looking words (has numbers, underscores, hyphens) get high weight
    if re.search(r'[0-9_-]', word):
        return 2.0
    
    # CamelCase or unusual capitalization = likely specific term
    if re.search(r'[a-z][A-Z]', word) or word[0].isupper():
        return 1.5
    
    # Short lowercase words (4-6 chars) that aren't common = likely project/tool names
    # e.g., wlxc, npm, git, rust, helm, etc.
    if 4 <= len(word_lower) <= 6 and word_lower not in COMMON_WORDS:
        return 1.5
    
    # Default weight
    return 1.0


def extract_topic_hints(query: str) -> List[Tuple[str, float]]:
    """
    Extract potential topic keywords from query with weights.
    Returns list of (word, weight) tuples sorted by weight descending.
    """
    # Remove common question words
    stopwords = {
        'what', 'when', 'where', 'why', 'how', 'who', 'which',
        'did', 'do', 'does', 'was', 'were', 'is', 'are', 'been',
        'have', 'has', 'had', 'the', 'a', 'an', 'about', 'with',
        'we', 'i', 'you', 'they', 'discuss', 'discussed',
        'decide', 'decided', 'talk', 'talked'
    }
    
    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b', query)
    
    weighted = []
    for word in words:
        if word.lower() not in stopwords and len(word) >= 3:
            weight = get_word_weight(word)
            weighted.append((word.lower(), weight))
    
    # Sort by weight descending, take top 5
    weighted.sort(key=lambda x: x[1], reverse=True)
    return weighted[:5]


def check_exact_phrase(query: str, text: str) -> bool:
    """Check if the exact query phrase appears in text."""
    # Normalize whitespace
    query_normalized = ' '.join(query.lower().split())
    text_normalized = ' '.join(text.lower().split())
    return query_normalized in text_normalized


def filter_by_topics(sessions: Dict, topics: List[str]) -> List[str]:
    """Filter sessions that mention any of the given topics."""
    if not topics:
        return list(sessions.keys())
    
    matching = []
    for session_id, info in sessions.items():
        session_topics = [t.lower() for t in info.get("topics", [])]
        if any(t in session_topics for t in topics):
            matching.append(session_id)
    
    return matching


def get_recent_sessions(sessions: Dict, limit: int = 10) -> List[str]:
    """Get most recent sessions by date."""
    sorted_sessions = sorted(
        sessions.items(),
        key=lambda x: x[1].get("timestamp", ""),
        reverse=True
    )
    return [s[0] for s in sorted_sessions[:limit]]


def extract_relevant_snippet(text: str, keywords: List[str], max_len: int = 500) -> str:
    """
    Extract a snippet centered around the first keyword match.
    
    Instead of just returning text[:500], find where keywords appear
    and return context around them.
    """
    text_lower = text.lower()
    
    # Find first keyword occurrence
    best_pos = len(text)  # Default to end if no match
    for kw in keywords:
        pos = text_lower.find(kw.lower())
        if pos != -1 and pos < best_pos:
            best_pos = pos
    
    if best_pos == len(text):
        # No keyword found, fall back to beginning
        return text[:max_len] + ("..." if len(text) > max_len else "")
    
    # Extract snippet centered around the match
    # Give more context before (100 chars) and after (400 chars)
    start = max(0, best_pos - 100)
    end = min(len(text), best_pos + 400)
    
    snippet = text[start:end]
    
    # Add ellipsis if truncated
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    
    return snippet


def search_session_content(
    session_id: str, 
    keywords: List[Tuple[str, float]],  # Now includes weights
    sessions_dir: Path, 
    original_query: str = "",
    max_results: int = 3, 
    enhanced: bool = True
) -> List[Dict]:
    """
    Search a session file for keywords.
    
    If enhanced=True, uses:
    - Substring matching
    - Compound word splitting  
    - Fuzzy matching (Levenshtein ≤ 2)
    - Concept expansion
    - Word weighting (rare words count more)
    - Exact phrase bonus
    """
    session_file = sessions_dir / f"{session_id}.jsonl"
    if not session_file.exists():
        return []
    
    # Extract just the words for matching
    keyword_words = [kw for kw, _ in keywords]
    keyword_weights = {kw: w for kw, w in keywords}
    
    results = []
    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    # Claude Code formats vary by version:
                    # - Newer: {type:"message", message:{role, content:[...]}}
                    # - Current (2.1.x): {type:"user"|"assistant", message:{role, content:"..."}}
                    if record.get("type") not in ("message", "user", "assistant"):
                        continue
                    
                    msg = record.get("message", {})
                    if msg.get("role") not in ("user", "assistant"):
                        continue
                    
                    # Extract text
                    content = msg.get("content", [])
                    text = ""
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text += block.get("text", "") + " "
                    
                    # Check for keyword matches with weighting
                    match_count = 0
                    weighted_score = 0.0
                    match_info = []
                    
                    if enhanced:
                        # Use enhanced matching - count and weight matches
                        for kw in keyword_words:
                            is_match, terms = enhanced_keyword_match(
                                kw, text,
                                use_substring=True,
                                use_compound=True,
                                use_fuzzy=True,
                                use_concepts=True
                            )
                            if is_match:
                                match_count += 1
                                weight = keyword_weights.get(kw, 1.0)
                                weighted_score += weight
                                match_info.extend(terms[:2])
                    else:
                        # Basic matching (fallback)
                        text_lower = text.lower()
                        for kw in keyword_words:
                            if kw.lower() in text_lower:
                                match_count += 1
                                weight = keyword_weights.get(kw, 1.0)
                                weighted_score += weight
                    
                    # Exact phrase bonus - significantly boost if exact query appears
                    exact_phrase_bonus = 0.0
                    if original_query and check_exact_phrase(original_query, text):
                        exact_phrase_bonus = 10.0  # Big bonus for exact match
                        match_info.insert(0, "EXACT_PHRASE")
                    
                    # Require at least 1 keyword to match
                    # But score higher when more keywords match
                    # ADVERSARIAL PROTECTION: If we have high-weight keywords,
                    # at least one of them must match (not just common words)
                    min_matches = 1
                    
                    # ADVERSARIAL PROTECTION: Require EXACT match of high-weight keywords
                    # Concept expansion can cause false positives (wlxc→windows→steakhouse)
                    # Only allow concepts if the original term also appears
                    high_weight_keywords = [kw for kw, w in keywords if w > 1.0]
                    if high_weight_keywords:
                        # At least one important keyword must match DIRECTLY (not via concepts)
                        high_weight_matched = False
                        for kw in high_weight_keywords:
                            # Check for direct match (substring, compound, fuzzy) but NOT concepts
                            is_match, _ = enhanced_keyword_match(
                                kw, text,
                                use_substring=True,
                                use_compound=True,
                                use_fuzzy=True,
                                use_concepts=False  # Disable concept expansion for adversarial check
                            ) if enhanced else (kw.lower() in text.lower(), [])
                            if is_match:
                                high_weight_matched = True
                                break
                        if not high_weight_matched:
                            continue  # Skip - only concept matches, not the actual keyword
                    
                    matched = match_count >= min_matches
                    
                    if matched:
                        # Final score = weighted keyword score + exact phrase bonus
                        # Bonus for matching MORE keywords
                        coverage_bonus = (match_count / len(keyword_words)) * 5.0 if keyword_words else 0
                        final_score = weighted_score + exact_phrase_bonus + coverage_bonus
                        
                        # Extract snippet around the matched keyword (not just first 500 chars)
                        snippet = extract_relevant_snippet(text, keyword_words, max_len=500)
                        
                        results.append({
                            "session": session_id,
                            "role": msg.get("role"),
                            "text": snippet,
                            "timestamp": record.get("timestamp", ""),
                            "match_info": match_info[:3] if match_info else None,
                            "match_count": match_count,
                            "match_score": final_score,
                            "exact_phrase": exact_phrase_bonus > 0
                        })
                        
                        if len(results) >= max_results:
                            return results
                
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"  Warning: Error reading {session_file}: {e}", file=sys.stderr)
    
    return results


def temporal_search(query: str, agent_id: str = "main", auto_index: bool = True) -> Dict:
    """
    Perform temporal-aware search.
    
    Returns dict with:
    - temporal: parsed temporal info (if any)
    - topics: extracted topic hints
    - sessions_searched: which sessions were searched
    - results: matching content
    """
    skill_root = SCRIPTS_DIR.parent
    
    # Load index (auto-create/refresh if needed)
    index = load_sessions_index(skill_root, agent_id, auto_create=auto_index)
    if not index:
        return {"error": "No sessions index found and auto-create failed"}
    
    sessions = index.get("sessions", {})
    sessions_dir = Path(index.get("sessionsDir", ""))
    
    if not sessions_dir.exists():
        # Fallback (older index format / non-Claude env)
        sessions_dir = Path.home() / ".clawdbot" / "agents" / agent_id / "sessions"
        # Claude Code project fallback
        cwd = Path.cwd()
        # Claude Code uses a leading '-' in its escaping ("/a/b" -> "-a-b").
        escaped = str(cwd).replace("/", "-")
        claude_dir = Path.home() / ".claude" / "projects" / escaped
        if claude_dir.exists():
            sessions_dir = claude_dir
    
    # Parse temporal reference
    temporal = parse_temporal_query(query)
    
    # Extract topic hints with weights
    topics_weighted = extract_topic_hints(query)
    topics = [t for t, _ in topics_weighted]
    
    # Filter sessions
    candidate_ids = list(sessions.keys())
    
    if temporal:
        # Filter by date range
        candidate_ids = filter_sessions_by_date(sessions, temporal["start"], temporal["end"])
        print(f"📅 Temporal filter: {temporal['match']} → {temporal['start']} to {temporal['end']}")
        print(f"   Filtered to {len(candidate_ids)} sessions")
    
    # Topic filtering: use as hint to prioritize, but don't exclude
    # (content may mention term without it being in top 10 indexed topics)
    topic_matched = []
    topic_unmatched = []
    if topics:
        topic_matched = filter_by_topics(
            {k: sessions[k] for k in candidate_ids if k in sessions},
            topics
        )
        topic_unmatched = [s for s in candidate_ids if s not in topic_matched]
        print(f"🏷️  Topic hints: {topics}")
        print(f"   {len(topic_matched)} topic matches + {len(topic_unmatched)} to search")
        # Prioritize topic matches but include others for full-text search
        candidate_ids = topic_matched + topic_unmatched
    
    # Fall back to recent if no filters applied
    if not temporal and not topics:
        candidate_ids = get_recent_sessions(sessions, limit=20)
        print(f"📆 No filters, using {len(candidate_ids)} most recent sessions")
    
    # Search sessions: prioritize topic matches, then search more for full coverage
    # Cap at 30 sessions to balance thoroughness vs performance
    all_results = []
    for session_id in candidate_ids[:30]:
        session_info = sessions.get(session_id, {})
        keywords = topics_weighted if topics_weighted else [(w, 1.0) for w in query.split()[:5]]
        
        matches = search_session_content(
            session_id, 
            keywords, 
            sessions_dir,
            original_query=query
        )
        for match in matches:
            match["date"] = session_info.get("date", "unknown")
            all_results.append(match)
    
    # Sort by match score (higher = better match)
    # Exact phrase matches will be at top due to bonus
    all_results.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    
    return {
        "query": query,
        "temporal": temporal,
        "topics": topics,
        "topics_weighted": topics_weighted,
        "sessions_searched": len(candidate_ids),
        "sessions_total": len(sessions),
        "results": all_results[:10]  # Top 10 results
    }


def main():
    parser = argparse.ArgumentParser(description="Temporal-aware session search")
    parser.add_argument("query", nargs="*", help="Search query")
    parser.add_argument("--query", "-q", dest="query_flag", help="Search query (alternative)")
    parser.add_argument("--agent-id", default="main", help="Agent ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-auto-index", action="store_true", help="Don't auto-create index")
    parser.add_argument("--stats", action="store_true", help="Show usage statistics")
    parser.add_argument("--no-log", action="store_true", help="Don't log this search")
    args = parser.parse_args()
    
    # Handle stats request
    if args.stats:
        show_stats()
        return
    
    query = args.query_flag or " ".join(args.query)
    if not query:
        parser.print_help()
        return
    
    print(f"🔍 Searching: \"{query}\"\n")
    
    result = temporal_search(query, args.agent_id, auto_index=not args.no_auto_index)
    
    if args.json:
        print(json.dumps(result, indent=2))
        # Log usage even for JSON output
        if not args.no_log and "error" not in result:
            exact_count = sum(1 for r in result.get("results", []) if r.get("exact_phrase"))
            log_usage(query, len(result.get("results", [])), result.get("sessions_searched", 0), exact_count)
        return
    
    if "error" in result:
        print(f"❌ {result['error']}")
        return
    
    # Log usage
    if not args.no_log:
        exact_count = sum(1 for r in result.get("results", []) if r.get("exact_phrase"))
        log_usage(query, len(result.get("results", [])), result.get("sessions_searched", 0), exact_count)
    
    print(f"\n📊 Searched {result['sessions_searched']}/{result['sessions_total']} sessions")
    print(f"   Found {len(result['results'])} matches\n")
    
    if not result["results"]:
        print("No matches found.")
        return
    
    for i, r in enumerate(result["results"], 1):
        date = r.get("date", "?")
        role = "👤" if r["role"] == "user" else "🤖"
        exact = "⭐" if r.get("exact_phrase") else ""
        print(f"{'─'*60}")
        print(f"🧠 ({date}) {role}{exact} {r['text'][:200]}...")
    
    print(f"{'─'*60}")


if __name__ == "__main__":
    main()
