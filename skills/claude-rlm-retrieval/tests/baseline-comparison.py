#!/usr/bin/env python3
"""
Compare baseline (grep/contains) vs skill (enhanced matching) accuracy.
Outputs numbers for the blog post charts.

Usage:
    python baseline-comparison.py
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add scripts dir to path
SCRIPT_DIR = (Path(__file__).parent / ".." / "scripts").resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from enhanced_matching import enhanced_keyword_match
from temporal_parser import parse_temporal_query

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
            })
        except Exception:
            pass
    
    return sessions


def baseline_match(query: str, content: str) -> bool:
    """Baseline: simple grep/contains matching (case-insensitive)."""
    query_lower = query.lower()
    content_lower = content.lower()
    
    # Split query into words and check if ALL words are in content
    words = query_lower.split()
    return all(word in content_lower for word in words)


def run_comparison(sessions: list) -> dict:
    """Run both baseline and skill tests."""
    
    all_content = "\n".join(s["content"] for s in sessions)
    
    # Test suite - based on ACTUAL content in Claude Code sessions
    # Sessions contain: chess game, move validation, WLXC containers, context-memory testing
    tests = [
        # Partial matching (should match - confirmed in sessions)
        ("chess", True, "partial"),
        ("socket", True, "partial"),  # websocket in sessions
        ("context", True, "partial"),  # context-memory mentioned
        ("move", True, "partial"),
        ("validation", True, "partial"),
        ("skill", True, "partial"),
        ("server", True, "partial"),
        ("game", True, "partial"),
        ("wlxc", True, "partial"),  # WLXC container project
        ("container", True, "partial"),
        
        # Compound terms (should match)
        ("WebSocket", True, "compound"),
        ("checkmate", True, "compound"),
        ("context-memory", True, "compound"),
        ("update-state", True, "compound"),
        ("move validation", True, "compound"),
        
        # Fact retrieval (should match)
        ("chess move validation", True, "fact"),
        ("context memory skill", True, "fact"),
        ("chess game", True, "fact"),
        ("WLXC container", True, "fact"),
        
        # Adversarial (should NOT match - not in sessions)
        # Note: Avoid queries with very common dev terms (python, rest, app) that may legitimately exist
        ("MongoDB replication sharding", False, "adversarial"),
        ("Kubernetes deployment pods", False, "adversarial"),
        ("Elasticsearch Kibana Logstash", False, "adversarial"),
        ("GraphQL Apollo Federation", False, "adversarial"),
        ("steakhouse restaurant recommendations", False, "adversarial"),
        ("cryptocurrency blockchain ethereum", False, "adversarial"),
        ("terraform ansible infrastructure", False, "adversarial"),
        ("apache spark streaming hadoop", False, "adversarial"),
        ("quantum computing qubits entanglement", False, "adversarial"),
        ("flutter dart ios android", False, "adversarial"),
        ("redis memcached caching", False, "adversarial"),
        ("nginx loadbalancer proxy", False, "adversarial"),
    ]
    
    baseline_results = {"passed": 0, "total": 0, "categories": {}}
    skill_results = {"passed": 0, "total": 0, "categories": {}}
    
    for query, should_match, category in tests:
        baseline_results["total"] += 1
        skill_results["total"] += 1
        
        # Initialize category
        for results in [baseline_results, skill_results]:
            if category not in results["categories"]:
                results["categories"][category] = {"passed": 0, "total": 0}
            results["categories"][category]["total"] += 1
        
        # Baseline: simple contains
        baseline_matched = baseline_match(query, all_content)
        baseline_correct = (baseline_matched == should_match)
        if baseline_correct:
            baseline_results["passed"] += 1
            baseline_results["categories"][category]["passed"] += 1
        
        # Skill: enhanced matching
        skill_matched, _ = enhanced_keyword_match(query, all_content)
        skill_correct = (skill_matched == should_match)
        if skill_correct:
            skill_results["passed"] += 1
            skill_results["categories"][category]["passed"] += 1
    
    return {
        "baseline": baseline_results,
        "skill": skill_results,
        "sessions": len(sessions),
        "messages": sum(s["messages"] for s in sessions),
        "tests": len(tests),
    }


def main():
    print("🔍 Finding Claude Code sessions...")
    sessions = find_sessions()
    
    if not sessions:
        print("❌ No Claude Code sessions found")
        return 1
    
    print(f"📊 Found {len(sessions)} sessions, {sum(s['messages'] for s in sessions)} messages")
    print()
    
    print("🧪 Running comparison tests...")
    results = run_comparison(sessions)
    
    baseline_acc = results["baseline"]["passed"] / results["baseline"]["total"] * 100
    skill_acc = results["skill"]["passed"] / results["skill"]["total"] * 100
    improvement = skill_acc - baseline_acc
    
    print()
    print("=" * 60)
    print("CLAUDE CODE BASELINE COMPARISON")
    print("=" * 60)
    print()
    print(f"Total tests:     {results['tests']}")
    print(f"Sessions:        {results['sessions']}")
    print(f"Messages:        {results['messages']}")
    print()
    print(f"📊 BASELINE (grep/contains): {baseline_acc:.1f}%")
    print(f"📊 WITH SKILL (enhanced):    {skill_acc:.1f}%")
    print(f"📈 IMPROVEMENT:              +{improvement:.1f}%")
    print()
    
    # Category breakdown
    print("| Category | Baseline | Skill | Δ |")
    print("|----------|----------|-------|---|")
    for cat in results["baseline"]["categories"]:
        b_cat = results["baseline"]["categories"][cat]
        s_cat = results["skill"]["categories"][cat]
        b_acc = b_cat["passed"] / b_cat["total"] * 100 if b_cat["total"] > 0 else 0
        s_acc = s_cat["passed"] / s_cat["total"] * 100 if s_cat["total"] > 0 else 0
        delta = s_acc - b_acc
        delta_str = f"+{delta:.0f}%" if delta > 0 else f"{delta:.0f}%"
        print(f"| {cat:12} | {b_acc:5.0f}% | {s_acc:4.0f}% | {delta_str} |")
    
    print()
    print("=" * 60)
    print("NUMBERS FOR generate-baseline-charts.py:")
    print("=" * 60)
    print()
    print("# Claude Code data (from baseline-comparison.py)")
    print("claude_code_data = {")
    print(f'    "Baseline (grep)": {baseline_acc:.1f},')
    print(f'    "With Skill": {skill_acc:.1f},')
    print("}")
    print()
    print("# Claude Code categories")
    print("claude_categories = {")
    for cat in ["partial", "adversarial", "compound", "fuzzy"]:
        if cat in results["baseline"]["categories"]:
            b_cat = results["baseline"]["categories"][cat]
            s_cat = results["skill"]["categories"][cat]
            b_acc = int(b_cat["passed"] / b_cat["total"] * 100) if b_cat["total"] > 0 else 0
            s_acc = int(s_cat["passed"] / s_cat["total"] * 100) if s_cat["total"] > 0 else 0
            print(f'    "{cat}": ({b_acc}, {s_acc}),')
    print("}")
    
    # Save results
    output_file = Path(__file__).parent / "baseline-comparison-results.json"
    with open(output_file, "w") as f:
        json.dump({
            "baseline_accuracy": baseline_acc,
            "skill_accuracy": skill_acc,
            "improvement": improvement,
            "tests": results["tests"],
            "sessions": results["sessions"],
            "messages": results["messages"],
            "baseline": results["baseline"],
            "skill": results["skill"],
        }, f, indent=2)
    print(f"\n📄 Saved: {output_file}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
