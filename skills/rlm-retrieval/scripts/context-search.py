#!/usr/bin/env python3
"""
Combined RLM-style search across all context sources.

Searches:
1. context-state.json (decisions, threads, entities)
2. memory/*.md files
3. Session JSONL transcripts

Usage:
  python context-search.py "query"
  python context-search.py "query" --json
  python context-search.py "query" --limit 5
"""

import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

def get_memory_dir() -> Path:
    candidates = [
        Path.cwd() / "memory",
        Path.home() / "clawd" / "memory",
        Path.home() / "clawdbot" / "memory",
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path.cwd() / "memory"

def get_sessions_dir(agent_id: str = "main") -> Path:
    return Path.home() / ".clawdbot" / "agents" / agent_id / "sessions"

def score_match(text: str, query_terms: List[str]) -> float:
    """Score how well text matches query terms."""
    text_lower = text.lower()
    score = 0.0
    
    for term in query_terms:
        term_lower = term.lower()
        if term_lower in text_lower:
            # Exact match bonus
            score += 2.0
            # Count occurrences (diminishing returns)
            count = text_lower.count(term_lower)
            score += min(count * 0.5, 2.0)
    
    return score

def search_state(state_path: Path, query_terms: List[str]) -> List[Dict]:
    """Search context-state.json for matches."""
    results = []
    
    if not state_path.exists():
        return results
    
    try:
        with open(state_path) as f:
            state = json.load(f)
    except:
        return results
    
    # Search decisions
    for decision in state.get("recentDecisions", []):
        text = f"{decision.get('decision', '')} {decision.get('context', '')}"
        score = score_match(text, query_terms)
        if score > 0:
            results.append({
                "source": "state:decision",
                "date": decision.get("date"),
                "content": decision.get("decision"),
                "context": decision.get("context"),
                "score": score + 1.0  # Boost decisions
            })
    
    # Search threads
    for thread in state.get("openThreads", []):
        text = f"{thread.get('id', '')} {thread.get('summary', '')}"
        score = score_match(text, query_terms)
        if score > 0:
            results.append({
                "source": "state:thread",
                "id": thread.get("id"),
                "status": thread.get("status"),
                "content": thread.get("summary"),
                "score": score
            })
    
    # Search entities
    for name, desc in state.get("entities", {}).items():
        text = f"{name} {desc}"
        score = score_match(text, query_terms)
        if score > 0:
            results.append({
                "source": "state:entity",
                "name": name,
                "content": desc,
                "score": score
            })
    
    return results

def search_memory_files(memory_dir: Path, query_terms: List[str]) -> List[Dict]:
    """Search memory/*.md files."""
    results = []
    
    for md_file in memory_dir.glob("**/*.md"):
        try:
            content = md_file.read_text()
        except:
            continue
        
        score = score_match(content, query_terms)
        if score > 0:
            # Find relevant section
            lines = content.split('\n')
            best_section = ""
            best_section_score = 0
            
            current_section = []
            for line in lines:
                if line.startswith('#'):
                    if current_section:
                        section_text = '\n'.join(current_section)
                        section_score = score_match(section_text, query_terms)
                        if section_score > best_section_score:
                            best_section = section_text[:300]
                            best_section_score = section_score
                    current_section = [line]
                else:
                    current_section.append(line)
            
            # Check last section
            if current_section:
                section_text = '\n'.join(current_section)
                section_score = score_match(section_text, query_terms)
                if section_score > best_section_score:
                    best_section = section_text[:300]
            
            # Recency boost
            filename = md_file.name
            if re.match(r'\d{4}-\d{2}-\d{2}', filename):
                try:
                    file_date = datetime.strptime(filename[:10], "%Y-%m-%d")
                    days_ago = (datetime.now() - file_date).days
                    if days_ago == 0:
                        score += 3.0
                    elif days_ago == 1:
                        score += 2.0
                    elif days_ago < 7:
                        score += 1.0
                except:
                    pass
            
            results.append({
                "source": f"memory:{md_file.relative_to(memory_dir)}",
                "path": str(md_file),
                "content": best_section or content[:300],
                "score": score
            })
    
    return results

def search_sessions(sessions_dir: Path, query_terms: List[str], limit: int = 5) -> List[Dict]:
    """Search session JSONL files."""
    results = []
    
    if not sessions_dir.exists():
        return results
    
    # Score sessions by recency first
    session_files = []
    for jsonl_file in sessions_dir.glob("*.jsonl"):
        mtime = jsonl_file.stat().st_mtime
        session_files.append((jsonl_file, mtime))
    
    # Sort by recency
    session_files.sort(key=lambda x: x[1], reverse=True)
    
    # Search top N sessions
    for jsonl_file, mtime in session_files[:20]:
        try:
            content = jsonl_file.read_text()
        except:
            continue
        
        score = score_match(content, query_terms)
        if score > 0:
            # Extract relevant snippet
            snippet = ""
            for line in content.split('\n'):
                if any(term.lower() in line.lower() for term in query_terms):
                    # Try to extract text content
                    try:
                        obj = json.loads(line)
                        if obj.get("type") == "message":
                            msg_content = obj.get("message", {}).get("content", [])
                            if isinstance(msg_content, list):
                                for item in msg_content:
                                    if isinstance(item, dict) and item.get("type") == "text":
                                        text = item.get("text", "")
                                        if any(term.lower() in text.lower() for term in query_terms):
                                            # Clean up the snippet
                                            clean_text = text.replace('\n', ' ').strip()[:300]
                                            if len(clean_text) > 20 and not clean_text.startswith('{'):
                                                snippet = clean_text
                                                break
                            elif isinstance(msg_content, str):
                                if any(term.lower() in msg_content.lower() for term in query_terms):
                                    snippet = msg_content[:300]
                    except:
                        pass
                    if snippet:
                        break
            
            # Recency boost
            days_ago = (datetime.now() - datetime.fromtimestamp(mtime)).days
            if days_ago == 0:
                score += 3.0
            elif days_ago == 1:
                score += 2.0
            elif days_ago < 7:
                score += 1.0
            
            results.append({
                "source": f"session:{jsonl_file.stem[:8]}",
                "path": str(jsonl_file),
                "content": snippet or "(content matched but not extracted)",
                "score": score
            })
    
    return results

def combined_search(query: str, limit: int = 10, agent_id: str = "main") -> List[Dict]:
    """Search all sources and combine results."""
    query_terms = [t for t in query.split() if len(t) > 2]
    
    memory_dir = get_memory_dir()
    sessions_dir = get_sessions_dir(agent_id)
    state_path = memory_dir / "context-state.json"
    
    all_results = []
    
    # Search each source
    all_results.extend(search_state(state_path, query_terms))
    all_results.extend(search_memory_files(memory_dir, query_terms))
    all_results.extend(search_sessions(sessions_dir, query_terms))
    
    # Sort by score
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    return all_results[:limit]

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Combined RLM context search")
    parser.add_argument("query", nargs="+", help="Search query")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    parser.add_argument("--agent", default="main", help="Agent ID")
    args = parser.parse_args()
    
    query = " ".join(args.query)
    results = combined_search(query, args.limit, args.agent)
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"🔍 Search: {query}")
        print(f"📊 Found: {len(results)} results")
        print("=" * 60)
        
        for i, r in enumerate(results):
            print(f"\n[{i+1}] {r['source']} (score: {r['score']:.1f})")
            content = r.get('content', '')[:200]
            if content:
                print(f"    {content}...")
            if r.get('date'):
                print(f"    Date: {r['date']}")

if __name__ == "__main__":
    main()
