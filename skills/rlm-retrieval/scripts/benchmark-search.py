#!/usr/bin/env python3
"""
Benchmark Search Performance

Runs test queries and measures latency statistics.
Supports both scan-based (current) and index-based (future) search methods.

Usage:
    python scripts/benchmark-search.py --queries 100 --output report.json
    python scripts/benchmark-search.py --method indexed --queries 50
    python scripts/benchmark-search.py --test-queries  # Use predefined test set
"""

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

# Import from sibling modules
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from temporal_search import temporal_search, load_sessions_index
from enhanced_matching import enhanced_keyword_match

# Default test queries for benchmarking
DEFAULT_TEST_QUERIES = [
    "rlm retrieval latency",
    "what did we do yesterday",
    "Glicko chess rating",
    "OpenClaw fork changes",
    "SEO fixes blog page",
    "context memory skill",
    "compaction survival",
    "wlxc container runtime",
    # Additional queries to reach 100
    "authentication oauth flow",
    "session transcript dump",
    "inverted index build",
    "temporal parser query",
    "enhanced matching algorithm",
    "chess rating system",
    "docker container deployment",
    "kubernetes pod scaling",
    "ci/cd pipeline setup",
    "postgresql database migration",
    "redis cache configuration",
    "nginx reverse proxy",
    "ssl certificate renewal",
    "jwt token validation",
    "api rate limiting",
    "webhook event handling",
    "message queue worker",
    "background job processor",
    "scheduled task cron",
    "log aggregation system",
    "monitoring dashboard",
    "alert notification channel",
    "error tracking sentry",
    "performance profiling",
    "memory leak detection",
    "cpu usage optimization",
    "disk space cleanup",
    "backup restore strategy",
    "disaster recovery plan",
    "load balancer health",
    "cdn cache invalidation",
    "dns record update",
    "firewall rule config",
    "vpn tunnel setup",
    "ssh key management",
    "git repository clone",
    "branch merge conflict",
    "pull request review",
    "code linting rules",
    "unit test coverage",
    "integration test suite",
    "end to end testing",
    "dependency vulnerability scan",
    "license compliance check",
    "documentation generation",
    "api schema validation",
    "graphql query optimization",
    "websocket connection pool",
    "sse event stream",
    "grpc service definition",
    "protobuf message encoding",
    "json schema validation",
    "xml parser configuration",
    "csv data import",
    "pdf report generation",
    "image resize processing",
    "video transcoding job",
    "audio waveform analysis",
    "machine learning model",
    "neural network training",
    "dataset preprocessing",
    "feature engineering pipeline",
    "hyperparameter tuning",
    "model evaluation metrics",
    "a/b testing framework",
    "funnel conversion analysis",
    "user segmentation cohort",
    "retention rate calculation",
    "churn prediction model",
    "recommendation engine",
    "search relevance ranking",
    "spam filter classification",
    "sentiment analysis api",
    "translation service locale",
    "timezone handling dst",
    "currency conversion rate",
    "tax calculation rules",
    "shipping cost estimator",
    "inventory stock level",
    "order fulfillment workflow",
    "payment gateway integration",
    "refund processing logic",
    "subscription billing cycle",
    "invoice pdf generation",
    "receipt email template",
    "customer support ticket",
    "knowledge base article",
    "faq page content",
    "terms of service update",
    "privacy policy gdpr",
    "cookie consent banner",
    "accessibility audit wcag",
    "seo meta tags",
    "sitemap xml generation",
    "robots txt rules",
    "canonical url redirect",
    "pagination offset limit",
    "cursor based pagination",
    "full text search index",
    "faceted filter navigation",
    "sort order direction",
]


def generate_queries(count: int, seed_queries: List[str]) -> List[str]:
    """Generate the specified number of queries, cycling through seed list."""
    queries = []
    for i in range(count):
        queries.append(seed_queries[i % len(seed_queries)])
    return queries


def run_search_scan(query: str, agent_id: str = "main") -> Dict[str, Any]:
    """
    Run scan-based search and measure latency.
    This is the current (baseline) implementation.
    """
    start_time = time.perf_counter()
    
    try:
        result = temporal_search(query, agent_id=agent_id, auto_index=True)
        
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        
        return {
            "query": query,
            "latency_ms": latency_ms,
            "results_count": len(result.get("results", [])),
            "sessions_searched": result.get("sessions_searched", 0),
            "error": None,
        }
    except Exception as e:
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        
        return {
            "query": query,
            "latency_ms": latency_ms,
            "results_count": 0,
            "sessions_searched": 0,
            "error": str(e),
        }


def run_search_indexed(query: str, agent_id: str = "main") -> Dict[str, Any]:
    """
    Run index-based search and measure latency.
    This is the future (optimized) implementation - placeholder for now.
    
    TODO: Implement once inverted index is built (Phase 3)
    """
    # For now, fall back to scan-based with a note
    # In Phase 3, this will use the inverted index
    result = run_search_scan(query, agent_id)
    result["method"] = "indexed (fallback to scan)"
    return result


def calculate_percentile(values: List[float], percentile: float) -> float:
    """Calculate percentile from a list of values."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = (percentile / 100) * (len(sorted_values) - 1)
    lower = int(index)
    upper = lower + 1
    if upper >= len(sorted_values):
        return sorted_values[-1]
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def run_benchmark(
    queries: List[str],
    method: str = "scan",
    agent_id: str = "main",
    warmup: int = 5
) -> Dict[str, Any]:
    """
    Run benchmark with the specified queries and method.
    
    Args:
        queries: List of queries to run
        method: "scan" (current) or "indexed" (future)
        agent_id: Agent ID to search
        warmup: Number of warmup queries to run before timing
    
    Returns:
        Benchmark results with latency statistics
    """
    print(f"\n🏁 Starting benchmark: {method} method")
    print(f"   Queries: {len(queries)}")
    print(f"   Warmup: {warmup} queries")
    print("=" * 60)
    
    # Select search function
    if method == "indexed":
        search_fn = run_search_indexed
    else:
        search_fn = run_search_scan
    
    # Warmup runs (not counted)
    if warmup > 0:
        print(f"Running {warmup} warmup queries...")
        for i, query in enumerate(queries[:warmup], 1):
            search_fn(query, agent_id)
            if i % 5 == 0:
                print(f"  Warmup {i}/{warmup}")
    
    # Actual benchmark runs
    print(f"\nRunning {len(queries)} benchmark queries...")
    results = []
    errors = []
    
    for i, query in enumerate(queries, 1):
        result = search_fn(query, agent_id)
        results.append(result)
        
        if result["error"]:
            errors.append({"query": query, "error": result["error"]})
        
        if i % 10 == 0 or i == len(queries):
            print(f"  Progress: {i}/{len(queries)} ({i/len(queries)*100:.0f}%)")
    
    # Calculate statistics
    latencies = [r["latency_ms"] for r in results if not r["error"]]
    results_counts = [r["results_count"] for r in results if not r["error"]]
    sessions_counts = [r["sessions_searched"] for r in results if not r["error"]]
    
    if not latencies:
        return {
            "method": method,
            "queries_total": len(queries),
            "queries_successful": 0,
            "queries_failed": len(errors),
            "errors": errors,
            "latency": {"error": "All queries failed"},
        }
    
    stats = {
        "method": method,
        "queries_total": len(queries),
        "queries_successful": len(latencies),
        "queries_failed": len(errors),
        "errors": errors[:5],  # First 5 errors only
        "timestamp": datetime.now().isoformat(),
        "latency": {
            "mean_ms": statistics.mean(latencies),
            "median_ms": statistics.median(latencies),
            "p50_ms": calculate_percentile(latencies, 50),
            "p95_ms": calculate_percentile(latencies, 95),
            "p99_ms": calculate_percentile(latencies, 99),
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "std_dev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
        },
        "results": {
            "mean_count": statistics.mean(results_counts) if results_counts else 0,
            "median_count": statistics.median(results_counts) if results_counts else 0,
        },
        "sessions": {
            "mean_searched": statistics.mean(sessions_counts) if sessions_counts else 0,
            "median_searched": statistics.median(sessions_counts) if sessions_counts else 0,
        },
        "raw_latencies": latencies,  # For detailed analysis
    }
    
    return stats


def print_report(stats: Dict[str, Any]):
    """Print formatted benchmark report."""
    print("\n" + "=" * 60)
    print(f"📊 Benchmark Report: {stats['method']}")
    print("=" * 60)
    print(f"Queries: {stats['queries_successful']}/{stats['queries_total']} successful")
    
    if stats['queries_failed'] > 0:
        print(f"⚠️  Failed: {stats['queries_failed']} queries")
    
    latency = stats['latency']
    print(f"\n⏱️  Latency Statistics")
    print(f"   Mean:   {latency['mean_ms']:8.2f} ms")
    print(f"   Median: {latency['median_ms']:8.2f} ms")
    print(f"   P50:    {latency['p50_ms']:8.2f} ms")
    print(f"   P95:    {latency['p95_ms']:8.2f} ms")
    print(f"   P99:    {latency['p99_ms']:8.2f} ms")
    print(f"   Min:    {latency['min_ms']:8.2f} ms")
    print(f"   Max:    {latency['max_ms']:8.2f} ms")
    print(f"   StdDev: {latency['std_dev_ms']:8.2f} ms")
    
    print(f"\n📈 Results per Query")
    print(f"   Mean:   {stats['results']['mean_count']:.1f}")
    print(f"   Median: {stats['results']['median_count']:.1f}")
    
    print(f"\n📁 Sessions Searched")
    print(f"   Mean:   {stats['sessions']['mean_searched']:.1f}")
    print(f"   Median: {stats['sessions']['median_searched']:.1f}")
    
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark search performance"
    )
    parser.add_argument(
        "--queries", "-n",
        type=int,
        default=100,
        help="Number of queries to run (default: 100)"
    )
    parser.add_argument(
        "--method", "-m",
        choices=["scan", "indexed", "both"],
        default="scan",
        help="Search method to benchmark (default: scan)"
    )
    parser.add_argument(
        "--agent-id", "-a",
        default="main",
        help="Agent ID to search (default: main)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output JSON file for results"
    )
    parser.add_argument(
        "--test-queries", "-t",
        action="store_true",
        help="Use predefined test query set"
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=5,
        help="Number of warmup queries (default: 5)"
    )
    parser.add_argument(
        "--query-file",
        help="File with queries (one per line)"
    )
    args = parser.parse_args()
    
    # Build query list
    if args.query_file:
        with open(args.query_file) as f:
            base_queries = [line.strip() for line in f if line.strip()]
    elif args.test_queries:
        base_queries = DEFAULT_TEST_QUERIES
    else:
        # Default to test queries
        base_queries = DEFAULT_TEST_QUERIES
    
    queries = generate_queries(args.queries, base_queries)
    
    # Run benchmark(s)
    all_stats = {}
    
    if args.method in ("scan", "both"):
        stats_scan = run_benchmark(queries, method="scan", agent_id=args.agent_id, warmup=args.warmup)
        all_stats["scan"] = stats_scan
        print_report(stats_scan)
    
    if args.method in ("indexed", "both"):
        stats_indexed = run_benchmark(queries, method="indexed", agent_id=args.agent_id, warmup=args.warmup)
        all_stats["indexed"] = stats_indexed
        print_report(stats_indexed)
    
    # Output JSON if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(all_stats, f, indent=2)
        print(f"\n💾 Results saved to: {output_path}")
    
    # Print summary comparison if both methods
    if args.method == "both" and "scan" in all_stats and "indexed" in all_stats:
        scan_stats = all_stats["scan"]["latency"]
        indexed_stats = all_stats["indexed"]["latency"]
        
        speedup = scan_stats["mean_ms"] / indexed_stats["mean_ms"] if indexed_stats["mean_ms"] > 0 else 0
        
        print("\n" + "=" * 60)
        print("📊 Comparison: Scan vs Indexed")
        print("=" * 60)
        print(f"   Mean latency: {scan_stats['mean_ms']:.1f}ms → {indexed_stats['mean_ms']:.1f}ms")
        print(f"   P95 latency:  {scan_stats['p95_ms']:.1f}ms → {indexed_stats['p95_ms']:.1f}ms")
        print(f"   Speedup:      {speedup:.1f}x")
        print("=" * 60)


if __name__ == "__main__":
    main()
