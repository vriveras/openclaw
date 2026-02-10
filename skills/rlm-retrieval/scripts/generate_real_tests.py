#!/usr/bin/env python3
"""
Generate test cases from real session transcripts.

Extracts facts, entities, and decisions from sessions, then generates
queries with ground truth for validation.
"""

import json
import re
import random
from pathlib import Path
from datetime import datetime
from collections import defaultdict

SCRIPTS_DIR = Path(__file__).parent
INDEX_FILE = SCRIPTS_DIR.parent / "memory" / "sessions-index.json"

# Patterns for extracting facts - focus on queryable terms, not raw data
PATTERNS = {
    "project_mention": r'\b(WLXC|wlxc|ChessRT|chessrt|Cat-Tic-Toe|OpenClaw|clawdbot|context-memory|WorkIQ|workiq|Himalaya|BlueBubbles|mcporter|IDC|Alt-Text|bird-tic-toe|qwen-tts|gsd|spec-planner)\b',
    "tech_terms": r'\b(containerd|MongoDB|WebSocket|Glicko-2|Elo|CUDA|PyTorch|ffmpeg|whisper|binfmt|Docker|Kubernetes|gRPC|REST|API|WSL|Linux|Windows|Python|Node|TypeScript|JavaScript|Rust|React|Tailwind|Redis|PostgreSQL|SQLite|JSON|YAML|Markdown)\b',
    "decisions": r'(?:decided|chose|going with|will use|switched to|picked|implemented|built|created|fixed)\s+([^.!?\n]{10,50})',
    "topics": r'\b(triage|inbox|calendar|meeting|email|teams|rating|chess|container|sandbox|policy|config|skill|memory|session|transcri\w+|heartbeat|cron|blog|test|validation|accuracy|compaction|index|search|retrieval|semantic|keyword|fuzzy|temporal)\b',
    "dates": r'\b(202[4-6]-\d{2}-\d{2})\b',
    "people": r'\b(Vicente|Tucker|Logan|Fei|Mark|Chris|Austin|Jon|Tim|George|Angela|Martin|Abhilash|Cary|Gabriel|Pavan|Rajesh|Satya)\b',
    "actions": r'(?:deployed|shipped|merged|committed|pushed|released|published|uploaded|downloaded|installed|configured|fixed|updated|added|removed|changed|created|deleted|moved|renamed)\s+([^.!?\n]{5,40})',
    "phrases": r'\b(working on|looking at|discussing|talking about|thinking about|trying to|need to|want to|going to)\s+([^.!?\n]{5,30})',
}

def load_session_content(session_file: Path, max_chars: int = 50000) -> str:
    """Load session transcript content."""
    content = []
    try:
        with open(session_file, 'r') as f:
            for line in f:
                try:
                    msg = json.loads(line)
                    if msg.get('type') == 'message':
                        text = ''
                        if isinstance(msg.get('message'), dict):
                            mc = msg['message'].get('content', [])
                            if isinstance(mc, list):
                                for block in mc:
                                    if isinstance(block, dict) and block.get('type') == 'text':
                                        text += block.get('text', '') + ' '
                            elif isinstance(mc, str):
                                text = mc
                        elif isinstance(msg.get('message'), str):
                            text = msg['message']
                        if text.strip():
                            content.append(text.strip())
                except json.JSONDecodeError:
                    continue
                if sum(len(c) for c in content) > max_chars:
                    break
    except Exception as e:
        print(f"Error loading {session_file}: {e}")
    return '\n'.join(content)

def extract_facts(content: str, session_id: str, session_date: str) -> list:
    """Extract queryable facts from session content."""
    facts = []
    
    for fact_type, pattern in PATTERNS.items():
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in set(matches):
            if isinstance(match, tuple):
                match = match[0]
            if len(match) > 3:  # Skip very short matches
                facts.append({
                    "type": fact_type,
                    "value": match,
                    "session_id": session_id,
                    "date": session_date
                })
    
    return facts

def generate_queries_from_facts(facts: list) -> list:
    """Generate test queries from extracted facts."""
    test_cases = []
    
    # Group facts by type
    by_type = defaultdict(list)
    for fact in facts:
        by_type[fact["type"]].append(fact)
    
    # Query templates by fact type
    templates = {
        "project_mention": [
            "{value}",
            "{value} project",
            "working on {value}",
            "{value} discussion",
            "{value} work",
        ],
        "tech_terms": [
            "{value}",
            "using {value}",
            "{value} configuration",
            "{value} setup",
        ],
        "topics": [
            "{value}",
            "{value} discussion",
            "about {value}",
        ],
        "decisions": [
            "{value}",
        ],
        "people": [
            "{value}",
            "conversation with {value}",
            "{value} mentioned",
            "talking to {value}",
        ],
        "dates": [
            "on {value}",
            "{value}",
        ],
        "actions": [
            "{value}",
        ],
        "phrases": [
            "{value}",
        ],
    }
    
    for fact_type, type_facts in by_type.items():
        type_templates = templates.get(fact_type, ["{value}"])
        
        for fact in type_facts:
            template = random.choice(type_templates)
            query = template.format(value=fact["value"])
            
            test_cases.append({
                "query": query,
                "expected_session": fact["session_id"],
                "expected_date": fact["date"],
                "fact_type": fact_type,
                "source_value": fact["value"],
            })
    
    return test_cases

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate test cases from real sessions")
    parser.add_argument("--limit", type=int, default=1000, help="Max test cases to generate")
    parser.add_argument("--sessions", type=int, default=50, help="Max sessions to sample")
    parser.add_argument("--output", type=str, default="real_test_cases.json", help="Output file")
    args = parser.parse_args()
    
    # Load index
    with open(INDEX_FILE) as f:
        index = json.load(f)
    
    sessions_dir = Path(index["sessionsDir"])
    sessions = list(index["sessions"].items())
    
    # Sample sessions
    if len(sessions) > args.sessions:
        sessions = random.sample(sessions, args.sessions)
    
    print(f"📂 Processing {len(sessions)} sessions...")
    
    all_facts = []
    for session_id, meta in sessions:
        session_file = sessions_dir / meta["file"]
        if session_file.exists():
            content = load_session_content(session_file)
            facts = extract_facts(content, session_id, meta["date"])
            all_facts.extend(facts)
            print(f"  ✓ {session_id[:8]}... ({len(facts)} facts)")
    
    print(f"\n📊 Extracted {len(all_facts)} total facts")
    
    # Generate test cases
    test_cases = generate_queries_from_facts(all_facts)
    
    # Dedupe by query+session (allow same query targeting different sessions)
    seen = set()
    unique_cases = []
    for tc in test_cases:
        key = (tc["query"].lower(), tc["expected_session"])
        if key not in seen:
            seen.add(key)
            unique_cases.append(tc)
    
    if len(unique_cases) > args.limit:
        unique_cases = random.sample(unique_cases, args.limit)
    
    print(f"✅ Generated {len(unique_cases)} unique test cases")
    
    # Save
    output_path = SCRIPTS_DIR.parent / "tests" / args.output
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump({
            "generated": datetime.now().isoformat(),
            "total_facts": len(all_facts),
            "total_cases": len(unique_cases),
            "sessions_sampled": len(sessions),
            "cases": unique_cases
        }, f, indent=2)
    
    print(f"💾 Saved to {output_path}")
    
    # Stats by type
    by_type = defaultdict(int)
    for tc in unique_cases:
        by_type[tc["fact_type"]] += 1
    print("\n📈 Cases by type:")
    for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"   {t}: {count}")

if __name__ == "__main__":
    main()
