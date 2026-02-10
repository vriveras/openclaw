#!/usr/bin/env python3
"""
Session Indexer for Context Memory

Builds a lightweight index of all sessions with:
- Date/time of session
- Extracted topics (keywords)
- Message count
- Optional summary

Cross-platform: works on Linux, macOS, Windows.

Usage:
    python scripts/index-sessions.py [--agent-id main] [--output memory/sessions-index.json]
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict

# Cross-platform: find sessions directory
def get_sessions_dir(agent_id: str) -> Path:
    """Get the sessions directory for an agent, cross-platform."""
    home = Path.home()
    
    # Try standard Clawdbot paths
    candidates = [
        home / ".clawdbot" / "agents" / agent_id / "sessions",
        home / "AppData" / "Local" / "clawdbot" / "agents" / agent_id / "sessions",  # Windows
        home / ".config" / "clawdbot" / "agents" / agent_id / "sessions",  # XDG
    ]
    
    for path in candidates:
        if path.exists():
            return path
    
    # Default to first option
    return candidates[0]

def extract_text_from_session(session_path: Path, max_messages: int = 500) -> Tuple[str, int, Optional[datetime], Optional[datetime]]:
    """
    Extract text content from a session JSONL file.
    
    Returns: (combined_text, message_count, session_start_time, session_last_time)
    """
    texts = []
    message_count = 0
    session_start = None
    session_last = None
    
    try:
        # Read file and get last N lines for recent context
        with open(session_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Sample from beginning (first 200) and end (last 300) for big files
        if len(lines) > max_messages * 2:
            sampled_lines = lines[:200] + lines[-300:]
        else:
            sampled_lines = lines[:max_messages * 3]
        
        for line in sampled_lines:
            line = line.strip()
            if not line:
                continue
            
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            # Track timestamps
            if 'timestamp' in record:
                try:
                    ts = record['timestamp']
                    if isinstance(ts, str):
                        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    elif isinstance(ts, (int, float)):
                        dt = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts)
                    else:
                        dt = None
                    
                    if dt:
                        if session_start is None:
                            session_start = dt
                        session_last = dt  # Keep updating to get last
                except (ValueError, OSError):
                    pass
            
            if record.get('type') != 'message':
                continue
            
            msg = record.get('message', {})
            if msg.get('role') not in ('user', 'assistant'):
                continue
            
            message_count += 1
            
            content = msg.get('content', [])
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get('type') == 'text':
                        texts.append(block.get('text', ''))
    
    except Exception as e:
        print(f"  Warning: Error reading {session_path.name}: {e}", file=sys.stderr)
    
    return '\n'.join(texts), message_count, session_start, session_last

def extract_topics(text: str, top_n: int = 10) -> List[str]:
    """
    Extract likely topics from text using keyword frequency.
    
    Filters out common words and returns significant terms.
    Preserves proper nouns, acronyms, and technical terms.
    """
    # Common stopwords to filter
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
        'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
        'from', 'as', 'into', 'through', 'during', 'before', 'after',
        'above', 'below', 'between', 'under', 'again', 'further', 'then',
        'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each',
        'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
        'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'and',
        'but', 'if', 'or', 'because', 'until', 'while', 'although', 'though',
        'this', 'that', 'these', 'those', 'what', 'which', 'who', 'whom',
        'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you',
        'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his',
        'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself',
        'they', 'them', 'their', 'theirs', 'themselves', 'am', 'about',
        'also', 'any', 'both', 'down', 'get', 'got', 'like', 'make', 'made',
        'now', 'one', 'out', 'over', 'see', 'up', 'use', 'using', 'want',
        'well', 'work', 'yeah', 'yes', 'ok', 'okay', 'sure', 'thanks',
        'thank', 'please', 'let', 'know', 'think', 'going', 'way', 'things',
        'thing', 'something', 'anything', 'everything', 'nothing', 'time',
        'really', 'actually', 'basically', 'probably', 'maybe', 'right',
        'good', 'great', 'nice', 'looks', 'look', 'looking', 'still', 'back',
        'first', 'last', 'next', 'new', 'old', 'done', 'try', 'tried',
        # Common logging/metadata terms (not meaningful topics)
        'message_id', 'heartbeat_ok', 'no_reply', 'session', 'sessions',
        'timestamp', 'system', 'content', 'user', 'assistant', 'tool',
        'error', 'warning', 'info', 'debug', 'true', 'false', 'null',
        'pst', 'utc', 'gmt', 'localhost', 'http', 'https'
    }
    
    # Extract words preserving case (for proper nouns/acronyms detection)
    words_original = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b', text)
    
    # Track both original case and lowercase versions
    # Key: lowercase, Value: (best_original_form, count, is_proper_noun)
    word_info: Dict[str, Tuple[str, int, bool]] = {}
    
    for word in words_original:
        lower = word.lower()
        if lower in stopwords or len(lower) < 3:
            continue
        
        # Detect proper nouns/acronyms/technical terms:
        # - All caps 2+ chars (WLXC, API, MVP)
        # - PascalCase (PostgreSQL, ChessRT)
        # - Short lowercase 4-6 chars that's not a stopword (wlxc, npm, git)
        # - Contains hyphens/underscores (glicko-2, context-memory)
        # - Contains digits (v2, gpt4, phase12)
        is_short_technical = (
            4 <= len(word) <= 6 and 
            word.islower() and 
            word.isalnum() and
            lower not in stopwords
        )
        is_proper = (
            (word.isupper() and len(word) >= 2) or  # WLXC, API (not single letters)
            (len(word) > 1 and word[0].isupper() and any(c.islower() for c in word)) or  # PostgreSQL
            re.match(r'^[A-Z][a-z]+[A-Z]', word) or  # CamelCase like ChessRT
            is_short_technical or  # Short project names: wlxc, npm (but not 'the', 'for')
            '-' in word or '_' in word or  # Compound terms: glicko-2, context-memory
            any(c.isdigit() for c in word)  # Versioned: gpt4, v2
        )
        
        if lower in word_info:
            orig, count, was_proper = word_info[lower]
            # Keep the proper noun form if we found one
            if is_proper and not was_proper:
                word_info[lower] = (word, count + 1, True)
            else:
                word_info[lower] = (orig, count + 1, was_proper or is_proper)
        else:
            word_info[lower] = (word, 1, is_proper)
    
    # Score words - heavily boost proper nouns and technical terms
    scored = []
    for lower, (original, count, is_proper) in word_info.items():
        score = count
        
        # MAJOR boost for proper nouns/acronyms (project names!)
        if is_proper:
            score *= 5.0
        
        # Boost longer words (more specific)
        if len(lower) >= 6:
            score *= 1.5
        
        # Boost technical-looking terms
        if '-' in lower or '_' in lower:
            score *= 2.0
        
        # Boost words with numbers (like Glicko-2, v2, etc)
        if any(c.isdigit() for c in lower):
            score *= 1.5
        
        # Store lowercase for index (easier matching) but track that it was proper
        scored.append((lower, score, is_proper))
    
    scored.sort(key=lambda x: x[1], reverse=True)
    
    # Return mix: prioritize proper nouns, then high-frequency terms
    proper_nouns = [(w, s) for w, s, p in scored if p][:5]  # Top 5 proper nouns
    other_terms = [(w, s) for w, s, p in scored if not p][:10]  # Top 10 other
    
    # Merge: proper nouns first, then fill with other terms
    result = [w for w, _ in proper_nouns]
    for w, _ in other_terms:
        if w not in result and len(result) < top_n:
            result.append(w)
    
    return result[:top_n]

def index_sessions(agent_id: str, output_path: Path) -> dict:
    """
    Build index of all sessions for an agent.
    """
    sessions_dir = get_sessions_dir(agent_id)
    
    if not sessions_dir.exists():
        print(f"Sessions directory not found: {sessions_dir}", file=sys.stderr)
        return {"sessions": {}, "lastUpdated": datetime.now().isoformat()}
    
    index = {
        "lastUpdated": datetime.now().isoformat(),
        "agentId": agent_id,
        "sessionsDir": str(sessions_dir),
        "sessions": {}
    }
    
    session_files = sorted(sessions_dir.glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    print(f"Indexing {len(session_files)} sessions from {sessions_dir}...")
    
    for session_file in session_files:
        session_id = session_file.stem
        
        text, msg_count, start_time, last_time = extract_text_from_session(session_file)
        
        if msg_count == 0:
            continue
        
        topics = extract_topics(text)
        
        # Get file modification time as fallback
        mtime = datetime.fromtimestamp(session_file.stat().st_mtime)
        # Use LAST activity time for date (more useful for long-running sessions)
        session_date = last_time or start_time or mtime
        
        index["sessions"][session_id] = {
            "date": session_date.strftime("%Y-%m-%d"),
            "time": session_date.strftime("%H:%M"),
            "timestamp": session_date.isoformat(),
            "messageCount": msg_count,
            "topics": topics,
            "file": session_file.name,
            "sizeBytes": session_file.stat().st_size
        }
        
        print(f"  ✓ {session_id[:8]}... ({session_date.strftime('%Y-%m-%d')}, {msg_count} msgs, topics: {', '.join(topics[:3])})")
    
    # Summary stats
    total_sessions = len(index["sessions"])
    total_messages = sum(s["messageCount"] for s in index["sessions"].values())
    
    if index["sessions"]:
        dates = [s["date"] for s in index["sessions"].values()]
        index["stats"] = {
            "totalSessions": total_sessions,
            "totalMessages": total_messages,
            "dateRange": {
                "oldest": min(dates),
                "newest": max(dates)
            }
        }
    
    # Write index
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2)
    
    print(f"\n✅ Indexed {total_sessions} sessions ({total_messages} messages)")
    print(f"   Output: {output_path}")
    
    return index

def main():
    parser = argparse.ArgumentParser(description="Index Clawdbot sessions for temporal search")
    parser.add_argument("--agent-id", default="main", help="Agent ID (default: main)")
    parser.add_argument("--output", default="memory/sessions-index.json", help="Output path")
    args = parser.parse_args()
    
    # Resolve output path relative to script location or cwd
    output_path = Path(args.output)
    if not output_path.is_absolute():
        # Try relative to skill root
        skill_root = Path(__file__).parent.parent
        if (skill_root / "SKILL.md").exists():
            output_path = skill_root / args.output
        else:
            output_path = Path.cwd() / args.output
    
    index_sessions(args.agent_id, output_path)

if __name__ == "__main__":
    main()
