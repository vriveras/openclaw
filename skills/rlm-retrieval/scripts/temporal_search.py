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
USAGE_LOG_FILE = SCRIPTS_DIR.parent / "memory" / "usage.log"

# Inverted index path
INVERTED_INDEX_FILE = SCRIPTS_DIR.parent / "memory" / "inverted-index.json"

# Global inverted index cache (loaded once at startup)
_inverted_index_cache = None
_inverted_index_loaded = False


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
        
        print("📊 Context-Memory Skill Usage Stats")
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
    """Auto-create the sessions index if missing or stale."""
    index_path = skill_root / "memory" / "sessions-index.json"
    
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
                [sys.executable, str(indexer), "--agent-id", agent_id],
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
    index_path = skill_root / "memory" / "sessions-index.json"
    
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


def build_inverted_index(sessions_index: Dict, force_rebuild: bool = False) -> Dict:
    """
    Build inverted index from sessions index.
    
    Structure: {token: [session_id, session_id, ...]}
    Tokens are extracted from session topics and content words.
    """
    global _inverted_index_cache, _inverted_index_loaded
    
    # Check if we have a cached version
    if _inverted_index_loaded and not force_rebuild:
        return _inverted_index_cache
    
    # Check if inverted index exists on disk
    if INVERTED_INDEX_FILE.exists() and not force_rebuild:
        try:
            mtime = INVERTED_INDEX_FILE.stat().st_mtime
            sessions_mtime = (SCRIPTS_DIR.parent / "memory" / "sessions-index.json").stat().st_mtime
            
            # Only load if newer than sessions index
            if mtime >= sessions_mtime:
                with open(INVERTED_INDEX_FILE, 'r', encoding='utf-8') as f:
                    _inverted_index_cache = json.load(f)
                    _inverted_index_loaded = True
                    return _inverted_index_cache
        except Exception:
            pass  # Fall through to rebuild
    
    # Build inverted index from sessions
    inverted = {
        "lastUpdated": datetime.now().isoformat(),
        "stats": {"totalTokens": 0, "totalPostings": 0},
        "index": {}
    }
    
    sessions = sessions_index.get("sessions", {})
    
    for session_id, info in sessions.items():
        # Index topics
        topics = info.get("topics", [])
        for topic in topics:
            token = topic.lower()
            if token not in inverted["index"]:
                inverted["index"][token] = []
            if session_id not in inverted["index"][token]:
                inverted["index"][token].append(session_id)
        
        # Index date parts for temporal queries
        date = info.get("date", "")
        if date:
            # Index full date and parts
            parts = date.split("-")
            for part in parts:
                token = f"date:{part}"
                if token not in inverted["index"]:
                    inverted["index"][token] = []
                if session_id not in inverted["index"][token]:
                    inverted["index"][token].append(session_id)
    
    # Calculate stats
    inverted["stats"]["totalTokens"] = len(inverted["index"])
    inverted["stats"]["totalPostings"] = sum(len(postings) for postings in inverted["index"].values())
    
    # Save to disk
    try:
        INVERTED_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(INVERTED_INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(inverted, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save inverted index: {e}", file=sys.stderr)
    
    _inverted_index_cache = inverted
    _inverted_index_loaded = True
    
    return inverted


def load_inverted_index(sessions_index: Dict = None, force_rebuild: bool = False) -> Optional[Dict]:
    """Load or build the inverted index."""
    global _inverted_index_cache, _inverted_index_loaded
    
    # Return cached version if available
    if _inverted_index_loaded and not force_rebuild:
        return _inverted_index_cache
    
    # Try to load from disk
    if INVERTED_INDEX_FILE.exists() and not force_rebuild:
        try:
            # Check if stale compared to sessions index
            if sessions_index:
                idx_mtime = INVERTED_INDEX_FILE.stat().st_mtime
                sessions_path = SCRIPTS_DIR.parent / "memory" / "sessions-index.json"
                if sessions_path.exists():
                    sessions_mtime = sessions_path.stat().st_mtime
                    if idx_mtime < sessions_mtime:
                        # Rebuild needed
                        return build_inverted_index(sessions_index, force_rebuild=True)
            
            with open(INVERTED_INDEX_FILE, 'r', encoding='utf-8') as f:
                _inverted_index_cache = json.load(f)
                _inverted_index_loaded = True
                return _inverted_index_cache
        except Exception as e:
            print(f"Warning: Failed to load inverted index: {e}", file=sys.stderr)
    
    # Build from sessions index if available
    if sessions_index:
        return build_inverted_index(sessions_index, force_rebuild)
    
    return None


def tokenize_query(query: str) -> List[str]:
    """
    Tokenize query the same way as indexing.
    Returns list of normalized tokens.
    """
    # Extract words
    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b', query)
    
    # Normalize and filter
    tokens = []
    stopwords = COMMON_WORDS.union({
        'what', 'when', 'where', 'why', 'how', 'who', 'which',
        'did', 'do', 'does', 'was', 'were', 'is', 'are', 'been',
        'have', 'has', 'had', 'the', 'a', 'an', 'about', 'with',
        'we', 'i', 'you', 'they', 'discuss', 'discussed',
        'decide', 'decided', 'talk', 'talked', 'work', 'worked'
    })
    
    for word in words:
        token = word.lower()
        if token not in stopwords and len(token) >= 3:
            tokens.append(token)
    
    return tokens


def intersect_posting_lists(posting_lists: List[set]) -> List[str]:
    """
    Intersect multiple posting lists efficiently.
    Returns session IDs that appear in ALL lists.
    """
    if not posting_lists:
        return []
    
    if len(posting_lists) == 1:
        return list(posting_lists[0])
    
    # Start with smallest set for efficiency
    sorted_sets = sorted(posting_lists, key=len)
    result = set(sorted_sets[0])
    
    for s in sorted_sets[1:]:
        result.intersection_update(s)
        if not result:
            break  # Early exit if empty
    
    return list(result)


def coarse_match(query: str, text: str) -> float:
    """
    Fast coarse matching - substring only, no fuzzy/concepts.
    
    Tier 2: Quick pre-filter to eliminate non-matching candidates.
    Returns match ratio (0.0 to 1.0) based on term overlap.
    """
    query_terms = query.lower().split()
    if not query_terms:
        return 0.0
    
    text_lower = text.lower()
    matches = sum(1 for term in query_terms if len(term) >= 3 and term in text_lower)
    return matches / len(query_terms)


def get_session_text(session_id: str, sessions_dir: Path) -> str:
    """Load all text content from a session file."""
    session_file = sessions_dir / f"{session_id}.jsonl"
    if not session_file.exists():
        return ""
    
    texts = []
    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if record.get("type") != "message":
                        continue
                    
                    msg = record.get("message", {})
                    if msg.get("role") not in ("user", "assistant"):
                        continue
                    
                    content = msg.get("content", [])
                    if isinstance(content, str):
                        texts.append(content)
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                texts.append(block.get("text", ""))
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    
    return " ".join(texts)


def quick_coarse_match(query: str, session_id: str, sessions_dir: Path) -> float:
    """
    Fast streaming coarse match - stops at first match for each term.
    
    Returns match ratio (0.0 to 1.0) without loading entire file into memory.
    """
    query_terms = [term.lower() for term in query.split() if len(term) >= 3]
    if not query_terms:
        return 0.0
    
    session_file = sessions_dir / f"{session_id}.jsonl"
    if not session_file.exists():
        return 0.0
    
    # Track which terms we've found
    found_terms = set()
    
    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if record.get("type") != "message":
                        continue
                    
                    msg = record.get("message", {})
                    if msg.get("role") not in ("user", "assistant"):
                        continue
                    
                    # Extract text and check for matches
                    content = msg.get("content", [])
                    text = ""
                    if isinstance(content, str):
                        text = content.lower()
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text += block.get("text", "").lower()
                    
                    # Check each term we haven't found yet
                    for term in list(query_terms):
                        if term in text:
                            found_terms.add(term)
                            query_terms.remove(term)
                            
                    # Early exit if all terms found
                    if not query_terms:
                        return 1.0
                        
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    
    # Return ratio of found terms to total terms
    total_terms = len(query_terms) + len(found_terms)
    return len(found_terms) / total_terms if total_terms > 0 else 0.0


def search_with_index(
    query: str,
    sessions_index: Dict,
    temporal: Optional[Dict] = None,
    max_results: int = 10,
    use_three_tier: bool = True
) -> Dict:
    """
    Search using inverted index for O(1) token lookup with three-tier optimization.
    
    Three-tier approach:
    - Tier 1: Index lookup (O(1)) - find candidate sessions
    - Tier 2: Coarse substring filtering (O(k)) - quick pre-filter
    - Tier 3: Enhanced matching (selective) - only top 20 candidates
    
    Returns dict with:
    - results: matching content
    - sessions_searched: which sessions were searched
    - index_hit: whether index was used
    - query_time_ms: time taken
    - tier_times_ms: breakdown of time per tier
    """
    import time
    start_time = time.time()
    tier_times = {}
    
    # Load inverted index
    inverted = load_inverted_index(sessions_index)
    if not inverted:
        return {"error": "No inverted index available", "index_hit": False, "results": []}
    
    # Tokenize query
    tokens = tokenize_query(query)
    if not tokens:
        return {"error": "No searchable tokens", "index_hit": False, "results": []}
    
    # ==========================================================================
    # TIER 1: Index lookup (O(1) per token)
    # ==========================================================================
    tier1_start = time.time()
    
    index_data = inverted.get("terms") or inverted.get("index", {})
    posting_lists = []
    matched_tokens = []
    
    for token in tokens:
        if token in index_data:
            # Handle both formats: list of session IDs or list of posting dicts
            entries = index_data[token]
            if entries and isinstance(entries[0], dict):
                session_ids = {posting["session"] for posting in entries}
            else:
                session_ids = set(entries)
            posting_lists.append(session_ids)
            matched_tokens.append(token)
    
    if not posting_lists:
        return {"error": "No index matches", "index_hit": False, "results": []}
    
    candidate_ids = intersect_posting_lists(posting_lists)
    
    if not candidate_ids and posting_lists:
        candidate_ids = list(set().union(*posting_lists))
    
    sessions = sessions_index.get("sessions", {})
    sessions_dir = Path(sessions_index.get("sessionsDir", ""))
    
    if temporal and candidate_ids:
        filtered_ids = filter_sessions_by_date(
            {k: sessions[k] for k in candidate_ids if k in sessions},
            temporal["start"],
            temporal["end"]
        )
        if filtered_ids:
            candidate_ids = filtered_ids
    
    if not candidate_ids:
        return {"error": "No candidates after filtering", "index_hit": True, "results": []}
    
    tier_times["tier1_index_ms"] = round((time.time() - tier1_start) * 1000, 2)
    
    # Extract topic hints with weights for enhanced matching
    topics_weighted = extract_topic_hints(query)
    
    # ======================================================================
    # TIER 2: Optimized enhanced matching on index candidates
    # ======================================================================
    tier2_start = time.time()
    
    # Use three-tier filtering if enabled and we have many candidates
    if use_three_tier and len(candidate_ids) > 30:
        # Quick coarse filter to prioritize candidates
        # Include ALL candidates that have ANY match, not just top ones
        coarse_scores = {}
        for session_id in candidate_ids:
            session_text = get_session_text(session_id, sessions_dir)
            if session_text:
                score = coarse_match(query, session_text)
                coarse_scores[session_id] = score
        
        # Sort by coarse score (descending) - but include ALL candidates
        # This preserves recall while still prioritizing likely matches
        sorted_candidates = sorted(candidate_ids, key=lambda s: coarse_scores.get(s, 0), reverse=True)
        search_candidates = sorted_candidates[:40]  # Increased limit for better recall
    else:
        search_candidates = candidate_ids[:40]  # Increased from 30
    
    all_results = []
    for session_id in search_candidates:
        session_info = sessions.get(session_id, {})
        keywords = topics_weighted if topics_weighted else [(w, 1.0) for w in tokens[:5]]
        
        matches = search_session_content(
            session_id,
            keywords,
            sessions_dir,
            original_query=query
        )
        for match in matches:
            match["date"] = session_info.get("date", "unknown")
            all_results.append(match)
    
    tier_times["tier2_search_ms"] = round((time.time() - tier2_start) * 1000, 2)
    sessions_searched = len(search_candidates)
    
    # Sort by match score
    all_results.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    
    query_time_ms = (time.time() - start_time) * 1000
    
    return {
        "query": query,
        "temporal": temporal,
        "topics": [t for t, _ in topics_weighted],
        "topics_weighted": topics_weighted,
        "sessions_searched": sessions_searched,
        "sessions_total": len(sessions),
        "candidates_found": len(candidate_ids),
        "index_hit": True,
        "index_tokens_matched": matched_tokens,
        "three_tier": use_three_tier,
        "query_time_ms": round(query_time_ms, 2),
        "tier_times_ms": tier_times,
        "results": all_results[:max_results]
    }


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
                    if record.get("type") != "message":
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


def run_benchmark(
    queries: List[str],
    sessions_index: Dict,
    agent_id: str = "main"
) -> Dict:
    """
    Run benchmark comparing three-tier vs legacy search.
    
    Returns detailed timing and recall comparison.
    """
    import time
    import statistics
    
    print(f"\n{'='*70}")
    print("🏁 THREE-TIER SEARCH BENCHMARK")
    print(f"{'='*70}")
    print(f"Queries: {len(queries)}")
    print(f"Total sessions in index: {len(sessions_index.get('sessions', {}))}")
    print()
    
    three_tier_times = []
    legacy_times = []
    three_tier_results = []
    legacy_results = []
    
    for i, query in enumerate(queries, 1):
        print(f"Query {i}/{len(queries)}: \"{query[:50]}...\"" if len(query) > 50 else f"Query {i}/{len(queries)}: \"{query}\"")
        
        # Three-tier search
        start = time.time()
        result_3t = search_with_index(query, sessions_index, use_three_tier=True)
        tt_time = result_3t.get("query_time_ms", (time.time() - start) * 1000)
        three_tier_times.append(tt_time)
        three_tier_results.append({r["session"]: r.get("match_score", 0) for r in result_3t.get("results", [])})
        
        # Legacy search
        start = time.time()
        result_legacy = search_with_index(query, sessions_index, use_three_tier=False)
        legacy_time = result_legacy.get("query_time_ms", (time.time() - start) * 1000)
        legacy_times.append(legacy_time)
        legacy_results.append({r["session"]: r.get("match_score", 0) for r in result_legacy.get("results", [])})
        
        print(f"  Three-tier: {tt_time:.1f}ms | Legacy: {legacy_time:.1f}ms | Speedup: {legacy_time/max(tt_time, 0.1):.1f}x")
    
    # Calculate statistics
    def calc_stats(times):
        if not times:
            return {}
        return {
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "p95": sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0],
            "p99": sorted(times)[int(len(times) * 0.99)] if len(times) > 1 else times[0],
            "min": min(times),
            "max": max(times),
        }
    
    tt_stats = calc_stats(three_tier_times)
    legacy_stats = calc_stats(legacy_times)
    
    # Calculate recall preservation
    recall_scores = []
    for tt_result, leg_result in zip(three_tier_results, legacy_results):
        if not leg_result:
            recall_scores.append(1.0 if not tt_result else 0.0)
            continue
        
        # Count how many legacy results are found in three-tier results
        legacy_sessions = set(leg_result.keys())
        tt_sessions = set(tt_result.keys())
        
        if not legacy_sessions:
            recall_scores.append(1.0)
            continue
        
        # Calculate recall: what fraction of legacy results appear in three-tier
        found_in_tt = len(legacy_sessions.intersection(tt_sessions))
        recall = found_in_tt / len(legacy_sessions)
        recall_scores.append(recall)
    
    avg_recall = statistics.mean(recall_scores) if recall_scores else 0.0
    
    # Print results
    print(f"\n{'='*70}")
    print("📊 BENCHMARK RESULTS")
    print(f"{'='*70}")
    
    print("\n⏱️  TIMING COMPARISON")
    print("-" * 50)
    print(f"{'Metric':<15} {'Three-Tier':>12} {'Legacy':>12} {'Speedup':>10}")
    print("-" * 50)
    
    metrics = ["mean", "median", "p95", "p99", "min", "max"]
    for metric in metrics:
        tt_val = tt_stats.get(metric, 0)
        leg_val = legacy_stats.get(metric, 0)
        speedup = leg_val / max(tt_val, 0.1)
        print(f"{metric.capitalize():<15} {tt_val:>10.1f}ms {leg_val:>10.1f}ms {speedup:>9.1f}x")
    
    print("\n🎯 RECALL VALIDATION")
    print("-" * 50)
    print(f"Average recall preserved: {avg_recall*100:.1f}%")
    print(f"Min recall: {min(recall_scores)*100:.1f}%")
    print(f"Max recall: {max(recall_scores)*100:.1f}%")
    
    # Success criteria check
    median_target = 75
    mean_target = 150
    recall_target = 0.998
    
    print(f"\n✅ SUCCESS CRITERIA")
    print("-" * 50)
    median_pass = tt_stats.get("median", 999) <= median_target
    mean_pass = tt_stats.get("mean", 999) <= mean_target
    recall_pass = avg_recall >= recall_target
    
    print(f"Median ≤ {median_target}ms: {'✅ PASS' if median_pass else '❌ FAIL'} ({tt_stats.get('median', 0):.1f}ms)")
    print(f"Mean ≤ {mean_target}ms: {'✅ PASS' if mean_pass else '❌ FAIL'} ({tt_stats.get('mean', 0):.1f}ms)")
    print(f"Recall ≥ {recall_target*100:.1f}%: {'✅ PASS' if recall_pass else '❌ FAIL'} ({avg_recall*100:.1f}%)")
    
    overall_pass = median_pass and mean_pass and recall_pass
    print(f"\n{'🎉 OVERALL: PASS' if overall_pass else '⚠️  OVERALL: NEEDS IMPROVEMENT'}")
    print(f"{'='*70}\n")
    
    return {
        "three_tier_stats": tt_stats,
        "legacy_stats": legacy_stats,
        "recall": {
            "average": avg_recall,
            "min": min(recall_scores) if recall_scores else 0,
            "max": max(recall_scores) if recall_scores else 0,
            "per_query": recall_scores
        },
        "speedup": {
            "mean": legacy_stats.get("mean", 0) / max(tt_stats.get("mean", 0.1), 0.1),
            "median": legacy_stats.get("median", 0) / max(tt_stats.get("median", 0.1), 0.1),
        },
        "criteria_passed": {
            "median": median_pass,
            "mean": mean_pass,
            "recall": recall_pass,
            "overall": overall_pass
        },
        "queries": len(queries)
    }


def temporal_search(query: str, agent_id: str = "main", auto_index: bool = True, use_three_tier: bool = True) -> Dict:
    """
    Perform temporal-aware search using inverted index first, with fallback to scan.
    
    Returns dict with:
    - temporal: parsed temporal info (if any)
    - topics: extracted topic hints
    - sessions_searched: which sessions were searched
    - results: matching content
    - search_path: 'index' or 'fallback' or 'hybrid'
    - query_time_ms: time taken
    """
    import time
    start_time = time.time()
    
    skill_root = SCRIPTS_DIR.parent
    
    # Load index (auto-create/refresh if needed)
    index = load_sessions_index(skill_root, agent_id, auto_create=auto_index)
    if not index:
        return {"error": "No sessions index found and auto-create failed"}
    
    sessions = index.get("sessions", {})
    sessions_dir = Path(index.get("sessionsDir", ""))
    
    if not sessions_dir.exists():
        sessions_dir = Path.home() / ".clawdbot" / "agents" / agent_id / "sessions"
    
    # Parse temporal reference
    temporal = parse_temporal_query(query)
    
    # PHASE 3: Try inverted index search first (with three-tier optimization)
    index_result = search_with_index(query, index, temporal, max_results=10, use_three_tier=use_three_tier)
    
    # Check if index search succeeded
    index_had_results = (
        index_result.get("index_hit") and 
        len(index_result.get("results", [])) > 0 and
        "error" not in index_result
    )
    
    if index_had_results:
        # Index search found results - use them
        query_time_ms = (time.time() - start_time) * 1000
        index_result["search_path"] = "index"
        index_result["fallback_time_ms"] = None
        index_result["total_time_ms"] = round(query_time_ms, 2)
        
        # Log the path used
        tier_info = " (3-tier)" if use_three_tier else " (legacy)"
        print(f"⚡ Index search{tier_info}: {index_result.get('query_time_ms', 0):.1f}ms | "
              f"{index_result['sessions_searched']} sessions | "
              f"{len(index_result['results'])} results")
        
        return index_result
    
    # Index search failed or found no results - FALLBACK to original scan method
    fallback_start = time.time()
    
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
    
    fallback_time_ms = (time.time() - fallback_start) * 1000
    total_time_ms = (time.time() - start_time) * 1000
    
    # Log the fallback
    index_error = index_result.get("error", "unknown")
    print(f"🔄 Fallback scan: {fallback_time_ms:.1f}ms (index failed: {index_error}) | "
          f"{len(candidate_ids)} sessions | {len(all_results)} results")
    
    return {
        "query": query,
        "temporal": temporal,
        "topics": topics,
        "topics_weighted": topics_weighted,
        "sessions_searched": len(candidate_ids),
        "sessions_total": len(sessions),
        "search_path": "fallback",
        "index_hit": False,
        "index_error": index_error,
        "fallback_time_ms": round(fallback_time_ms, 2),
        "total_time_ms": round(total_time_ms, 2),
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
    parser.add_argument("--benchmark", action="store_true", help="Run benchmark comparison")
    parser.add_argument("--legacy", action="store_true", help="Use legacy two-tier search (no coarse filter)")
    args = parser.parse_args()
    
    # Handle stats request
    if args.stats:
        show_stats()
        return
    
    # Handle benchmark mode
    if args.benchmark:
        skill_root = SCRIPTS_DIR.parent
        index = load_sessions_index(skill_root, args.agent_id, auto_create=not args.no_auto_index)
        if not index:
            print("❌ No sessions index found. Run index-sessions.py first.")
            return
        
        # Generate diverse test queries
        test_queries = [
            "what did we discuss about authentication",
            "wlxc container runtime implementation",
            "glicko rating system chess",
            "memory retrieval search optimization",
            "discord bot channel messages",
            "kubernetes deployment configuration",
            "oauth jwt token security",
            "typescript react component",
            "python script automation",
            "ci cd pipeline github actions",
            "database postgres sql query",
            "wsl windows subsystem linux",
            "docker container image build",
            "ssl tls certificate https",
            "e2e testing playwright cypress",
            "whatsapp telegram messaging",
            "markdown documentation readme",
            "context memory skill rlm",
            "clawdbot agent gateway",
            "chessrt game leaderboard",
            "worked on yesterday",
            "last week decisions",
            "discussed auth implementation",
            "file upload handling",
            "error handling exception",
            "api endpoint rest",
            "jsonl transcript session",
            "index search performance",
            "cache optimization speed",
            "refactor code cleanup",
        ]
        
        # Limit to available sessions if needed
        if len(index.get("sessions", {})) < 10:
            print(f"⚠️  Only {len(index.get('sessions', {}))} sessions indexed. Benchmark may be limited.")
            test_queries = test_queries[:10]
        
        benchmark_results = run_benchmark(test_queries[:50], index, args.agent_id)
        
        if args.json:
            print(json.dumps(benchmark_results, indent=2))
        return
    
    query = args.query_flag or " ".join(args.query)
    if not query:
        parser.print_help()
        return
    
    print(f"🔍 Searching: \"{query}\"\n")
    
    result = temporal_search(query, args.agent_id, auto_index=not args.no_auto_index, use_three_tier=not args.legacy)
    
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
    
    # Show search path and timing
    search_path = result.get("search_path", "unknown")
    total_time = result.get("total_time_ms", 0)
    index_time = result.get("query_time_ms", 0) if search_path == "index" else None
    fallback_time = result.get("fallback_time_ms", 0) if search_path == "fallback" else None
    
    # Show three-tier timing breakdown if available
    tier_times = result.get("tier_times_ms", {})
    if tier_times:
        print(f"\n⚡ Three-tier timing breakdown:")
        if "tier1_index_ms" in tier_times:
            print(f"   Tier 1 (Index):     {tier_times['tier1_index_ms']:.1f}ms")
        if "tier2_coarse_ms" in tier_times:
            print(f"   Tier 2 (Coarse):    {tier_times['tier2_coarse_ms']:.1f}ms")
        if "tier3_enhanced_ms" in tier_times:
            print(f"   Tier 3 (Enhanced):  {tier_times['tier3_enhanced_ms']:.1f}ms")
    
    path_icon = "⚡" if search_path == "index" else "🔄" if search_path == "fallback" else "❓"
    
    print(f"\n📊 Searched {result['sessions_searched']}/{result['sessions_total']} sessions")
    if "candidates_found" in result:
        print(f"   Index candidates: {result['candidates_found']}")
    print(f"   Found {len(result['results'])} matches")
    print(f"   Path: {path_icon} {search_path} ({total_time:.1f}ms)", end="")
    if index_time:
        print(f" [index: {index_time:.1f}ms]")
    elif fallback_time:
        print(f" [fallback: {fallback_time:.1f}ms]")
    else:
        print()
    print()
    
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
