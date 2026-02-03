#!/usr/bin/env python3
"""
Incremental Inverted Index Updater

Updates the inverted index with new messages from a session transcript.
Only processes NEW messages since the last indexed message for that session.

Usage:
    python update-inverted-index.py <session_id> <session_file_path>
    python update-inverted-index.py abc123 ~/.clawdbot/agents/main/sessions/abc123.jsonl

Requirements:
    - Incremental updates <10ms per message
    - Handle concurrent updates safely (file locking)
    - Don't re-index already-indexed messages
"""

import argparse
import fcntl
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Skill paths
SKILL_ROOT = Path(__file__).parent.parent
DATA_DIR = SKILL_ROOT / "data"
INVERTED_INDEX_PATH = DATA_DIR / "inverted-index.json"


def get_lock_file() -> Path:
    """Get the lock file path for concurrent access control."""
    return DATA_DIR / ".inverted-index.lock"


class FileLock:
    """Simple file-based lock for concurrent update safety."""
    
    def __init__(self, lock_file: Path, timeout: float = 30.0):
        self.lock_file = lock_file
        self.timeout = timeout
        self.fd = None
    
    def __enter__(self):
        start_time = time.time()
        while True:
            try:
                self.fd = open(self.lock_file, 'w')
                fcntl.flock(self.fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except (IOError, OSError):
                if time.time() - start_time > self.timeout:
                    raise TimeoutError(f"Could not acquire lock within {self.timeout}s")
                time.sleep(0.01)  # 10ms backoff
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd:
            fcntl.flock(self.fd.fileno(), fcntl.LOCK_UN)
            self.fd.close()
            try:
                os.remove(self.lock_file)
            except OSError:
                pass


def tokenize_text(text: str) -> List[str]:
    """
    Tokenize text into searchable terms.
    - Lowercase
    - Extract alphanumeric tokens (3+ chars)
    - Preserve compound words (kebab-case, snake_case, camelCase)
    """
    if not text:
        return []
    
    # Convert to lowercase
    text = text.lower()
    
    # Replace common separators with spaces for tokenization
    text = re.sub(r'[-_]', ' ', text)
    
    # Split camelCase
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    
    # Extract tokens (3+ alphanumeric chars)
    tokens = re.findall(r'\b[a-z][a-z0-9]{2,}\b', text)
    
    # Also extract compound terms as single tokens
    compound_terms = re.findall(r'\b[a-z]+[-_][a-z]+\b', text)
    
    # Extract acronyms (2+ uppercase chars)
    acronyms = re.findall(r'\b[A-Z]{2,}\b', text.lower())
    
    all_tokens = tokens + compound_terms + acronyms
    
    # Deduplicate while preserving order
    seen = set()
    result = []
    for token in all_tokens:
        if token not in seen:
            seen.add(token)
            result.append(token)
    
    return result


def load_inverted_index() -> Dict:
    """Load the inverted index from disk."""
    if not INVERTED_INDEX_PATH.exists():
        return {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat(),
            "totalMessages": 0,
            "totalTokens": 0,
            "sessions": {},
            "index": {}  # token -> [{session_id, message_idx, timestamp}]
        }
    
    with open(INVERTED_INDEX_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_inverted_index(index: Dict) -> None:
    """Save the inverted index to disk atomically."""
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Write to temp file first (atomic write)
    temp_path = INVERTED_INDEX_PATH.with_suffix('.tmp')
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2)
    
    # Atomic rename
    temp_path.replace(INVERTED_INDEX_PATH)


def get_last_indexed_message(session_id: str, index: Dict) -> Tuple[int, Optional[str]]:
    """
    Get the last indexed message index and timestamp for a session.
    
    Returns:
        (last_message_index, last_timestamp) - (-1, None) if never indexed
    """
    session_meta = index.get("sessions", {}).get(session_id, {})
    last_idx = session_meta.get("lastMessageIndex", -1)
    last_ts = session_meta.get("lastTimestamp")
    return last_idx, last_ts


def read_new_messages(session_file: Path, last_indexed: int) -> List[Dict]:
    """
    Read only NEW messages from session file since last_indexed.
    
    Args:
        session_file: Path to the session JSONL file
        last_indexed: Last message index that was indexed (-1 = none)
    
    Returns:
        List of new message records with their indices
    """
    new_messages = []
    
    if not session_file.exists():
        return new_messages
    
    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f):
                if idx <= last_indexed:
                    continue  # Skip already indexed messages
                
                line = line.strip()
                if not line:
                    continue
                
                try:
                    record = json.loads(line)
                    # Only index message records
                    if record.get('type') == 'message':
                        record['_message_index'] = idx
                        new_messages.append(record)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error reading session file: {e}", file=sys.stderr)
    
    return new_messages


def extract_text_from_message(record: Dict) -> str:
    """Extract searchable text from a message record."""
    msg = record.get('message', {})
    content = msg.get('content', [])
    
    texts = []
    
    if isinstance(content, str):
        texts.append(content)
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                if block.get('type') == 'text':
                    texts.append(block.get('text', ''))
                elif block.get('type') == 'tool_result':
                    # Include tool results for better searchability
                    content_val = block.get('content', {})
                    if isinstance(content_val, dict):
                        texts.append(content_val.get('text', ''))
                    elif isinstance(content_val, str):
                        texts.append(content_val)
    
    # Also include tool calls
    if msg.get('role') == 'assistant' and 'tool_calls' in msg:
        for tc in msg.get('tool_calls', []):
            if isinstance(tc, dict):
                func = tc.get('function', {})
                texts.append(func.get('name', ''))
                texts.append(func.get('arguments', ''))
    
    return ' '.join(texts)


def update_index_with_messages(
    index: Dict,
    session_id: str,
    messages: List[Dict]
) -> Tuple[int, int, float]:
    """
    Add new messages to the inverted index.
    
    Args:
        index: The inverted index dict
        session_id: Session identifier
        messages: List of new message records
    
    Returns:
        (messages_added, tokens_added, total_time_ms)
    """
    start_time = time.time()
    messages_added = 0
    tokens_added = 0
    
    # Initialize session metadata if new
    if session_id not in index.get("sessions", {}):
        index["sessions"][session_id] = {
            "firstIndexed": datetime.now().isoformat(),
            "lastMessageIndex": -1,
            "messageCount": 0,
            "tokenCount": 0
        }
    
    session_meta = index["sessions"][session_id]
    last_idx = session_meta.get("lastMessageIndex", -1)
    
    for record in messages:
        msg_idx = record.get('_message_index', 0)
        
        # Skip if already indexed (shouldn't happen with proper filtering)
        if msg_idx <= last_idx:
            continue
        
        # Extract text and tokenize
        text = extract_text_from_message(record)
        tokens = tokenize_text(text)
        
        # Get timestamp
        timestamp = record.get('timestamp')
        if timestamp:
            try:
                if isinstance(timestamp, (int, float)):
                    timestamp = datetime.fromtimestamp(
                        timestamp / 1000 if timestamp > 1e12 else timestamp
                    ).isoformat()
            except:
                timestamp = datetime.now().isoformat()
        else:
            timestamp = datetime.now().isoformat()
        
        # Add to index
        for token in tokens:
            if token not in index["index"]:
                index["index"][token] = []
            
            index["index"][token].append({
                "session_id": session_id,
                "message_idx": msg_idx,
                "timestamp": timestamp
            })
            tokens_added += 1
        
        # Update session metadata
        last_idx = msg_idx
        messages_added += 1
    
    # Update session metadata
    session_meta["lastMessageIndex"] = last_idx
    session_meta["lastIndexed"] = datetime.now().isoformat()
    session_meta["messageCount"] = session_meta.get("messageCount", 0) + messages_added
    session_meta["tokenCount"] = session_meta.get("tokenCount", 0) + tokens_added
    
    # Update global stats
    index["totalMessages"] = index.get("totalMessages", 0) + messages_added
    index["totalTokens"] = index.get("totalTokens", 0) + tokens_added
    index["updated"] = datetime.now().isoformat()
    
    total_time_ms = (time.time() - start_time) * 1000
    
    return messages_added, tokens_added, total_time_ms


def update_inverted_index(session_id: str, session_file_path: str) -> Dict:
    """
    Main entry point: update the inverted index with new messages from a session.
    
    Args:
        session_id: The session identifier
        session_file_path: Path to the session JSONL file
    
    Returns:
        Result dict with stats
    """
    session_file = Path(session_file_path)
    
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Acquire lock for concurrent safety
    lock_file = get_lock_file()
    
    with FileLock(lock_file, timeout=30.0):
        # Load existing index
        index = load_inverted_index()
        
        # Find last indexed message for this session
        last_idx, last_ts = get_last_indexed_message(session_id, index)
        
        # Read only new messages
        new_messages = read_new_messages(session_file, last_idx)
        
        if not new_messages:
            return {
                "success": True,
                "session_id": session_id,
                "messages_added": 0,
                "tokens_added": 0,
                "time_ms": 0,
                "status": "no_new_messages"
            }
        
        # Update index with new messages
        messages_added, tokens_added, update_time_ms = update_index_with_messages(
            index, session_id, new_messages
        )
        
        # Save updated index
        save_start = time.time()
        save_inverted_index(index)
        save_time_ms = (time.time() - save_start) * 1000
        
        total_time_ms = update_time_ms + save_time_ms
        
        # Calculate per-message latency
        per_message_ms = total_time_ms / messages_added if messages_added > 0 else 0
        
        return {
            "success": True,
            "session_id": session_id,
            "messages_added": messages_added,
            "tokens_added": tokens_added,
            "time_ms": round(total_time_ms, 2),
            "per_message_ms": round(per_message_ms, 2),
            "save_time_ms": round(save_time_ms, 2),
            "status": "updated",
            "last_message_index": index["sessions"][session_id]["lastMessageIndex"]
        }


def main():
    parser = argparse.ArgumentParser(
        description="Incrementally update inverted index with new session messages"
    )
    parser.add_argument("session_id", help="Session identifier")
    parser.add_argument("session_file_path", help="Path to session JSONL file")
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output result as JSON"
    )
    parser.add_argument(
        "--silent", "-s",
        action="store_true",
        help="Silent mode (no output unless error)"
    )
    
    args = parser.parse_args()
    
    try:
        result = update_inverted_index(args.session_id, args.session_file_path)
        
        if args.json:
            print(json.dumps(result))
        elif not args.silent:
            if result["messages_added"] > 0:
                print(f"✅ Indexed {result['messages_added']} messages "
                      f"({result['tokens_added']} tokens) "
                      f"in {result['time_ms']}ms "
                      f"({result['per_message_ms']}ms/msg)")
            else:
                print(f"ℹ️ No new messages to index for {args.session_id}")
        
        sys.exit(0 if result["success"] else 1)
        
    except Exception as e:
        error_result = {
            "success": False,
            "session_id": args.session_id,
            "error": str(e)
        }
        
        if args.json:
            print(json.dumps(error_result))
        else:
            print(f"❌ Error: {e}", file=sys.stderr)
        
        sys.exit(1)


if __name__ == "__main__":
    main()
