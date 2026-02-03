#!/usr/bin/env python3
"""Analyze validation sessions to extract metrics and generate graphs."""

import json
import re
import os
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Find all sessions with context-memory searches
SESSIONS_DIR = Path.home() / ".openclaw/agents/main/sessions"
OUTPUT_DIR = Path("skills/context-memory/validation-results")

def parse_session(session_path: Path) -> list:
    """Parse a session file and extract validation queries."""
    queries = []
    
    with open(session_path) as f:
        messages = [json.loads(line) for line in f if line.strip()]
    
    for i, msg in enumerate(messages):
        if msg.get("type") != "message":
            continue
        
        message_data = msg.get("message", {})
        role = message_data.get("role")
        
        # Look for user queries that mention context-memory searches
        if role == "user":
            content = message_data.get("content", [])
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text", "")
                    # Match multiple patterns:
                    # 1. Context-memory: "query". Search.
                    # 2. Search for "query"
                    # 3. temporal_search.py "query"
                    patterns = [
                        r'Context-memory:\s*["\']([^"\']+)["\']',
                        r'[Ss]earch\s+(?:for\s+)?["\']([^"\']+)["\']',
                        r'temporal_search\.py\s+["\']([^"\']+)["\']',
                        r'search.*["\']([^"\']{3,50})["\']',  # Generic search with quoted query
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            queries.append({
                                "query": match.group(1),
                                "timestamp": msg.get("timestamp"),
                                "session_id": session_path.stem,
                                "msg_index": i
                            })
                            break
        
        # Also look for tool calls with temporal_search
        elif role == "assistant":
            content = message_data.get("content", [])
            for item in content:
                if isinstance(item, dict) and item.get("type") == "toolCall":
                    args = item.get("arguments", {})
                    cmd = args.get("command", "")
                    if "temporal_search" in cmd:
                        # Extract query from command
                        match = re.search(r'temporal_search\.py\s+["\']([^"\']+)["\']', cmd)
                        if match:
                            queries.append({
                                "query": match.group(1),
                                "timestamp": msg.get("timestamp"),
                                "session_id": session_path.stem,
                                "msg_index": i,
                                "from_tool_call": True
                            })
        
        # Look for tool results with search results
        elif role == "toolResult":
            content = message_data.get("content", [])
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text", "")
                    
                    # Parse search output
                    if "Searching:" in text and "Found" in text:
                        # Extract query
                        query_match = re.search(r'Searching:\s*["\']([^"\']+)["\']', text)
                        # Extract result count
                        found_match = re.search(r'Found\s+(\d+)\s+match', text)
                        # Extract duration from details
                        details = message_data.get("details", {})
                        duration_ms = details.get("durationMs", 0)
                        
                        if query_match and found_match and queries:
                            # Update the last query with results
                            queries[-1].update({
                                "found_count": int(found_match.group(1)),
                                "duration_ms": duration_ms,
                                "has_results": int(found_match.group(1)) > 0,
                                "raw_output": text[:500]  # First 500 chars for context
                            })
    
    return [q for q in queries if "found_count" in q]

def categorize_query(query: str) -> str:
    """Categorize query by type."""
    query_lower = query.lower()
    
    # Adversarial/negative queries (things that shouldn't exist)
    adversarial_patterns = [
        "stripe", "kubernetes", "docker swarm", "terraform", "aws",
        "blockchain", "cryptocurrency", "react native", "flutter"
    ]
    if any(p in query_lower for p in adversarial_patterns):
        return "adversarial"
    
    # Project queries
    project_patterns = ["chessrt", "wlxc", "cat-tic-toe", "openclaw", "clawdbot"]
    if any(p in query_lower for p in project_patterns):
        return "project"
    
    # Technical queries
    technical_patterns = [
        "api", "websocket", "database", "postgres", "redis", "auth",
        "glicko", "rating", "matchmaking", "elo"
    ]
    if any(p in query_lower for p in technical_patterns):
        return "technical"
    
    # People/org queries
    people_patterns = [
        "fei", "logan", "tucker", "vicente", "manager", "team",
        "direct report", "1:1", "meeting"
    ]
    if any(p in query_lower for p in people_patterns):
        return "people"
    
    # Temporal queries
    temporal_patterns = [
        "yesterday", "last week", "today", "recent", "ago"
    ]
    if any(p in query_lower for p in temporal_patterns):
        return "temporal"
    
    # Decision queries
    decision_patterns = [
        "decision", "chose", "decided", "why did we", "rationale"
    ]
    if any(p in query_lower for p in decision_patterns):
        return "decision"
    
    return "general"

def analyze_all_sessions():
    """Analyze all sessions and compile metrics."""
    all_queries = []
    
    # Find sessions with context-memory content
    for session_file in SESSIONS_DIR.glob("*.jsonl"):
        with open(session_file) as f:
            content = f.read()
            if "context-memory" in content.lower() or "temporal_search" in content:
                queries = parse_session(session_file)
                all_queries.extend(queries)
    
    return all_queries

def generate_report(queries: list) -> dict:
    """Generate metrics report from queries."""
    if not queries:
        return {"error": "No queries found"}
    
    # Basic stats
    total = len(queries)
    with_results = sum(1 for q in queries if q.get("has_results"))
    empty_results = total - with_results
    
    # By category
    by_category = defaultdict(lambda: {"total": 0, "found": 0, "durations": []})
    for q in queries:
        cat = categorize_query(q["query"])
        by_category[cat]["total"] += 1
        if q.get("has_results"):
            by_category[cat]["found"] += 1
        by_category[cat]["durations"].append(q.get("duration_ms", 0))
    
    # Latency stats
    durations = [q.get("duration_ms", 0) for q in queries if q.get("duration_ms")]
    avg_latency = sum(durations) / len(durations) if durations else 0
    max_latency = max(durations) if durations else 0
    min_latency = min(durations) if durations else 0
    
    # Category breakdown
    category_stats = {}
    for cat, data in by_category.items():
        cat_durations = data["durations"]
        category_stats[cat] = {
            "total": data["total"],
            "found": data["found"],
            "accuracy": round(data["found"] / data["total"] * 100, 1) if data["total"] > 0 else 0,
            "avg_latency_ms": round(sum(cat_durations) / len(cat_durations)) if cat_durations else 0
        }
    
    return {
        "total_queries": total,
        "queries_with_results": with_results,
        "queries_empty": empty_results,
        "retrieval_rate": round(with_results / total * 100, 1) if total > 0 else 0,
        "latency": {
            "avg_ms": round(avg_latency),
            "min_ms": min_latency,
            "max_ms": max_latency
        },
        "by_category": category_stats,
        "queries": queries[:50]  # Sample of queries
    }

def generate_charts(report: dict, output_dir: Path):
    """Generate matplotlib charts from the report."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        print("matplotlib not installed, skipping charts")
        return
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Category accuracy bar chart
    categories = list(report["by_category"].keys())
    accuracies = [report["by_category"][c]["accuracy"] for c in categories]
    totals = [report["by_category"][c]["total"] for c in categories]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(categories, accuracies, color=['#4CAF50' if a > 80 else '#FFC107' if a > 50 else '#F44336' for a in accuracies])
    ax.set_ylabel('Retrieval Accuracy (%)')
    ax.set_xlabel('Query Category')
    ax.set_title(f'Context-Memory Live Validation: Retrieval by Category\n({report["total_queries"]} queries)')
    ax.set_ylim(0, 105)
    
    # Add count labels on bars
    for bar, total in zip(bars, totals):
        height = bar.get_height()
        ax.annotate(f'n={total}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(output_dir / "accuracy-by-category.png", dpi=150)
    plt.close()
    
    # 2. Latency distribution
    if report.get("queries"):
        durations = [q.get("duration_ms", 0) for q in report["queries"] if q.get("duration_ms")]
        if durations:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.hist(durations, bins=20, color='#2196F3', edgecolor='white')
            ax.axvline(report["latency"]["avg_ms"], color='red', linestyle='--', label=f'Avg: {report["latency"]["avg_ms"]}ms')
            ax.set_xlabel('Latency (ms)')
            ax.set_ylabel('Query Count')
            ax.set_title('Search Latency Distribution')
            ax.legend()
            plt.tight_layout()
            plt.savefig(output_dir / "latency-distribution.png", dpi=150)
            plt.close()
    
    # 3. Summary pie chart
    fig, ax = plt.subplots(figsize=(8, 8))
    sizes = [report["queries_with_results"], report["queries_empty"]]
    labels = [f'Found ({report["queries_with_results"]})', f'Empty ({report["queries_empty"]})']
    colors = ['#4CAF50', '#9E9E9E']
    ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    ax.set_title(f'Live Validation Results\n{report["total_queries"]} queries, {report["retrieval_rate"]}% retrieval rate')
    plt.tight_layout()
    plt.savefig(output_dir / "results-summary.png", dpi=150)
    plt.close()
    
    print(f"Charts saved to {output_dir}")

def main():
    print("Analyzing validation sessions...")
    
    queries = analyze_all_sessions()
    print(f"Found {len(queries)} validation queries")
    
    report = generate_report(queries)
    
    # Save report
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / "validation-report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Report saved to {report_path}")
    
    # Generate charts
    generate_charts(report, OUTPUT_DIR)
    
    # Print summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    print(f"Total queries: {report['total_queries']}")
    print(f"Retrieval rate: {report['retrieval_rate']}%")
    print(f"Average latency: {report['latency']['avg_ms']}ms")
    print("\nBy category:")
    for cat, stats in report.get("by_category", {}).items():
        print(f"  {cat}: {stats['accuracy']}% ({stats['found']}/{stats['total']})")

if __name__ == "__main__":
    main()
