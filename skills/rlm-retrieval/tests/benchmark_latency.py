#!/usr/bin/env python3
"""
Latency Benchmark: Raw Clawdbot vs Enhanced Hybrid

Measures search latency for:
1. Basic keyword search (raw Clawdbot approach)
2. Enhanced matching (substring + compound + fuzzy + concepts)
3. Full hybrid with temporal filtering

Usage:
    python tests/benchmark_latency.py
    python tests/benchmark_latency.py --iterations 100
"""

import argparse
import json
import time
import re
import sys
from pathlib import Path
from datetime import datetime
from statistics import mean, stdev, median

TESTS_DIR = Path(__file__).parent
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from enhanced_matching import enhanced_keyword_match, normalize_for_matching

# Sample queries for benchmarking
BENCHMARK_QUERIES = [
    # Simple exact match
    ("context-memory", ["context-memory", "retrieval", "search"]),
    ("wlxc", ["wlxc", "container", "windows"]),
    
    # Partial/compound
    ("ReadMessage", ["ReadMessageItem", "email", "message"]),
    ("HostWindows", ["HostWindowsContainer", "container"]),
    
    # Fuzzy
    ("postgres", ["PostgreSQL", "database"]),
    ("javascrpt", ["javascript", "typescript"]),  # Typo
    
    # Concept expansion
    ("glicko", ["rating", "chess", "leaderboard"]),
    ("oauth", ["authentication", "token", "security"]),
    
    # Complex queries
    ("what did we discuss about authentication yesterday", ["oauth", "auth", "token"]),
    ("how does the rating system work in ChessRT", ["glicko", "elo", "rating"]),
]

def load_sample_content():
    """Load sample content for benchmarking."""
    # Load from memory files if available
    workspace = Path.home() / "clawd"
    content_parts = []
    
    # Memory files
    memory_dir = workspace / "memory"
    if memory_dir.exists():
        for f in memory_dir.glob("*.md"):
            try:
                content_parts.append(f.read_text()[:10000])
            except:
                pass
    
    # MEMORY.md
    memory_file = workspace / "MEMORY.md"
    if memory_file.exists():
        try:
            content_parts.append(memory_file.read_text()[:10000])
        except:
            pass
    
    # Add some synthetic content if not enough
    if len(content_parts) < 3:
        content_parts.append("""
        We use context-memory for retrieval with RLM approach.
        The Glicko-2 rating system powers ChessRT leaderboard.
        PostgreSQL is used for the database backend.
        OAuth2 authentication with JWT tokens for security.
        The ReadMessageItem function handles email retrieval.
        HostWindowsContainer manages Windows containers in wlxc.
        JavaScript and TypeScript are used for the frontend.
        """)
    
    return "\n".join(content_parts)

def basic_keyword_search(query: str, content: str, keywords: list) -> list:
    """
    Basic keyword search (simulates raw Clawdbot without enhancements).
    """
    found = []
    content_lower = content.lower()
    
    for kw in keywords:
        if kw.lower() in content_lower:
            found.append(kw)
    
    return found

def enhanced_search(query: str, content: str, keywords: list) -> list:
    """
    Enhanced search with all improvements.
    """
    found = []
    
    for kw in keywords:
        matched, terms = enhanced_keyword_match(
            kw, content,
            use_substring=True,
            use_compound=True,
            use_fuzzy=True,
            use_concepts=True
        )
        if matched:
            found.append(kw)
    
    return found

def benchmark_search(search_fn, queries, content, iterations=50):
    """
    Benchmark a search function.
    
    Returns: dict with timing stats and accuracy
    """
    latencies = []
    total_found = 0
    total_expected = 0
    
    for _ in range(iterations):
        for query, keywords in queries:
            start = time.perf_counter()
            found = search_fn(query, content, keywords)
            end = time.perf_counter()
            
            latencies.append((end - start) * 1000)  # ms
            total_found += len(found)
            total_expected += len(keywords)
    
    return {
        "iterations": iterations * len(queries),
        "total_queries": len(queries),
        "latency_ms": {
            "mean": round(mean(latencies), 3),
            "median": round(median(latencies), 3),
            "stdev": round(stdev(latencies), 3) if len(latencies) > 1 else 0,
            "min": round(min(latencies), 3),
            "max": round(max(latencies), 3),
            "p95": round(sorted(latencies)[int(len(latencies) * 0.95)], 3),
        },
        "recall": round(total_found / total_expected * 100, 1) if total_expected > 0 else 0,
    }

def run_benchmarks(iterations=50):
    """Run all benchmarks and return results."""
    print(f"🔬 Running latency benchmarks ({iterations} iterations)...\n")
    
    content = load_sample_content()
    print(f"   Content size: {len(content):,} chars")
    print(f"   Queries: {len(BENCHMARK_QUERIES)}")
    print()
    
    results = {}
    
    # Basic search (raw Clawdbot approach)
    print("⏱️  Benchmarking: Basic keyword search...")
    results["basic"] = benchmark_search(basic_keyword_search, BENCHMARK_QUERIES, content, iterations)
    print(f"   Mean: {results['basic']['latency_ms']['mean']:.3f}ms, Recall: {results['basic']['recall']}%")
    
    # Enhanced search
    print("⏱️  Benchmarking: Enhanced matching...")
    results["enhanced"] = benchmark_search(enhanced_search, BENCHMARK_QUERIES, content, iterations)
    print(f"   Mean: {results['enhanced']['latency_ms']['mean']:.3f}ms, Recall: {results['enhanced']['recall']}%")
    
    return results

def generate_comparison_table(results):
    """Generate markdown comparison table."""
    basic = results["basic"]
    enhanced = results["enhanced"]
    
    speedup = basic["latency_ms"]["mean"] / enhanced["latency_ms"]["mean"] if enhanced["latency_ms"]["mean"] > 0 else 0
    recall_gain = enhanced["recall"] - basic["recall"]
    
    table = f"""
| Metric | Basic (Raw) | Enhanced (Hybrid) | Change |
|--------|-------------|-------------------|--------|
| **Mean Latency** | {basic['latency_ms']['mean']:.2f}ms | {enhanced['latency_ms']['mean']:.2f}ms | {'+' if enhanced['latency_ms']['mean'] > basic['latency_ms']['mean'] else ''}{((enhanced['latency_ms']['mean'] / basic['latency_ms']['mean']) - 1) * 100:.0f}% |
| **Median Latency** | {basic['latency_ms']['median']:.2f}ms | {enhanced['latency_ms']['median']:.2f}ms | |
| **P95 Latency** | {basic['latency_ms']['p95']:.2f}ms | {enhanced['latency_ms']['p95']:.2f}ms | |
| **Recall** | {basic['recall']:.0f}% | {enhanced['recall']:.0f}% | **+{recall_gain:.0f}%** |
"""
    return table

def main():
    parser = argparse.ArgumentParser(description="Latency benchmark")
    parser.add_argument("--iterations", "-n", type=int, default=50, help="Iterations per query")
    parser.add_argument("--output", "-o", default="tests/benchmark-results.json", help="Output file")
    args = parser.parse_args()
    
    results = run_benchmarks(args.iterations)
    
    # Summary
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    print(generate_comparison_table(results))
    
    # Calculate tradeoff
    basic = results["basic"]
    enhanced = results["enhanced"]
    
    latency_increase = enhanced["latency_ms"]["mean"] - basic["latency_ms"]["mean"]
    recall_increase = enhanced["recall"] - basic["recall"]
    
    print(f"\n📊 Tradeoff Analysis:")
    print(f"   Latency cost: +{latency_increase:.2f}ms per query")
    print(f"   Recall gain: +{recall_increase:.0f}%")
    if latency_increase > 0:
        print(f"   Cost per 1% recall: +{latency_increase / recall_increase:.3f}ms" if recall_increase > 0 else "")
    
    # Save results
    output_path = TESTS_DIR / "benchmark-results.json"
    results["timestamp"] = datetime.now().isoformat()
    results["iterations"] = args.iterations
    
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_path}")

if __name__ == "__main__":
    main()
