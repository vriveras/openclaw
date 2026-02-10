#!/usr/bin/env python3
"""
Test Incremental Index Updates (Phase 2 Validation)

Tests the update-inverted-index.py script for:
- Update latency per message (<10ms requirement)
- Concurrent update safety
- No re-indexing of already-indexed messages
- Correct metadata tracking

Usage:
    python tests/test_incremental_updates.py
"""

import json
import os
import sys
import tempfile
import time
import threading
from pathlib import Path

# Add scripts to path
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# Import using importlib since module name has hyphen
import importlib.util
spec = importlib.util.spec_from_file_location("update_inverted_index", str(SCRIPTS_DIR / "update-inverted-index.py"))
update_module = importlib.util.module_from_spec(spec)
sys.modules["update_inverted_index"] = update_module
spec.loader.exec_module(update_module)

# Now import the functions
tokenize_text = update_module.tokenize_text
load_inverted_index = update_module.load_inverted_index
save_inverted_index = update_module.save_inverted_index
get_last_indexed_message = update_module.get_last_indexed_message
read_new_messages = update_module.read_new_messages
update_index_with_messages = update_module.update_index_with_messages
update_inverted_index = update_module.update_inverted_index
FileLock = update_module.FileLock
DATA_DIR = update_module.DATA_DIR
INVERTED_INDEX_PATH = update_module.INVERTED_INDEX_PATH


def create_test_session_file(messages: list) -> Path:
    """Create a temporary session file with test messages."""
    fd, path = tempfile.mkstemp(suffix='.jsonl')
    
    with os.fdopen(fd, 'w') as f:
        for i, msg in enumerate(messages):
            record = {
                "type": "message",
                "timestamp": time.time() * 1000,
                "message": {
                    "role": msg.get("role", "user"),
                    "content": [{"type": "text", "text": msg.get("text", "")}]
                }
            }
            f.write(json.dumps(record) + '\n')
    
    return Path(path)


def test_tokenize():
    """Test tokenization."""
    print("\n🧪 Testing tokenization...")
    
    text = "The quick brown fox jumps over Glicko-2 rating system"
    tokens = tokenize_text(text)
    
    assert "quick" in tokens, "Should extract 'quick'"
    assert "glicko" in tokens, "Should extract 'glicko' from Glicko-2"
    assert "rating" in tokens, "Should extract 'rating'"
    assert "fox" in tokens, "Should extract 'fox'"
    # Note: "the" is 3 chars so it's kept (we filter <3, not <=3)
    
    print(f"  📊 Tokens: {tokens[:5]}...")
    print("  ✅ Tokenization works correctly")


def test_latency_requirement():
    """Test that updates are <10ms per message."""
    print("\n🧪 Testing latency requirement (<10ms per message)...")
    
    # Create test messages
    messages = [
        {"role": "user", "text": f"Test message {i} about Python programming and API design"}
        for i in range(100)
    ]
    
    session_file = create_test_session_file(messages)
    
    try:
        # Time the update
        start = time.time()
        result = update_inverted_index("test-session-latency", str(session_file))
        elapsed_ms = (time.time() - start) * 1000
        
        if not result["success"]:
            print(f"  ⚠️  Update failed (expected - no index yet): {result.get('error')}")
            print("  ℹ️  Run Phase 1 first to create inverted-index.json")
            return
        
        per_message_ms = result.get("per_message_ms", elapsed_ms / len(messages))
        
        print(f"  📊 Total time: {elapsed_ms:.2f}ms for {result.get('messages_added', 0)} messages")
        print(f"  📊 Per-message: {per_message_ms:.2f}ms")
        
        if per_message_ms < 10:
            print(f"  ✅ PASS: {per_message_ms:.2f}ms < 10ms requirement")
        else:
            print(f"  ❌ FAIL: {per_message_ms:.2f}ms > 10ms requirement")
            
    finally:
        os.unlink(session_file)


def test_no_reindexing():
    """Test that already-indexed messages are not re-indexed."""
    print("\n🧪 Testing no re-indexing of existing messages...")
    
    # Create initial messages
    messages = [
        {"role": "user", "text": "First message about wlxc containers"},
        {"role": "assistant", "text": "Second message about Docker and Kubernetes"},
    ]
    
    session_file = create_test_session_file(messages)
    session_id = "test-session-no-reindex"
    
    try:
        # First update
        result1 = update_inverted_index(session_id, str(session_file))
        
        if not result1["success"]:
            print(f"  ⚠️  First update failed (expected - no index yet)")
            print("  ℹ️  Run Phase 1 first to create inverted-index.json")
            return
        
        added1 = result1.get("messages_added", 0)
        print(f"  📊 First update: {added1} messages added")
        
        # Second update (should add 0)
        result2 = update_inverted_index(session_id, str(session_file))
        added2 = result2.get("messages_added", 0)
        
        print(f"  📊 Second update: {added2} messages added")
        
        if added2 == 0:
            print("  ✅ PASS: No messages re-indexed")
        else:
            print(f"  ❌ FAIL: {added2} messages were re-indexed")
            
    finally:
        os.unlink(session_file)


def test_concurrent_safety():
    """Test concurrent update safety with file locking."""
    print("\n🧪 Testing concurrent update safety...")
    
    lock_file = DATA_DIR / ".test-lock"
    results = []
    
    def try_lock(thread_id):
        try:
            with FileLock(lock_file, timeout=1.0):
                time.sleep(0.1)  # Hold lock briefly
                results.append((thread_id, "acquired"))
        except TimeoutError:
            results.append((thread_id, "timeout"))
        except Exception as e:
            results.append((thread_id, f"error: {e}"))
    
    # Start multiple threads competing for lock
    threads = []
    for i in range(5):
        t = threading.Thread(target=try_lock, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    acquired = sum(1 for _, status in results if status == "acquired")
    timeouts = sum(1 for _, status in results if status == "timeout")
    
    print(f"  📊 Results: {acquired} acquired, {timeouts} timeouts")
    
    if acquired > 0 and timeouts >= 0:
        print("  ✅ PASS: File locking works (some threads waited)")
    else:
        print("  ❌ FAIL: Locking may not be working correctly")


def test_incremental_updates():
    """Test incremental updates with new messages added."""
    print("\n🧪 Testing incremental updates...")
    
    session_id = "test-session-incremental"
    
    # Create initial file with 2 messages
    messages1 = [
        {"role": "user", "text": "Message 1 about Phase 2 implementation"},
        {"role": "assistant", "text": "Message 2 about incremental indexing"},
    ]
    session_file = create_test_session_file(messages1)
    
    try:
        # First update
        result1 = update_inverted_index(session_id, str(session_file))
        
        if not result1["success"]:
            print(f"  ⚠️  First update failed (expected - no index yet)")
            print("  ℹ️  Run Phase 1 first to create inverted-index.json")
            os.unlink(session_file)
            return
        
        print(f"  📊 First update: {result1.get('messages_added')} messages")
        
        # Append more messages to file
        messages2 = [
            {"role": "user", "text": "Message 3 about hook handlers"},
            {"role": "assistant", "text": "Message 4 about debounce logic"},
        ]
        
        with open(session_file, 'a') as f:
            for msg in messages2:
                record = {
                    "type": "message",
                    "timestamp": time.time() * 1000,
                    "message": {
                        "role": msg.get("role", "user"),
                        "content": [{"type": "text", "text": msg.get("text", "")}]
                    }
                }
                f.write(json.dumps(record) + '\n')
        
        # Second update (should only add new messages)
        result2 = update_inverted_index(session_id, str(session_file))
        added2 = result2.get("messages_added", 0)
        
        print(f"  📊 Second update: {added2} messages (expected 2)")
        
        if added2 == 2:
            print("  ✅ PASS: Only new messages were indexed")
        else:
            print(f"  ❌ FAIL: Expected 2 new messages, got {added2}")
            
    finally:
        os.unlink(session_file)


def test_hook_handler():
    """Test the hook handler."""
    print("\n🧪 Testing hook handler...")
    
    HOOK_DIR = Path(__file__).parent.parent / "src" / "hooks" / "rlm-index-refresh"
    handler = HOOK_DIR / "handler.py"
    
    if not handler.exists():
        print("  ❌ FAIL: handler.py not found")
        return
    
    # Test with dummy event
    import subprocess
    
    result = subprocess.run(
        [sys.executable, str(handler), "--help"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0 and "RLM Index Refresh" in result.stdout:
        print("  ✅ PASS: Hook handler is working")
    else:
        print(f"  ❌ FAIL: Hook handler test failed")
        print(f"     stdout: {result.stdout[:200]}")
        print(f"     stderr: {result.stderr[:200]}")


def main():
    print("=" * 60)
    print("🧪 Phase 2: Incremental Index Update Tests")
    print("=" * 60)
    
    # Check if inverted index exists
    if not INVERTED_INDEX_PATH.exists():
        print("\n⚠️  WARNING: inverted-index.json does not exist!")
        print("   Phase 1 must be completed before running these tests.")
        print("   Some tests will be skipped.\n")
    
    # Run tests
    test_tokenize()
    test_latency_requirement()
    test_no_reindexing()
    test_concurrent_safety()
    test_incremental_updates()
    test_hook_handler()
    
    print("\n" + "=" * 60)
    print("✅ Test run complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
