#!/usr/bin/env python3
"""
RLM Index Refresh Hook Handler

Listens for `session:transcript:update` events and triggers incremental
index updates with debounce/cooldown logic.

Usage:
    # Called by OpenClaw when transcript updates
    python handler.py --event session:transcript:update --session-id <id> --file-path <path>
    
    # Or as a module
    from handler import handle_transcript_update
    handle_transcript_update(session_id, file_path)

Debounce strategy:
    - 30-second cooldown per session (configurable)
    - 5-second debounce for rapid updates
    - Queue-based processing for concurrent updates
"""

import argparse
import json
import os
import sys
import time
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Add scripts dir to path for imports
HOOK_DIR = Path(__file__).parent
SRC_DIR = HOOK_DIR.parent.parent
SCRIPTS_DIR = SRC_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# Import the update function
try:
    from update_inverted_index import update_inverted_index
except ImportError:
    # Fallback: subprocess call
    UPDATE_SCRIPT = str(SCRIPTS_DIR / "update-inverted-index.py")
    USE_SUBPROCESS = True
else:
    USE_SUBPROCESS = False


# Configuration
DEBOUNCE_SECONDS = 5.0       # Wait for rapid updates to settle
COOLDOWN_SECONDS = 30.0      # Minimum time between updates for same session
MAX_QUEUE_SIZE = 100         # Prevent memory issues

# State tracking
_last_update_time: Dict[str, float] = {}
_pending_updates: Dict[str, dict] = {}
_update_lock = threading.Lock()
_debounce_timers: Dict[str, threading.Timer] = {}


def get_state_file() -> Path:
    """Get the state file path for tracking update times."""
    return HOOK_DIR / ".hook-state.json"


def load_state() -> Dict:
    """Load persistent state (last update times)."""
    state_file = get_state_file()
    if state_file.exists():
        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"lastUpdates": {}}


def save_state(state: Dict) -> None:
    """Save persistent state atomically."""
    state_file = get_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    
    temp_file = state_file.with_suffix('.tmp')
    with open(temp_file, 'w') as f:
        json.dump(state, f, indent=2)
    temp_file.replace(state_file)


def is_in_cooldown(session_id: str) -> bool:
    """Check if session is in cooldown period."""
    state = load_state()
    last_update = state.get("lastUpdates", {}).get(session_id, 0)
    elapsed = time.time() - last_update
    return elapsed < COOLDOWN_SECONDS


def record_update_time(session_id: str) -> None:
    """Record that we just updated this session."""
    state = load_state()
    state["lastUpdates"][session_id] = time.time()
    save_state(state)


def run_update_script(session_id: str, file_path: str) -> dict:
    """Run the update script (subprocess fallback)."""
    import subprocess
    
    cmd = [
        sys.executable,
        UPDATE_SCRIPT,
        session_id,
        file_path,
        "--json"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return {
                "success": False,
                "error": result.stderr or "Unknown error"
            }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Update script timed out after 60s"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def do_update(session_id: str, file_path: str) -> dict:
    """Execute the actual index update."""
    if USE_SUBPROCESS:
        result = run_update_script(session_id, file_path)
    else:
        result = update_inverted_index(session_id, file_path)
    
    # Record update time on success
    if result.get("success"):
        record_update_time(session_id)
    
    return result


def debounced_update(session_id: str, file_path: str) -> None:
    """
    Schedule an update with debounce.
    
    If multiple updates come in rapidly, only the last one executes.
    """
    with _update_lock:
        # Cancel existing timer for this session
        if session_id in _debounce_timers:
            _debounce_timers[session_id].cancel()
        
        # Store pending update
        _pending_updates[session_id] = {
            "session_id": session_id,
            "file_path": file_path,
            "queued_at": time.time()
        }
        
        # Check queue size
        if len(_pending_updates) > MAX_QUEUE_SIZE:
            # Remove oldest pending update
            oldest = min(_pending_updates.items(), key=lambda x: x[1]["queued_at"])
            del _pending_updates[oldest[0]]
        
        # Schedule new timer
        def execute():
            with _update_lock:
                # Check if still pending (might have been cancelled)
                if session_id not in _pending_updates:
                    return
                
                # Check cooldown
                if is_in_cooldown(session_id):
                    # Reschedule for after cooldown
                    remaining = COOLDOWN_SECONDS - (time.time() - load_state()["lastUpdates"].get(session_id, 0))
                    timer = threading.Timer(max(0.1, remaining), execute)
                    timer.daemon = True
                    _debounce_timers[session_id] = timer
                    timer.start()
                    return
                
                # Remove from pending
                del _pending_updates[session_id]
                if session_id in _debounce_timers:
                    del _debounce_timers[session_id]
            
            # Execute update (outside lock)
            do_update(session_id, file_path)
        
        timer = threading.Timer(DEBOUNCE_SECONDS, execute)
        timer.daemon = True
        _debounce_timers[session_id] = timer
        timer.start()


def handle_transcript_update(session_id: str, file_path: str, immediate: bool = False) -> dict:
    """
    Handle a session:transcript:update event.
    
    Args:
        session_id: The session that was updated
        file_path: Path to the session transcript file
        immediate: If True, bypass debounce (use with caution)
    
    Returns:
        Result dict with status
    """
    # Validate inputs
    if not session_id or not file_path:
        return {
            "success": False,
            "error": "Missing session_id or file_path",
            "session_id": session_id
        }
    
    if not Path(file_path).exists():
        return {
            "success": False,
            "error": f"Session file not found: {file_path}",
            "session_id": session_id
        }
    
    # Check cooldown
    if is_in_cooldown(session_id) and not immediate:
        return {
            "success": True,
            "status": "cooldown",
            "session_id": session_id,
            "message": f"Session {session_id} is in cooldown (updates every {COOLDOWN_SECONDS}s)"
        }
    
    if immediate:
        # Execute immediately
        return do_update(session_id, file_path)
    else:
        # Schedule with debounce
        debounced_update(session_id, file_path)
        return {
            "success": True,
            "status": "queued",
            "session_id": session_id,
            "message": f"Update queued (debounce: {DEBOUNCE_SECONDS}s)"
        }


def handle_event(event_type: str, payload: dict) -> dict:
    """
    Generic event handler entry point.
    
    Args:
        event_type: Type of event (e.g., "session:transcript:update")
        payload: Event payload dict
    
    Returns:
        Result dict
    """
    if event_type == "session:transcript:update":
        session_id = payload.get("session_id") or payload.get("sessionId")
        file_path = payload.get("file_path") or payload.get("filePath") or payload.get("path")
        immediate = payload.get("immediate", False)
        
        return handle_transcript_update(session_id, file_path, immediate)
    
    return {
        "success": False,
        "error": f"Unknown event type: {event_type}"
    }


def main():
    parser = argparse.ArgumentParser(
        description="RLM Index Refresh Hook Handler"
    )
    parser.add_argument(
        "--event", "-e",
        required=True,
        help="Event type (e.g., session:transcript:update)"
    )
    parser.add_argument(
        "--session-id", "-s",
        help="Session identifier"
    )
    parser.add_argument(
        "--file-path", "-f",
        help="Path to session transcript file"
    )
    parser.add_argument(
        "--payload", "-p",
        help="JSON payload (alternative to individual args)"
    )
    parser.add_argument(
        "--immediate", "-i",
        action="store_true",
        help="Execute immediately without debounce"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output result as JSON"
    )
    
    args = parser.parse_args()
    
    # Build payload
    if args.payload:
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError as e:
            result = {"success": False, "error": f"Invalid JSON payload: {e}"}
            if args.json:
                print(json.dumps(result))
            else:
                print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
    else:
        payload = {
            "session_id": args.session_id,
            "file_path": args.file_path,
            "immediate": args.immediate
        }
    
    # Handle event
    result = handle_event(args.event, payload)
    
    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result.get("success"):
            status = result.get("status", "ok")
            msg = result.get("message", "")
            if msg:
                print(f"✅ {status}: {msg}")
            else:
                print(f"✅ {status}")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
    
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
