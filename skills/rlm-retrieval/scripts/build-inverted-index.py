#!/usr/bin/env python3
"""
Build Inverted Index for RLM Retrieval

Phase 1: Initial index build from all existing sessions.
Scans all session JSONL files, tokenizes messages, and builds
an inverted index mapping terms to their occurrences.

Index Schema:
{
  "version": 1,
  "last_updated": "ISO timestamp",
  "total_terms": N,
  "total_messages": N,
  "terms": {
    "rlm": [{"session": "abc123", "msg_idx": 45, "timestamp": "..."}],
    ...
  },
  "sessions": {
    "abc123": {"last_msg_idx": 67, "indexed_at": "...", "term_count": 145}
  }
}
"""

import json
import re
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Any

# ============================================================================
# CONFIGURATION
# ============================================================================

SESSIONS_DIR = Path("/home/virivera/.clawdbot/agents/main/sessions")
OUTPUT_PATH = Path("/home/virivera/clawd/skills/rlm-retrieval/memory/inverted-index.json")
INDEX_VERSION = 1
MIN_TERM_LENGTH = 3

# Common English stopwords to filter out
STOPWORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her",
    "she", "or", "an", "will", "my", "one", "all", "would", "there",
    "their", "what", "so", "up", "out", "if", "about", "who", "get",
    "which", "go", "me", "when", "make", "can", "like", "time", "no",
    "just", "him", "know", "take", "people", "into", "year", "your",
    "good", "some", "could", "them", "see", "other", "than", "then",
    "now", "look", "only", "come", "its", "over", "think", "also",
    "back", "after", "use", "two", "how", "our", "work", "first",
    "well", "way", "even", "new", "want", "because", "any", "these",
    "give", "day", "most", "us", "is", "was", "are", "were", "been",
    "has", "had", "did", "does", "doing", "done", "am", "being",
    "having", "got", "gets", "going", "went", "coming", "came",
    "said", "says", "saying", "made", "making", "took", "taking",
    "seen", "seeing", "used", "using", "found", "finding", "give",
    "gave", "given", "giving", "put", "puts", "putting", "let",
    "lets", "letting", "may", "might", "must", "shall", "should",
    "will", "would", "can", "could", "should", "need", "needs",
    "needed", "needing", "seem", "seems", "seemed", "seeming",
    "feel", "feels", "felt", "feeling", "try", "tries", "tried",
    "trying", "ask", "asks", "asked", "asking", "tell", "tells",
    "told", "telling", "call", "calls", "called", "calling",
    "turn", "turns", "turned", "turning", "start", "starts",
    "started", "starting", "show", "shows", "showed", "shown",
    "showing", "hear", "hears", "heard", "hearing", "play",
    "plays", "played", "playing", "run", "runs", "ran", "running",
    "move", "moves", "moved", "moving", "live", "lives", "lived",
    "living", "believe", "believes", "believed", "believing",
    "bring", "brings", "brought", "bringing", "happen", "happens",
    "happened", "happening", "write", "writes", "wrote", "written",
    "writing", "provide", "provides", "provided", "providing",
    "sit", "sits", "sat", "sitting", "stand", "stands", "stood",
    "standing", "lose", "loses", "lost", "losing", "pay", "pays",
    "paid", "paying", "meet", "meets", "met", "meeting", "include",
    "includes", "included", "including", "continue", "continues",
    "continued", "continuing", "set", "sets", "setting", "learn",
    "learns", "learned", "learning", "change", "changes", "changed",
    "changing", "lead", "leads", "led", "leading", "understand",
    "understands", "understood", "understanding", "watch", "watches",
    "watched", "watching", "follow", "follows", "followed", "following",
    "stop", "stops", "stopped", "stopping", "create", "creates",
    "created", "creating", "speak", "speaks", "spoke", "spoken",
    "speaking", "read", "reads", "reading", "allow", "allows",
    "allowed", "allowing", "add", "adds", "added", "adding", "spend",
    "spends", "spent", "spending", "grow", "grows", "grew", "grown",
    "growing", "open", "opens", "opened", "opening", "walk", "walks",
    "walked", "walking", "win", "wins", "won", "winning", "offer",
    "offers", "offered", "offering", "remember", "remembers",
    "remembered", "remembering", "love", "loves", "loved", "loving",
    "consider", "considers", "considered", "considering", "appear",
    "appears", "appeared", "appearing", "buy", "buys", "bought",
    "buying", "wait", "waits", "waited", "waiting", "serve",
    "serves", "served", "serving", "die", "dies", "died", "dying",
    "send", "sends", "sent", "sending", "expect", "expects",
    "expected", "expecting", "build", "builds", "built", "building",
    "stay", "stays", "stayed", "staying", "fall", "falls", "fell",
    "fallen", "falling", "cut", "cuts", "cutting", "reach",
    "reaches", "reached", "reaching", "kill", "kills", "killed",
    "killing", "remain", "remains", "remained", "remaining", "suggest",
    "suggests", "suggested", "suggesting", "raise", "raises", "raised",
    "raising", "pass", "passes", "passed", "passing", "sell", "sells",
    "sold", "selling", "require", "requires", "required", "requiring",
    "report", "reports", "reported", "reporting", "decide", "decides",
    "decided", "deciding", "pull", "pulls", "pulled", "pulling",
    "return", "returns", "returned", "returning", "explain", "explains",
    "explained", "explaining", "carry", "carries", "carried", "carrying",
    "develop", "develops", "developed", "developing", "hope", "hopes",
    "hoped", "hoping", "drive", "drives", "drove", "driven", "driving",
    "break", "breaks", "broke", "broken", "breaking", "receive",
    "receives", "received", "receiving", "agree", "agrees", "agreed",
    "agreeing", "support", "supports", "supported", "supporting",
    "remove", "removes", "removed", "removing", "return", "returns",
    "returned", "returning", "eat", "eats", "ate", "eaten", "eating",
    "draw", "draws", "drew", "drawn", "drawing", "choose", "chooses",
    "chose", "chosen", "choosing", "catch", "catches", "caught",
    "catching", "throw", "throws", "threw", "thrown", "throwing",
    "become", "becomes", "became", "becoming", "cause", "causes",
    "caused", "causing", "check", "checks", "checked", "checking",
    "come", "comes", "came", "coming", "find", "finds", "found",
    "finding", "get", "gets", "got", "gotten", "getting", "give",
    "gives", "gave", "given", "giving", "go", "goes", "went", "gone",
    "going", "have", "has", "had", "having", "hear", "hears", "heard",
    "hearing", "help", "helps", "helped", "helping", "keep", "keeps",
    "kept", "keeping", "know", "knows", "knew", "known", "knowing",
    "leave", "leaves", "left", "leaving", "let", "lets", "letting",
    "like", "likes", "liked", "liking", "live", "lives", "lived",
    "living", "look", "looks", "looked", "looking", "make", "makes",
    "made", "making", "mean", "means", "meant", "meaning", "move",
    "moves", "moved", "moving", "need", "needs", "needed", "needing",
    "play", "plays", "played", "playing", "put", "puts", "putting",
    "run", "runs", "ran", "running", "say", "says", "said", "saying",
    "see", "sees", "saw", "seen", "seeing", "seem", "seems", "seemed",
    "seeming", "show", "shows", "showed", "shown", "showing", "take",
    "takes", "took", "taken", "taking", "tell", "tells", "told",
    "telling", "think", "thinks", "thought", "thinking", "try",
    "tries", "tried", "trying", "turn", "turns", "turned", "turning",
    "use", "uses", "used", "using", "want", "wants", "wanted",
    "wanting", "work", "works", "worked", "working"
}

# ============================================================================
# COMPOUND WORD SPLITTING (from enhanced_matching.py)
# ============================================================================

def split_compound(word: str) -> List[str]:
    """
    Split compound words into parts.
    
    Handles:
    - camelCase → camel, case
    - PascalCase → pascal, case
    - kebab-case → kebab, case
    - snake_case → snake, case
    - SCREAMING_SNAKE → screaming, snake
    """
    parts = []
    
    # First split on - and _
    tokens = re.split(r'[-_]', word)
    
    for token in tokens:
        if not token:
            continue
            
        # Split camelCase and PascalCase
        # Insert space before uppercase letters that follow lowercase
        split = re.sub(r'([a-z])([A-Z])', r'\1 \2', token)
        # Insert space before uppercase letters followed by lowercase (for acronyms)
        split = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', split)
        
        parts.extend(split.lower().split())
    
    return parts


def tokenize_text(text: str) -> Set[str]:
    """
    Tokenize text into searchable terms.
    
    - Lowercase all terms
    - Split compounds (camelCase, kebab-case, snake_case)
    - Filter common stopwords
    - Keep terms with 3+ characters
    """
    if not text:
        return set()
    
    terms = set()
    
    # Extract raw words (alphanumeric with hyphens/underscores)
    raw_words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]*\b', text)
    
    for word in raw_words:
        # Get compound splits
        parts = split_compound(word)
        
        for part in parts:
            part_lower = part.lower()
            
            # Filter: must be 3+ chars and not a stopword
            if len(part_lower) >= MIN_TERM_LENGTH and part_lower not in STOPWORDS:
                terms.add(part_lower)
    
    return terms


# ============================================================================
# MESSAGE EXTRACTION
# ============================================================================

def extract_message_text(msg: Dict[str, Any]) -> str:
    """
    Extract searchable text from a message object.
    Handles various message types and content structures.
    """
    text_parts = []
    
    # Get message content
    message_data = msg.get("message", {})
    if not message_data:
        return ""
    
    # Handle different content types
    content = message_data.get("content", [])
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type == "text":
                    text_parts.append(item.get("text", ""))
                elif item_type == "thinking":
                    text_parts.append(item.get("thinking", ""))
                elif item_type == "toolCall":
                    # Include tool call names and arguments
                    text_parts.append(item.get("name", ""))
                    args = item.get("arguments", {})
                    if isinstance(args, dict):
                        for key, val in args.items():
                            if isinstance(val, str):
                                text_parts.append(val)
                elif item_type == "toolResult":
                    # Include tool result content
                    result_content = item.get("content", [])
                    if isinstance(result_content, list):
                        for rc in result_content:
                            if isinstance(rc, dict) and rc.get("type") == "text":
                                text_parts.append(rc.get("text", ""))
    elif isinstance(content, str):
        text_parts.append(content)
    
    # Join all text parts
    return " ".join(text_parts)


def parse_session_file(filepath: Path) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Parse a session JSONL file and return session ID with list of messages.
    Only processes 'message' type entries with actual content.
    """
    session_id = filepath.stem.replace(".jsonl", "")
    messages = []
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    entry = json.loads(line)
                    
                    # Only process message entries
                    if entry.get("type") == "message":
                        msg_data = entry.get("message", {})
                        
                        # Skip empty messages
                        if not msg_data.get("content"):
                            continue
                        
                        messages.append({
                            "idx": line_num,
                            "timestamp": entry.get("timestamp", ""),
                            "role": msg_data.get("role", ""),
                            "text": extract_message_text(entry)
                        })
                        
                except json.JSONDecodeError:
                    continue
                    
    except Exception as e:
        print(f"Warning: Error reading {filepath}: {e}", file=sys.stderr)
    
    return session_id, messages


# ============================================================================
# INDEX BUILDING
# ============================================================================

def build_inverted_index(sessions_dir: Path) -> Dict[str, Any]:
    """
    Build inverted index from all session files.
    
    Returns index structure:
    {
        "version": 1,
        "last_updated": "ISO timestamp",
        "total_terms": N,
        "total_messages": N,
        "terms": {term: [{session, msg_idx, timestamp}, ...]},
        "sessions": {session_id: {last_msg_idx, indexed_at, term_count}}
    }
    """
    # Initialize index structure
    index = {
        "version": INDEX_VERSION,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_terms": 0,
        "total_messages": 0,
        "terms": defaultdict(list),
        "sessions": {}
    }
    
    # Track unique terms
    unique_terms = set()
    total_messages = 0
    
    # Find all session files
    session_files = list(sessions_dir.glob("*.jsonl"))
    session_files = [f for f in session_files if not f.name.endswith(".deleted")]
    
    print(f"Found {len(session_files)} session files to index")
    
    # Process each session file
    for i, filepath in enumerate(session_files):
        if i % 50 == 0:
            print(f"  Processing {i+1}/{len(session_files)}: {filepath.name}")
        
        session_id, messages = parse_session_file(filepath)
        
        if not messages:
            continue
        
        # Track session stats
        session_term_count = 0
        max_msg_idx = 0
        
        # Process each message
        for msg in messages:
            msg_idx = msg["idx"]
            max_msg_idx = max(max_msg_idx, msg_idx)
            
            # Tokenize message text
            terms = tokenize_text(msg["text"])
            
            # Add each term occurrence to index
            for term in terms:
                unique_terms.add(term)
                index["terms"][term].append({
                    "session": session_id,
                    "msg_idx": msg_idx,
                    "timestamp": msg["timestamp"]
                })
                session_term_count += 1
            
            total_messages += 1
        
        # Store session metadata
        index["sessions"][session_id] = {
            "last_msg_idx": max_msg_idx,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "term_count": session_term_count,
            "message_count": len(messages)
        }
    
    # Finalize index stats
    index["total_terms"] = len(unique_terms)
    index["total_messages"] = total_messages
    
    # Convert defaultdict to regular dict for JSON serialization
    index["terms"] = dict(index["terms"])
    
    return index


# ============================================================================
# MAIN
# ============================================================================

def main():
    import time
    
    print("=" * 60)
    print("Building Inverted Index for RLM Retrieval")
    print("=" * 60)
    
    # Verify sessions directory exists
    if not SESSIONS_DIR.exists():
        print(f"Error: Sessions directory not found: {SESSIONS_DIR}")
        sys.exit(1)
    
    # Build index
    start_time = time.time()
    index = build_inverted_index(SESSIONS_DIR)
    build_time = time.time() - start_time
    
    # Ensure output directory exists
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Save index
    print(f"\nSaving index to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    
    # Get file size
    file_size_mb = OUTPUT_PATH.stat().st_size / (1024 * 1024)
    
    # Print report
    print("\n" + "=" * 60)
    print("INDEX BUILD COMPLETE")
    print("=" * 60)
    print(f"Build time:        {build_time:.2f} seconds")
    print(f"Index file size:   {file_size_mb:.2f} MB")
    print(f"Total sessions:    {len(index['sessions'])}")
    print(f"Total messages:    {index['total_messages']}")
    print(f"Unique terms:      {index['total_terms']}")
    print(f"Index version:     {index['version']}")
    print(f"Last updated:      {index['last_updated']}")
    print("=" * 60)
    
    # Show sample terms
    print("\nSample indexed terms (first 20):")
    sample_terms = sorted(index["terms"].keys())[:20]
    for term in sample_terms:
        count = len(index["terms"][term])
        print(f"  '{term}': {count} occurrence(s)")
    
    # Show top terms by frequency
    print("\nTop 10 most frequent terms:")
    top_terms = sorted(
        index["terms"].items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:10]
    for term, postings in top_terms:
        print(f"  '{term}': {len(postings)} occurrence(s)")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
