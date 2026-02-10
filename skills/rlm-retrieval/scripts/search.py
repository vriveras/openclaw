#!/usr/bin/env python3
"""
RLM-inspired search for Clawdbot context memory.
Implements heuristics from arxiv.org/abs/2512.24601

Usage: 
  python search.py "query"
  python search.py --topic auth
  python search.py --recent 3

Searches memory/ directory (Clawdbot convention).
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Clawdbot uses memory/ not .claude-memory/
MEMORY_DIR = Path(__file__).parent.parent.parent.parent / "memory"
STATE_FILE = MEMORY_DIR / "context-state.json"
CHUNK_PATTERN = "conv-*.md"


def load_metadata() -> Dict[str, Any]:
    """
    RLM Principle 1: Metadata first, content later.
    """
    metadata = {
        "state": None,
        "chunks": [],
        "total_chunks": 0,
        "date_range": None,
    }
    
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            metadata["state"] = json.load(f)
    
    chunks = []
    for chunk_path in sorted(MEMORY_DIR.glob(CHUNK_PATTERN), reverse=True):
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


def filter_by_priors(metadata: Dict, query: str) -> List[Dict]:
    """
    RLM Principle 2: Use model priors to filter.
    """
    chunks = metadata["chunks"]
    state = metadata["state"] or {}
    
    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    
    active_topics = set(t.lower() for t in state.get("activeTopics", []))
    entities = set(e.lower() for e in state.get("entities", {}).keys())
    thread_ids = set(t["id"].lower() for t in state.get("openThreads", []))
    
    scored_chunks = []
    for chunk in chunks:
        score = 0.0
        reasons = []
        
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
        
        chunk_name_lower = chunk["name"].lower()
        for topic in active_topics:
            if topic in query_lower or topic in chunk_name_lower:
                score += 2.0
                reasons.append(f"topic:{topic}")
        
        for entity in entities:
            if entity in query_lower:
                score += 1.5
                reasons.append(f"entity:{entity}")
        
        for tid in thread_ids:
            if tid in query_lower:
                score += 2.0
                reasons.append(f"thread:{tid}")
        
        scored_chunks.append({
            **chunk,
            "prior_score": score,
            "reasons": reasons,
        })
    
    scored_chunks.sort(key=lambda x: (-x["prior_score"], x["age_days"]))
    return scored_chunks


def search_chunk_content(chunk_path: Path, query: str) -> Dict:
    """
    RLM Principle 3: Intelligent chunking within content.
    """
    content = chunk_path.read_text()
    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    
    sections = re.split(r'^(##+ .+)$', content, flags=re.MULTILINE)
    
    matches = []
    current_header = "Header"
    
    for i, section in enumerate(sections):
        if section.startswith("#"):
            current_header = section.strip()
            continue
        
        section_lower = section.lower()
        word_matches = [w for w in query_words if w in section_lower and len(w) > 3]
        
        if word_matches:
            snippet = extract_snippet(section, query_words)
            matches.append({
                "header": current_header,
                "snippet": snippet,
                "word_matches": word_matches,
                "match_count": len(word_matches),
            })
    
    return {
        "path": str(chunk_path),
        "name": chunk_path.name,
        "matches": matches,
        "total_matches": len(matches),
    }


def extract_snippet(text: str, keywords: set, context_chars: int = 200) -> str:
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
    
    return text[:context_chars].strip() + "..."


def accumulate_results(search_results: List[Dict], max_results: int = 5) -> Dict:
    """
    RLM Principle 5: Accumulate in variables.
    """
    all_matches = []
    for result in search_results:
        for match in result.get("matches", []):
            all_matches.append({
                "chunk": result["name"],
                "header": match["header"],
                "snippet": match["snippet"],
                "score": match["match_count"] + (1 if result.get("prior_score", 0) > 2 else 0),
            })
    
    all_matches.sort(key=lambda x: -x["score"])
    top_matches = all_matches[:max_results]
    
    return {
        "total_searched": len(search_results),
        "total_matches": len(all_matches),
        "top_results": top_matches,
    }


def search(query: str, max_chunks: int = 10, max_results: int = 5) -> Dict:
    """Main search implementing RLM heuristics."""
    if not MEMORY_DIR.exists():
        return {"error": f"Memory directory not found: {MEMORY_DIR}"}
    
    metadata = load_metadata()
    
    if metadata["total_chunks"] == 0:
        return {
            "query": query,
            "state": metadata["state"],
            "results": [],
            "message": "No conversation chunks found."
        }
    
    filtered_chunks = filter_by_priors(metadata, query)
    candidates = filtered_chunks[:max_chunks]
    search_results = []
    
    for chunk in candidates:
        result = search_chunk_content(chunk["path"], query)
        result["prior_score"] = chunk["prior_score"]
        result["prior_reasons"] = chunk["reasons"]
        search_results.append(result)
    
    search_results = [r for r in search_results if r["total_matches"] > 0]
    accumulated = accumulate_results(search_results, max_results)
    
    return {
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


def get_recent(n: int = 3) -> Dict:
    metadata = load_metadata()
    
    recent = []
    for chunk in metadata["chunks"][:n]:
        content = chunk["path"].read_text()
        summary_match = re.search(r'\*\*Summary[:\*]*\*?\*? ?(.+)', content)
        if not summary_match:
            summary_match = re.search(r'^## Summary\n(.+)', content, re.MULTILINE)
        summary = summary_match.group(1) if summary_match else content[:200] + "..."
        
        recent.append({
            "name": chunk["name"],
            "date": chunk["date"].isoformat() if chunk["date"] else "unknown",
            "summary": summary.strip(),
        })
    
    return {
        "recent_chunks": recent,
        "state": metadata["state"],
    }


def main():
    parser = argparse.ArgumentParser(description="RLM-inspired context search")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--recent", "-r", type=int, metavar="N", help="Get N recent chunks")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    
    args = parser.parse_args()
    
    if args.recent:
        result = get_recent(args.recent)
    elif args.query:
        result = search(args.query)
    else:
        parser.print_help()
        return
    
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        if "recent_chunks" in result:
            print("=== Recent Conversations ===\n")
            for chunk in result["recent_chunks"]:
                print(f"📄 {chunk['name']} ({chunk['date']})")
                print(f"   {chunk['summary']}\n")
        elif "query" in result:
            print(f"=== Search: {result['query']} ===\n")
            print(f"Searched {result.get('searched_chunks', 0)} chunks\n")
            if result.get("top_results"):
                for r in result["top_results"]:
                    print(f"📄 {r['chunk']} > {r['header']}")
                    print(f"   {r['snippet']}\n")
            else:
                print("No matches found.")


if __name__ == "__main__":
    main()
