#!/usr/bin/env python3
"""
RLM-inspired search for context memory.
Implements heuristics from arxiv.org/abs/2512.24601

Usage: 
  python search.py "query"
  python search.py "what did we discuss yesterday?"  # Temporal awareness
  python search.py --topic auth
  python search.py --recent 3
  python search.py --since 2026-01-20

Works on Windows, macOS, and Linux.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Import enhanced matching and temporal parser
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))
try:
    from enhanced_matching import enhanced_keyword_match, split_compound, get_related_concepts
    ENHANCED_AVAILABLE = True
except ImportError:
    ENHANCED_AVAILABLE = False

try:
    from temporal_parser import parse_temporal_query
    TEMPORAL_AVAILABLE = True
except ImportError:
    TEMPORAL_AVAILABLE = False

MEMORY_DIR = Path(".claude-memory")


def load_metadata() -> Dict[str, Any]:
    """
    RLM Principle 1: Metadata first, content later.
    Load structure without loading full content.
    """
    metadata = {
        "state": None,
        "chunks": [],
        "total_chunks": 0,
        "date_range": None,
    }
    
    # Load state (small, structured)
    state_file = MEMORY_DIR / "state.json"
    if state_file.exists():
        with open(state_file) as f:
            metadata["state"] = json.load(f)
    
    # List chunks with metadata only (not content)
    chunks = []
    for chunk_path in sorted(MEMORY_DIR.glob("conv-*.md"), reverse=True):
        # Extract date from filename: conv-2026-01-29-001.md
        name = chunk_path.stem
        parts = name.split("-")
        if len(parts) >= 4:
            date_str = f"{parts[1]}-{parts[2]}-{parts[3]}"
            try:
                chunk_date = datetime.strptime(date_str, "%Y-%m-%d")
            except:
                chunk_date = None
        else:
            chunk_date = None
        
        # Get file size as proxy for content length
        size = chunk_path.stat().st_size
        
        chunks.append({
            "path": chunk_path,
            "name": chunk_path.name,
            "date": chunk_date,
            "size": size,
            "age_days": (datetime.now() - chunk_date).days if chunk_date else 999,
        })
    
    metadata["chunks"] = chunks
    metadata["total_chunks"] = len(chunks)
    
    if chunks:
        dates = [c["date"] for c in chunks if c["date"]]
        if dates:
            metadata["date_range"] = {
                "oldest": min(dates).isoformat(),
                "newest": max(dates).isoformat(),
            }
    
    return metadata


def filter_by_priors(metadata: Dict, query: str, date_range: Optional[Tuple[str, str]] = None) -> List[Dict]:
    """
    RLM Principle 2: Use model priors to filter.
    Based on query, predict which chunks are likely relevant.
    
    Args:
        metadata: Loaded metadata
        query: Search query
        date_range: Optional (start_date, end_date) tuple in YYYY-MM-DD format
    """
    chunks = metadata["chunks"]
    state = metadata["state"] or {}
    
    # Filter by date range if specified
    if date_range:
        start_date, end_date = date_range
        chunks = [
            c for c in chunks 
            if c["date"] and start_date <= c["date"].strftime("%Y-%m-%d") <= end_date
        ]
    
    # Extract keywords from query
    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    
    # Get active topics and entities from state
    active_topics = set(t.lower() for t in state.get("activeTopics", []))
    entities = set(e.lower() for e in state.get("entities", {}).keys())
    thread_ids = set(t["id"].lower() for t in state.get("openThreads", []))
    
    # Score each chunk based on filename/date relevance
    scored_chunks = []
    for chunk in chunks:
        score = 0.0
        reasons = []
        
        # Recency weight (RLM principle: recent context more relevant)
        age = chunk["age_days"]
        if age == 0:
            score += 3.0
            reasons.append("today")
        elif age == 1:
            score += 2.0
            reasons.append("yesterday")
        elif age <= 7:
            score += 1.0
            reasons.append("this week")
        
        # Topic match bonus
        chunk_name_lower = chunk["name"].lower()
        for topic in active_topics:
            if topic in query_lower or topic in chunk_name_lower:
                score += 2.0
                reasons.append(f"topic:{topic}")
        
        # Entity match
        for entity in entities:
            if entity in query_lower:
                score += 1.5
                reasons.append(f"entity:{entity}")
        
        # Thread match
        for tid in thread_ids:
            if tid in query_lower:
                score += 2.0
                reasons.append(f"thread:{tid}")
        
        # Keyword in query that might match chunk
        # (we'll verify with content search later)
        for word in query_words:
            if len(word) > 3:  # Skip short words
                score += 0.1  # Small boost, will be refined
        
        scored_chunks.append({
            **chunk,
            "prior_score": score,
            "reasons": reasons,
        })
    
    # Sort by score, then by recency
    scored_chunks.sort(key=lambda x: (-x["prior_score"], x["age_days"]))
    
    return scored_chunks


def search_chunk_content(chunk_path: Path, query: str, enhanced: bool = True) -> Dict:
    """
    RLM Principle 3: Intelligent chunking within content.
    Search within a chunk, split by semantic boundaries.
    
    If enhanced=True and available, uses:
    - Substring matching
    - Compound word splitting
    - Fuzzy matching (Levenshtein ≤ 2)
    - Concept expansion
    """
    content = chunk_path.read_text()
    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    
    # Split by markdown headers (semantic boundaries)
    # Match headers with 2+ # signs (## or ###, etc.)
    sections = re.split(r'^(##+ .+)$', content, flags=re.MULTILINE)
    
    matches = []
    current_header = "Summary"
    
    for i, section in enumerate(sections):
        # Only skip actual h2+ headers captured by the regex
        if re.match(r'^##+ ', section):
            current_header = section.strip()
            continue
        
        section_lower = section.lower()
        
        # Check for query word matches
        word_matches = []
        match_info = []
        
        if enhanced and ENHANCED_AVAILABLE:
            # Use enhanced matching
            # Skip common short words but keep technical acronyms (3+ chars)
            SKIP_WORDS = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'has', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'way', 'who', 'did', 'get', 'let', 'put', 'say', 'too', 'use', 'set'}
            for w in query_words:
                if len(w) < 2 or w in SKIP_WORDS:
                    continue
                matched, terms = enhanced_keyword_match(
                    w, section,
                    use_substring=True,
                    use_compound=True,
                    use_fuzzy=True,
                    use_concepts=True
                )
                if matched:
                    word_matches.append(w)
                    match_info.extend(terms[:2])
        else:
            # Basic matching (fallback)
            word_matches = [w for w in query_words if w in section_lower and len(w) >= 2]
        
        if word_matches:
            # Extract relevant snippet (context around match)
            snippet = extract_snippet(section, query_words)
            result = {
                "header": current_header,
                "snippet": snippet,
                "word_matches": word_matches,
                "match_count": len(word_matches),
            }
            if match_info:
                result["match_info"] = match_info[:5]  # Top 5 match reasons
            matches.append(result)
    
    return {
        "path": str(chunk_path),
        "name": chunk_path.name,
        "matches": matches,
        "total_matches": len(matches),
    }


def extract_snippet(text: str, keywords: set, context_chars: int = 200) -> str:
    """Extract snippet around first keyword match."""
    text_lower = text.lower()
    
    for keyword in keywords:
        if len(keyword) <= 3:
            continue
        pos = text_lower.find(keyword)
        if pos != -1:
            start = max(0, pos - context_chars // 2)
            end = min(len(text), pos + len(keyword) + context_chars // 2)
            snippet = text[start:end].strip()
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet = snippet + "..."
            return snippet
    
    # No match, return beginning
    return text[:context_chars].strip() + "..."


def accumulate_results(search_results: List[Dict], max_results: int = 5) -> Dict:
    """
    RLM Principle 5: Accumulate in variables.
    Build up structured results, don't return everything.
    """
    # Flatten and score all matches
    all_matches = []
    for result in search_results:
        for match in result.get("matches", []):
            all_matches.append({
                "chunk": result["name"],
                "header": match["header"],
                "snippet": match["snippet"],
                "score": match["match_count"] + (1 if result.get("prior_score", 0) > 2 else 0),
            })
    
    # Sort by score
    all_matches.sort(key=lambda x: -x["score"])
    
    # Take top results
    top_matches = all_matches[:max_results]
    
    return {
        "total_searched": len(search_results),
        "total_matches": len(all_matches),
        "top_results": top_matches,
    }


def search(query: str, max_chunks: int = 10, max_results: int = 5, 
           date_start: str = None, date_end: str = None) -> Dict:
    """
    Main search function implementing RLM heuristics.
    
    1. Load metadata (not content)
    2. Parse temporal references from query
    3. Filter by priors (predict relevance)
    4. Search content of top candidates
    5. Accumulate and rank results
    6. Return constant-size output
    """
    if not MEMORY_DIR.exists():
        return {"error": "No .claude-memory/ found. Run init.py first."}
    
    # Step 1: Metadata
    metadata = load_metadata()
    
    if metadata["total_chunks"] == 0:
        return {
            "query": query,
            "state": metadata["state"],
            "results": [],
            "message": "No conversation chunks found."
        }
    
    # Step 2: Parse temporal references
    date_range = None
    temporal_match = None
    
    if date_start and date_end:
        date_range = (date_start, date_end)
    elif TEMPORAL_AVAILABLE:
        temporal = parse_temporal_query(query)
        if temporal:
            date_range = (temporal["start"], temporal["end"])
            temporal_match = temporal["match"]
    
    # Step 3: Filter by priors (with date range if found)
    filtered_chunks = filter_by_priors(metadata, query, date_range)
    
    # Step 3: Search content (only top candidates)
    candidates = filtered_chunks[:max_chunks]
    search_results = []
    
    for chunk in candidates:
        result = search_chunk_content(chunk["path"], query)
        result["prior_score"] = chunk["prior_score"]
        result["prior_reasons"] = chunk["reasons"]
        search_results.append(result)
    
    # Filter to chunks with actual matches
    search_results = [r for r in search_results if r["total_matches"] > 0]
    
    # Step 4 & 5: Accumulate and return constant-size
    accumulated = accumulate_results(search_results, max_results)
    
    result = {
        "query": query,
        "metadata": {
            "total_chunks": metadata["total_chunks"],
            "date_range": metadata["date_range"],
            "active_topics": metadata["state"].get("activeTopics", []) if metadata["state"] else [],
        },
        "searched_chunks": len(candidates),
        "chunks_with_matches": len(search_results),
        **accumulated,
    }
    
    # Add temporal info if query had time reference
    if temporal_match:
        result["temporal"] = {
            "detected": temporal_match,
            "filtered_range": date_range,
        }
    
    return result


def get_recent(n: int = 3) -> Dict:
    """Get N most recent chunks with summaries."""
    metadata = load_metadata()
    
    recent = []
    for chunk in metadata["chunks"][:n]:
        content = chunk["path"].read_text()
        # Extract summary line
        summary_match = re.search(r'\*\*Summary:\*\* (.+)', content)
        summary = summary_match.group(1) if summary_match else content[:200] + "..."
        
        recent.append({
            "name": chunk["name"],
            "date": chunk["date"].isoformat() if chunk["date"] else "unknown",
            "summary": summary,
        })
    
    return {
        "recent_chunks": recent,
        "state": metadata["state"],
    }


def get_by_topic(topic: str) -> Dict:
    """Get context related to a specific topic."""
    metadata = load_metadata()
    state = metadata["state"] or {}
    
    results = {
        "topic": topic,
        "in_active_topics": topic.lower() in [t.lower() for t in state.get("activeTopics", [])],
        "related_threads": [],
        "related_decisions": [],
        "related_chunks": [],
    }
    
    # Find related threads
    for thread in state.get("openThreads", []):
        if topic.lower() in thread.get("id", "").lower() or \
           topic.lower() in thread.get("summary", "").lower():
            results["related_threads"].append(thread)
    
    # Find related decisions
    for decision in state.get("decisions", []):
        if topic.lower() in decision.get("decision", "").lower():
            results["related_decisions"].append(decision)
    
    # Search chunks for topic
    search_result = search(topic, max_chunks=5, max_results=3)
    results["related_chunks"] = search_result.get("top_results", [])
    
    return results


def main():
    parser = argparse.ArgumentParser(description="RLM-inspired context search")
    parser.add_argument("query", nargs="?", help="Search query (supports temporal: 'yesterday', 'last week')")
    parser.add_argument("--recent", "-r", type=int, metavar="N", help="Get N most recent chunks")
    parser.add_argument("--topic", "-t", help="Get context for specific topic")
    parser.add_argument("--since", help="Filter chunks from date (YYYY-MM-DD)")
    parser.add_argument("--until", help="Filter chunks until date (YYYY-MM-DD)")
    parser.add_argument("--max-chunks", type=int, default=10, help="Max chunks to search")
    parser.add_argument("--max-results", type=int, default=5, help="Max results to return")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    if args.recent:
        result = get_recent(args.recent)
    elif args.topic:
        result = get_by_topic(args.topic)
    elif args.query:
        date_start = args.since
        date_end = args.until or datetime.now().strftime("%Y-%m-%d")
        if args.since and not args.until:
            date_end = datetime.now().strftime("%Y-%m-%d")
        result = search(args.query, args.max_chunks, args.max_results, 
                       date_start if args.since else None, 
                       date_end if args.since else None)
    else:
        parser.print_help()
        return
    
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print_human_readable(result)


def print_human_readable(result: Dict):
    """Pretty print results."""
    if "error" in result:
        print(f"Error: {result['error']}")
        return
    
    if "recent_chunks" in result:
        print("=== Recent Conversations ===\n")
        for chunk in result["recent_chunks"]:
            print(f"📄 {chunk['name']} ({chunk['date']})")
            print(f"   {chunk['summary']}\n")
        return
    
    if "topic" in result and "related_threads" in result:
        print(f"=== Context for: {result['topic']} ===\n")
        print(f"Active topic: {'✓' if result['in_active_topics'] else '✗'}\n")
        
        if result["related_threads"]:
            print("Related threads:")
            for t in result["related_threads"]:
                print(f"  [{t['status']}] {t['id']}: {t.get('summary', '')}")
            print()
        
        if result["related_decisions"]:
            print("Related decisions:")
            for d in result["related_decisions"]:
                print(f"  {d['date']}: {d['decision']}")
            print()
        
        if result["related_chunks"]:
            print("From conversations:")
            for r in result["related_chunks"]:
                print(f"  📄 {r['chunk']} > {r['header']}")
                print(f"     {r['snippet'][:100]}...")
                print()
        return
    
    # Search results
    if "query" in result:
        print(f"=== Search: {result['query']} ===\n")
        
        # Show temporal filtering if applied
        if result.get("temporal"):
            t = result["temporal"]
            print(f"🕐 Temporal filter: '{t['detected']}' → {t['filtered_range'][0]} to {t['filtered_range'][1]}\n")
        
        print(f"Searched {result.get('searched_chunks', 0)} chunks, "
              f"found {result.get('chunks_with_matches', 0)} with matches\n")
        
        if result.get("top_results"):
            print("Top results:")
            for r in result["top_results"]:
                print(f"\n📄 {r['chunk']} > {r['header']}")
                print(f"   {r['snippet']}")
        else:
            print("No matches found.")


if __name__ == "__main__":
    main()
