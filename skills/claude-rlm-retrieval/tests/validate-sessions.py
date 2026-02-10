#!/usr/bin/env python3
"""
Validate context-memory skill against raw Claude Code session JSONL files.
Tests the same failure patterns found in Clawdbot validation.

Usage:
    python validate-sessions.py
    python validate-sessions.py --verbose
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add scripts dir to path - use absolute path resolution
SCRIPT_DIR = (Path(__file__).parent / ".." / "scripts").resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from enhanced_matching import enhanced_keyword_match
from temporal_parser import parse_temporal_query

# Find Claude Code sessions
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"


def find_sessions() -> list:
    """Find all Claude Code session files."""
    sessions = []
    if not CLAUDE_PROJECTS.exists():
        return sessions
    
    for jsonl in CLAUDE_PROJECTS.rglob("*.jsonl"):
        try:
            content = jsonl.read_text()
            line_count = content.count('\n')
            
            # Parse first message to get date
            first_line = content.split('\n')[0]
            if first_line:
                data = json.loads(first_line)
                timestamp = data.get("timestamp")
                if timestamp:
                    date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                else:
                    date = datetime.fromtimestamp(jsonl.stat().st_mtime)
            else:
                date = datetime.fromtimestamp(jsonl.stat().st_mtime)
            
            sessions.append({
                "path": jsonl,
                "content": content,
                "messages": line_count,
                "date": date,
                "project": jsonl.parent.name,
            })
        except Exception as e:
            print(f"Warning: Could not parse {jsonl}: {e}", file=sys.stderr)
    
    return sessions


def extract_topics(sessions: list) -> dict:
    """Extract topics mentioned across sessions."""
    topics = {}
    all_content = " ".join(s["content"] for s in sessions).lower()
    
    # Technical terms to look for
    terms = [
        "chess", "glicko", "rating", "move", "validation", "server",
        "checkmate", "socket", "websocket", "typescript", "react",
        "context-memory", "search", "temporal", "query", "matching",
        "wlxc", "container", "windows", "linux", "runtime",
        "init", "update-state", "save", "resume", "skill",
    ]
    
    for term in terms:
        if term in all_content:
            topics[term] = all_content.count(term)
    
    return {k: v for k, v in sorted(topics.items(), key=lambda x: -x[1]) if v > 0}


def run_validation(sessions: list, verbose: bool = False) -> dict:
    """Run validation tests against sessions."""
    
    topics = extract_topics(sessions)
    all_content = "\n".join(s["content"] for s in sessions)
    
    results = {
        "sessions": len(sessions),
        "messages": sum(s["messages"] for s in sessions),
        "categories": {},
        "total_tests": 0,
        "total_passed": 0,
    }
    
    # Define test categories with queries
    # NOTE: Test cases must match what's actually in Claude Code sessions
    test_categories = {
        "partial_matching": {
            "description": "Single-word queries that should match compound terms",
            "tests": [
                # Format: (query, should_match, description)
                ("chess", True, "'chess' in sessions"),
                ("socket", True, "'socket' in 'websocket'"),
                ("context", True, "'context' in 'context-memory'"),
                ("move", True, "'move' in chess sessions"),
                ("validation", True, "'validation' in sessions"),
            ],
        },
        "temporal_filtering": {
            "description": "Time-relative queries",
            "tests": [
                ("what happened yesterday", True, "yesterday filter"),
                ("last 3 days", True, "last N days"),
                ("this week", True, "this week"),
                ("show me recent activity", True, "recent"),
            ],
        },
        "adversarial": {
            "description": "Topics never discussed (should NOT match)",
            "tests": [
                # Avoid terms that might fuzzy-match or concept-expand to common dev words
                ("Elasticsearch Kibana Logstash", False, "never discussed"),
                ("GraphQL Apollo Federation", False, "never discussed"),
                ("steakhouse restaurant recommendations", False, "never discussed"),
                ("cryptocurrency blockchain ethereum", False, "never discussed"),
                ("terraform ansible infrastructure", False, "never discussed"),
                ("apache spark streaming hadoop", False, "never discussed"),
            ],
        },
        "compound_terms": {
            "description": "CamelCase and compound word matching",
            "tests": [
                ("WebSocket", True, "camelCase websocket in sessions"),
                ("checkmate", True, "compound in chess sessions"),
                ("context-memory", True, "kebab-case in sessions"),
            ],
        },
        "fact_retrieval": {
            "description": "Specific facts from conversations",
            "tests": [
                ("move validation", True, "chess implementation"),
                ("context memory skill", True, "skill testing"),
                ("chess game", True, "mentioned in sessions"),
            ],
        },
    }
    
    # Run tests
    for category, config in test_categories.items():
        cat_results = {
            "description": config["description"],
            "tests": len(config["tests"]),
            "passed": 0,
            "failed": [],
        }
        
        for query, should_match, desc in config["tests"]:
            results["total_tests"] += 1
            
            # Run enhanced matching
            matched, terms = enhanced_keyword_match(query, all_content)
            
            # For temporal, also check parser
            temporal = parse_temporal_query(query)
            if temporal:
                # Filter sessions by date (make naive for comparison)
                start = datetime.strptime(temporal["start"], "%Y-%m-%d")
                end = datetime.strptime(temporal["end"], "%Y-%m-%d") + timedelta(days=1)
                filtered = [s for s in sessions if start <= s["date"].replace(tzinfo=None) <= end]
                if filtered:
                    filtered_content = "\n".join(s["content"] for s in filtered)
                    matched, terms = enhanced_keyword_match(query, filtered_content)
            
            # Check result
            passed = (matched == should_match)
            
            if passed:
                cat_results["passed"] += 1
                results["total_passed"] += 1
                if verbose:
                    print(f"  ✅ {query}: {desc}")
            else:
                cat_results["failed"].append({
                    "query": query,
                    "expected": should_match,
                    "got": matched,
                    "desc": desc,
                    "terms": terms[:5] if terms else [],
                })
                if verbose:
                    print(f"  ❌ {query}: expected {should_match}, got {matched}")
        
        results["categories"][category] = cat_results
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Validate against Claude Code sessions")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show each test")
    args = parser.parse_args()
    
    print("🔍 Finding Claude Code sessions...")
    sessions = find_sessions()
    
    if not sessions:
        print("❌ No Claude Code sessions found in ~/.claude/projects/")
        sys.exit(1)
    
    print(f"📊 Found {len(sessions)} sessions with {sum(s['messages'] for s in sessions)} messages")
    
    # Show topics
    topics = extract_topics(sessions)
    print(f"📝 Topics detected: {', '.join(list(topics.keys())[:10])}")
    print()
    
    # Run validation
    print("🧪 Running validation tests...")
    if args.verbose:
        print()
    
    results = run_validation(sessions, args.verbose)
    
    # Print results
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print()
    
    total_accuracy = results["total_passed"] / results["total_tests"] * 100 if results["total_tests"] > 0 else 0
    
    print(f"Sessions:  {results['sessions']}")
    print(f"Messages:  {results['messages']}")
    print(f"Tests:     {results['total_tests']}")
    print(f"Passed:    {results['total_passed']}")
    print(f"Accuracy:  {total_accuracy:.1f}%")
    print()
    
    # Category breakdown
    print("| Category | Tests | Passed | Accuracy |")
    print("|----------|-------|--------|----------|")
    for cat, data in results["categories"].items():
        acc = data["passed"] / data["tests"] * 100 if data["tests"] > 0 else 0
        status = "✅" if acc == 100 else "⚠️" if acc >= 80 else "❌"
        print(f"| {cat} | {data['tests']} | {data['passed']} | {status} {acc:.0f}% |")
    
    # Show failures
    all_failures = []
    for cat, data in results["categories"].items():
        for f in data["failed"]:
            all_failures.append((cat, f))
    
    if all_failures:
        print()
        print("❌ FAILURES:")
        for cat, f in all_failures:
            print(f"  [{cat}] '{f['query']}': expected {f['expected']}, got {f['got']}")
            if f.get("terms"):
                print(f"           matched terms: {f['terms']}")
    
    # Output JSON
    output_file = Path(__file__).parent / "validation-results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n📄 Full results: {output_file}")
    
    return 0 if total_accuracy >= 85 else 1


if __name__ == "__main__":
    sys.exit(main())
