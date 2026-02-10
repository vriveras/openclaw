#!/usr/bin/env python3
"""
True RLM-style recursive search over session transcripts.

Implements the RLM paper approach:
1. Score sessions by priors (recency, topic match)
2. Chunk sessions into searchable units
3. Score and rank ALL chunks, not just first match
4. Accumulate results with constant-size output

Usage:
  python rlm-search.py "query" [--limit 10] [--agent main]
"""

import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

# Import enhanced matching
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))
try:
    from enhanced_matching import enhanced_keyword_match, split_compound, get_related_concepts
    ENHANCED_AVAILABLE = True
except ImportError:
    ENHANCED_AVAILABLE = False

@dataclass
class SearchResult:
    source: str
    chunk_id: str
    content: str
    score: float
    timestamp: Optional[str] = None
    metadata: Optional[Dict] = None

def get_sessions_dir(agent_id: str = "main") -> Path:
    return Path.home() / ".clawdbot" / "agents" / agent_id / "sessions"

def get_memory_dir() -> Path:
    candidates = [
        Path.cwd() / "memory",
        Path.home() / "clawd" / "memory",
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path.cwd() / "memory"

def tokenize_query(query: str) -> List[str]:
    """Extract meaningful search terms."""
    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b', query.lower())
    stopwords = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had',
                 'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been', 'will', 'more',
                 'when', 'who', 'which', 'their', 'what', 'there', 'from', 'this', 'that', 'with'}
    return [w for w in words if w not in stopwords]

def score_text(text: str, query_terms: List[str], enhanced: bool = True) -> float:
    """
    Score text against query terms.
    
    If enhanced=True and available, uses:
    - Substring matching (score += 1.5)
    - Compound word splitting (score += 2.0)
    - Fuzzy matching (score += 1.0)
    - Concept expansion (score += 1.5)
    """
    if not text or not query_terms:
        return 0.0
    
    text_lower = text.lower()
    score = 0.0
    
    for term in query_terms:
        # Exact match (highest score)
        if term in text_lower:
            score += 2.0
            count = text_lower.count(term)
            score += min(count * 0.3, 1.5)
            if re.search(rf'\b{re.escape(term)}\b', text_lower):
                score += 0.5
            continue
        
        # Enhanced matching
        if enhanced and ENHANCED_AVAILABLE:
            matched, match_info = enhanced_keyword_match(
                term, text,
                use_substring=True,
                use_compound=True,
                use_fuzzy=True,
                use_concepts=True
            )
            if matched:
                # Score based on match type
                for info in match_info:
                    if '⊂' in info:  # Substring
                        score += 1.5
                    elif '≈' in info:  # Fuzzy
                        score += 1.0
                    else:  # Exact or concept
                        score += 1.8
    
    # Normalize by number of terms for fairness
    if query_terms:
        score = score / len(query_terms) * min(len(query_terms), 3)
    
    return score

def extract_message_text(msg_obj: dict) -> Tuple[str, str]:
    """Extract role and text from a message object."""
    role = msg_obj.get("message", {}).get("role", "unknown")
    content = msg_obj.get("message", {}).get("content", [])
    
    if isinstance(content, str):
        return role, content
    
    texts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text = item.get("text", "")
            # Skip very short or JSON-looking content
            if len(text) > 20 and not text.strip().startswith('{'):
                texts.append(text)
    
    return role, "\n".join(texts)

def chunk_session(jsonl_path: Path, chunk_size: int = 10) -> List[Dict]:
    """
    Chunk a session into searchable units.
    
    RLM approach: chunk by semantic boundaries (messages), not arbitrary bytes.
    Each chunk contains consecutive messages for context.
    """
    chunks = []
    current_chunk = {
        "messages": [],
        "start_idx": 0,
        "timestamp": None,
        "text": ""
    }
    message_idx = 0
    
    try:
        with open(jsonl_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                if obj.get("type") == "message":
                    role, text = extract_message_text(obj)
                    
                    if text and len(text) > 10:
                        if not current_chunk["timestamp"]:
                            current_chunk["timestamp"] = obj.get("timestamp")
                        
                        current_chunk["messages"].append({
                            "role": role,
                            "text": text[:1000],  # Limit per message
                            "idx": message_idx
                        })
                        current_chunk["text"] += f"\n{text[:500]}"
                        message_idx += 1
                        
                        # Create chunk when we hit chunk_size messages
                        if len(current_chunk["messages"]) >= chunk_size:
                            chunks.append(current_chunk)
                            current_chunk = {
                                "messages": [],
                                "start_idx": message_idx,
                                "timestamp": None,
                                "text": ""
                            }
        
        # Don't forget last chunk
        if current_chunk["messages"]:
            chunks.append(current_chunk)
            
    except Exception as e:
        print(f"Error chunking {jsonl_path}: {e}", file=sys.stderr)
    
    return chunks

def score_session_prior(jsonl_path: Path, query_terms: List[str], active_topics: List[str] = None) -> float:
    """
    RLM prior-based scoring: predict relevance BEFORE reading full content.
    """
    score = 0.0
    
    # Recency scoring
    mtime = datetime.fromtimestamp(jsonl_path.stat().st_mtime)
    days_ago = (datetime.now() - mtime).days
    
    if days_ago == 0:
        score += 3.0  # Today
    elif days_ago == 1:
        score += 2.0  # Yesterday
    elif days_ago < 7:
        score += 1.0  # This week
    else:
        score += 0.5  # Older
    
    # Size heuristic (larger sessions more likely to have content)
    size = jsonl_path.stat().st_size
    if size > 100000:  # >100KB
        score += 1.0
    elif size > 10000:  # >10KB
        score += 0.5
    
    # Topic match from active topics
    if active_topics:
        # Quick scan first line for session metadata
        try:
            with open(jsonl_path, 'r') as f:
                first_lines = f.read(5000)
                for topic in active_topics:
                    if topic.lower() in first_lines.lower():
                        score += 2.0
                        break
        except:
            pass
    
    return score

def search_state(state_path: Path, query_terms: List[str]) -> List[SearchResult]:
    """Search context-state.json."""
    results = []
    
    if not state_path.exists():
        return results
    
    try:
        with open(state_path) as f:
            state = json.load(f)
    except:
        return results
    
    # Search decisions (high value)
    for i, decision in enumerate(state.get("recentDecisions", [])):
        text = f"{decision.get('decision', '')} {decision.get('context', '')}"
        score = score_text(text, query_terms)
        if score > 0:
            results.append(SearchResult(
                source="state",
                chunk_id=f"decision:{i}",
                content=decision.get("decision", ""),
                score=score + 2.0,  # Boost decisions
                timestamp=decision.get("date"),
                metadata={"context": decision.get("context")}
            ))
    
    # Search threads
    for thread in state.get("openThreads", []):
        text = f"{thread.get('id', '')} {thread.get('summary', '')}"
        score = score_text(text, query_terms)
        if score > 0:
            results.append(SearchResult(
                source="state",
                chunk_id=f"thread:{thread.get('id')}",
                content=thread.get("summary", ""),
                score=score + 1.0,
                metadata={"status": thread.get("status")}
            ))
    
    # Search entities
    for name, desc in state.get("entities", {}).items():
        text = f"{name} {desc}"
        score = score_text(text, query_terms)
        if score > 0:
            results.append(SearchResult(
                source="state",
                chunk_id=f"entity:{name}",
                content=f"{name}: {desc}",
                score=score
            ))
    
    return results

def search_memory_files(memory_dir: Path, query_terms: List[str]) -> List[SearchResult]:
    """Search memory/*.md files with chunking by section."""
    results = []
    
    for md_file in memory_dir.glob("**/*.md"):
        try:
            content = md_file.read_text()
        except:
            continue
        
        # Chunk by headers (semantic boundaries)
        sections = re.split(r'^(#+\s+.+)$', content, flags=re.MULTILINE)
        
        current_header = ""
        for i, section in enumerate(sections):
            if section.startswith('#'):
                current_header = section.strip()
            else:
                section_text = section.strip()
                if len(section_text) > 50:
                    score = score_text(section_text, query_terms)
                    if score > 0:
                        # Recency boost for dated files
                        filename = md_file.name
                        if re.match(r'\d{4}-\d{2}-\d{2}', filename):
                            try:
                                file_date = datetime.strptime(filename[:10], "%Y-%m-%d")
                                days_ago = (datetime.now() - file_date).days
                                if days_ago == 0:
                                    score += 2.0
                                elif days_ago == 1:
                                    score += 1.0
                            except:
                                pass
                        
                        results.append(SearchResult(
                            source="memory",
                            chunk_id=f"{md_file.name}:{i}",
                            content=f"{current_header}\n{section_text[:300]}",
                            score=score,
                            metadata={"file": str(md_file)}
                        ))
    
    return results

def rlm_search_sessions(sessions_dir: Path, query_terms: List[str], 
                        active_topics: List[str] = None,
                        max_sessions: int = 10,
                        max_chunks_per_session: int = 50) -> List[SearchResult]:
    """
    RLM-style recursive search over sessions.
    
    1. Score sessions by prior (recency, size, topic)
    2. Select top candidates
    3. Chunk each candidate
    4. Score ALL chunks
    5. Return top results
    """
    results = []
    
    if not sessions_dir.exists():
        return results
    
    # Step 1: Score sessions by prior
    session_scores = []
    for jsonl_file in sessions_dir.glob("*.jsonl"):
        prior_score = score_session_prior(jsonl_file, query_terms, active_topics)
        session_scores.append((jsonl_file, prior_score))
    
    # Step 2: Select top candidates by prior
    session_scores.sort(key=lambda x: x[1], reverse=True)
    top_sessions = session_scores[:max_sessions]
    
    # Step 3-4: Chunk and score each candidate
    for jsonl_file, prior_score in top_sessions:
        chunks = chunk_session(jsonl_file, chunk_size=10)
        
        for chunk_idx, chunk in enumerate(chunks[:max_chunks_per_session]):
            chunk_score = score_text(chunk["text"], query_terms)
            
            if chunk_score > 0:
                # Combine prior score with chunk score
                total_score = prior_score + chunk_score
                
                # Extract best snippet from chunk
                best_snippet = ""
                best_snippet_score = 0
                for msg in chunk["messages"]:
                    msg_score = score_text(msg["text"], query_terms)
                    if msg_score > best_snippet_score:
                        best_snippet = msg["text"][:300]
                        best_snippet_score = msg_score
                
                results.append(SearchResult(
                    source="session",
                    chunk_id=f"{jsonl_file.stem[:8]}:chunk{chunk_idx}",
                    content=best_snippet or chunk["text"][:300],
                    score=total_score,
                    timestamp=chunk.get("timestamp"),
                    metadata={
                        "session": jsonl_file.stem,
                        "chunk_idx": chunk_idx,
                        "message_count": len(chunk["messages"])
                    }
                ))
    
    return results

def combined_rlm_search(query: str, limit: int = 10, agent_id: str = "main", 
                        min_score: float = 5.0) -> List[SearchResult]:
    """
    Full RLM search across all sources with recursive chunking.
    
    Args:
        min_score: Minimum score threshold. Results below this are considered
                   "not confident enough" and filtered out. This prevents
                   false positives on adversarial queries.
    """
    query_terms = tokenize_query(query)
    
    if not query_terms:
        return []
    
    memory_dir = get_memory_dir()
    sessions_dir = get_sessions_dir(agent_id)
    state_path = memory_dir / "context-state.json"
    
    # Load active topics for prior scoring
    active_topics = []
    try:
        with open(state_path) as f:
            state = json.load(f)
            active_topics = state.get("activeTopics", [])
    except:
        pass
    
    all_results = []
    
    # Search each source
    all_results.extend(search_state(state_path, query_terms))
    all_results.extend(search_memory_files(memory_dir, query_terms))
    all_results.extend(rlm_search_sessions(sessions_dir, query_terms, active_topics))
    
    # Step 5: Sort by score, filter by minimum, return constant-size output
    all_results.sort(key=lambda x: x.score, reverse=True)
    
    # Filter by minimum score to avoid false positives
    confident_results = [r for r in all_results if r.score >= min_score]
    
    return confident_results[:limit]

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RLM-style recursive context search")
    parser.add_argument("query", nargs="+", help="Search query")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    parser.add_argument("--agent", default="main", help="Agent ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--min-score", type=float, default=5.0, help="Minimum confidence score")
    args = parser.parse_args()
    
    query = " ".join(args.query)
    results = combined_rlm_search(query, args.limit, args.agent, args.min_score)
    
    if args.json:
        output = {
            "query": query,
            "found": len(results),
            "confident": len(results) > 0,
            "results": [{"source": r.source, "chunk_id": r.chunk_id, "content": r.content, 
                        "score": r.score, "timestamp": r.timestamp} for r in results]
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"🧠 RLM Search: {query}")
        
        if len(results) == 0:
            print(f"📊 NOT_FOUND — No results above confidence threshold ({args.min_score})")
            print("   This topic may not have been discussed.")
        else:
            print(f"📊 Found: {len(results)} confident results")
            print("=" * 60)
            
            for i, r in enumerate(results):
                confidence = "🟢" if r.score >= 10 else "🟡" if r.score >= 7 else "🟠"
                print(f"\n[{i+1}] {confidence} {r.source}:{r.chunk_id} (score: {r.score:.1f})")
                content = r.content.replace('\n', ' ')[:200]
                print(f"    {content}...")
                if r.timestamp:
                    print(f"    ⏰ {r.timestamp[:16]}")

if __name__ == "__main__":
    main()
