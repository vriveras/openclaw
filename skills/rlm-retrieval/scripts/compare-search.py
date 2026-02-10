#!/usr/bin/env python3
"""
Compare Search Methods: OLD (scan) vs NEW (indexed)

Runs identical queries through both methods and compares:
- Result sets (recall check)
- Latency (speedup factor)
- Quality metrics (false positives, ranking)

Usage:
    python scripts/compare-search.py --queries 50
    python scripts/compare-search.py --test-queries --output comparison.json
    python scripts/compare-search.py --query "specific search term"
"""

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple

# Import from sibling modules
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from temporal_search import temporal_search
from enhanced_matching import enhanced_keyword_match

# Default test queries
DEFAULT_TEST_QUERIES = [
    "rlm retrieval latency",
    "what did we do yesterday",
    "Glicko chess rating",
    "OpenClaw fork changes",
    "SEO fixes blog page",
    "context memory skill",
    "compaction survival",
    "wlxc container runtime",
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
]


def generate_queries(count: int, seed_queries: List[str]) -> List[str]:
    """Generate the specified number of queries, cycling through seed list."""
    queries = []
    for i in range(count):
        queries.append(seed_queries[i % len(seed_queries)])
    return queries


def run_old_search(query: str, agent_id: str = "main") -> Dict[str, Any]:
    """
    Run OLD (scan-based) search method.
    This is the baseline/current implementation.
    """
    start_time = time.perf_counter()
    
    try:
        result = temporal_search(query, agent_id=agent_id, auto_index=True)
        
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        
        # Extract result identifiers for comparison
        result_ids = []
        for r in result.get("results", []):
            # Create unique identifier for each result
            result_id = f"{r.get('session', '')}:{r.get('timestamp', '')}:{hash(r.get('text', '')[:100])}"
            result_ids.append(result_id)
        
        return {
            "query": query,
            "latency_ms": latency_ms,
            "results": result.get("results", []),
            "result_ids": set(result_ids),
            "result_count": len(result.get("results", [])),
            "sessions_searched": result.get("sessions_searched", 0),
            "error": None,
        }
    except Exception as e:
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        
        return {
            "query": query,
            "latency_ms": latency_ms,
            "results": [],
            "result_ids": set(),
            "result_count": 0,
            "sessions_searched": 0,
            "error": str(e),
        }


def run_new_search(query: str, agent_id: str = "main") -> Dict[str, Any]:
    """
    Run NEW (index-based) search method.
    
    TODO: Replace with actual indexed search once Phase 3 is complete.
    For now, this is a placeholder that falls back to scan.
    """
    start_time = time.perf_counter()
    
    try:
        # TODO: Implement indexed search here
        # For now, use the same scan method but mark as "new"
        # In Phase 3, this will use inverted index lookup
        
        result = temporal_search(query, agent_id=agent_id, auto_index=True)
        
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        
        # Extract result identifiers for comparison
        result_ids = []
        for r in result.get("results", []):
            result_id = f"{r.get('session', '')}:{r.get('timestamp', '')}:{hash(r.get('text', '')[:100])}"
            result_ids.append(result_id)
        
        return {
            "query": query,
            "latency_ms": latency_ms,
            "results": result.get("results", []),
            "result_ids": set(result_ids),
            "result_count": len(result.get("results", [])),
            "sessions_searched": result.get("sessions_searched", 0),
            "error": None,
            "note": "Using fallback (indexed not yet implemented)"
        }
    except Exception as e:
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        
        return {
            "query": query,
            "latency_ms": latency_ms,
            "results": [],
            "result_ids": set(),
            "result_count": 0,
            "sessions_searched": 0,
            "error": str(e),
        }


def compare_result_sets(
    old_results: Set[str],
    new_results: Set[str]
) -> Dict[str, Any]:
    """
    Compare two result sets and calculate metrics.
    
    Returns:
        - recall: % of old results found in new
        - precision: % of new results that were in old
        - f1: harmonic mean of recall and precision
        - missing: results in old but not new
        - extra: results in new but not old
    """
    if not old_results and not new_results:
        return {
            "recall": 1.0,
            "precision": 1.0,
            "f1": 1.0,
            "missing_count": 0,
            "extra_count": 0,
        }
    
    if not old_results:
        return {
            "recall": 1.0,
            "precision": 0.0,
            "f1": 0.0,
            "missing_count": 0,
            "extra_count": len(new_results),
        }
    
    if not new_results:
        return {
            "recall": 0.0,
            "precision": 1.0,
            "f1": 0.0,
            "missing_count": len(old_results),
            "extra_count": 0,
        }
    
    intersection = old_results & new_results
    
    recall = len(intersection) / len(old_results) if old_results else 1.0
    precision = len(intersection) / len(new_results) if new_results else 1.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "recall": recall,
        "precision": precision,
        "f1": f1,
        "missing_count": len(old_results - new_results),
        "extra_count": len(new_results - old_results),
        "intersection_count": len(intersection),
    }


def run_comparison(
    queries: List[str],
    agent_id: str = "main",
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Run comparison between OLD and NEW search methods.
    
    Returns detailed comparison metrics.
    """
    print(f"\n🔬 Running comparison: OLD vs NEW")
    print(f"   Queries: {len(queries)}")
    print("=" * 60)
    
    query_results = []
    old_latencies = []
    new_latencies = []
    recalls = []
    precisions = []
    f1s = []
    
    for i, query in enumerate(queries, 1):
        # Run both methods
        old_result = run_old_search(query, agent_id)
        new_result = run_new_search(query, agent_id)
        
        # Compare result sets
        comparison = compare_result_sets(
            old_result["result_ids"],
            new_result["result_ids"]
        )
        
        # Collect metrics
        if not old_result["error"] and not new_result["error"]:
            old_latencies.append(old_result["latency_ms"])
            new_latencies.append(new_result["latency_ms"])
            recalls.append(comparison["recall"])
            precisions.append(comparison["precision"])
            f1s.append(comparison["f1"])
        
        query_results.append({
            "query": query,
            "old": {
                "latency_ms": old_result["latency_ms"],
                "result_count": old_result["result_count"],
                "error": old_result["error"],
            },
            "new": {
                "latency_ms": new_result["latency_ms"],
                "result_count": new_result["result_count"],
                "error": new_result["error"],
                "note": new_result.get("note"),
            },
            "comparison": comparison,
        })
        
        if verbose:
            print(f"\nQuery {i}: '{query}'")
            print(f"  OLD: {old_result['latency_ms']:.1f}ms, {old_result['result_count']} results")
            print(f"  NEW: {new_result['latency_ms']:.1f}ms, {new_result['result_count']} results")
            print(f"  Recall: {comparison['recall']:.2%}, Precision: {comparison['precision']:.2%}")
        elif i % 10 == 0 or i == len(queries):
            print(f"  Progress: {i}/{len(queries)} ({i/len(queries)*100:.0f}%)")
    
    # Calculate aggregate statistics
    def calc_stats(values: List[float]) -> Dict[str, float]:
        if not values:
            return {"mean": 0, "median": 0, "min": 0, "max": 0}
        return {
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
        }
    
    old_latency_stats = calc_stats(old_latencies)
    new_latency_stats = calc_stats(new_latencies)
    
    speedup = (
        old_latency_stats["mean"] / new_latency_stats["mean"]
        if new_latency_stats["mean"] > 0 else 0
    )
    
    recall_stats = calc_stats(recalls)
    precision_stats = calc_stats(precisions)
    f1_stats = calc_stats(f1s)
    
    # Count errors
    old_errors = sum(1 for q in query_results if q["old"]["error"])
    new_errors = sum(1 for q in query_results if q["new"]["error"])
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "queries_total": len(queries),
        "queries_successful": len(old_latencies),
        "old_errors": old_errors,
        "new_errors": new_errors,
        "baseline": {
            "avg_ms": round(old_latency_stats["mean"], 2),
            "p50_ms": round(old_latency_stats["median"], 2),
            "p95_ms": round(sorted(old_latencies)[int(len(old_latencies)*0.95)] if old_latencies else 0, 2),
            "p99_ms": round(sorted(old_latencies)[int(len(old_latencies)*0.99)] if old_latencies else 0, 2),
        },
        "indexed": {
            "avg_ms": round(new_latency_stats["mean"], 2),
            "p50_ms": round(new_latency_stats["median"], 2),
            "p95_ms": round(sorted(new_latencies)[int(len(new_latencies)*0.95)] if new_latencies else 0, 2),
            "p99_ms": round(sorted(new_latencies)[int(len(new_latencies)*0.99)] if new_latencies else 0, 2),
        },
        "speedup": round(speedup, 2),
        "recall_delta": round(recall_stats["mean"] - 1.0, 4),  # Delta from perfect recall
        "false_positive_delta": round(1.0 - precision_stats["mean"], 4),
        "quality": {
            "recall_mean": round(recall_stats["mean"], 4),
            "recall_min": round(recall_stats["min"], 4),
            "precision_mean": round(precision_stats["mean"], 4),
            "f1_mean": round(f1_stats["mean"], 4),
        },
        "query_results": query_results,
    }
    
    return report


def print_comparison_report(report: Dict[str, Any]):
    """Print formatted comparison report."""
    print("\n" + "=" * 60)
    print("📊 Comparison Report: OLD (scan) vs NEW (indexed)")
    print("=" * 60)
    
    print(f"\n📈 Queries: {report['queries_successful']}/{report['queries_total']} successful")
    if report['old_errors'] > 0:
        print(f"⚠️  OLD method errors: {report['old_errors']}")
    if report['new_errors'] > 0:
        print(f"⚠️  NEW method errors: {report['new_errors']}")
    
    baseline = report["baseline"]
    indexed = report["indexed"]
    
    print(f"\n⏱️  Latency Comparison")
    print(f"   Metric    | Baseline (OLD) | Indexed (NEW) | Change")
    print(f"   ----------|----------------|---------------|--------")
    print(f"   Mean      | {baseline['avg_ms']:10.1f} ms | {indexed['avg_ms']:9.1f} ms | {indexed['avg_ms']/baseline['avg_ms']*100:5.1f}%")
    print(f"   P50       | {baseline['p50_ms']:10.1f} ms | {indexed['p50_ms']:9.1f} ms | {indexed['p50_ms']/baseline['p50_ms']*100:5.1f}%")
    print(f"   P95       | {baseline['p95_ms']:10.1f} ms | {indexed['p95_ms']:9.1f} ms | {indexed['p95_ms']/baseline['p95_ms']*100:5.1f}%")
    print(f"   P99       | {baseline['p99_ms']:10.1f} ms | {indexed['p99_ms']:9.1f} ms | {indexed['p99_ms']/baseline['p99_ms']*100:5.1f}%")
    
    print(f"\n🚀 Speedup Factor: {report['speedup']:.1f}x")
    
    print(f"\n🎯 Quality Metrics")
    print(f"   Recall:        {report['quality']['recall_mean']:.2%} (min: {report['quality']['recall_min']:.2%})")
    print(f"   Precision:     {report['quality']['precision_mean']:.2%}")
    print(f"   F1 Score:      {report['quality']['f1_mean']:.2%}")
    print(f"   Recall Δ:      {report['recall_delta']:+.4f}")
    print(f"   False Pos Δ:   {report['false_positive_delta']:+.4f}")
    
    # Quality assessment
    if report['quality']['recall_mean'] >= 0.99 and report['false_positive_delta'] < 0.01:
        print(f"\n✅ QUALITY CHECK PASSED: No significant regression")
    elif report['quality']['recall_mean'] >= 0.95:
        print(f"\n⚠️  QUALITY WARNING: Minor recall degradation")
    else:
        print(f"\n❌ QUALITY CHECK FAILED: Significant quality regression")
    
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Compare OLD vs NEW search methods"
    )
    parser.add_argument(
        "--queries", "-n",
        type=int,
        default=50,
        help="Number of queries to run (default: 50)"
    )
    parser.add_argument(
        "--agent-id", "-a",
        default="main",
        help="Agent ID to search (default: main)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output JSON file for detailed results"
    )
    parser.add_argument(
        "--test-queries", "-t",
        action="store_true",
        help="Use predefined test query set"
    )
    parser.add_argument(
        "--query",
        help="Run single query comparison"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output per query"
    )
    parser.add_argument(
        "--query-file",
        help="File with queries (one per line)"
    )
    args = parser.parse_args()
    
    # Single query mode
    if args.query:
        print(f"Comparing single query: '{args.query}'")
        old_result = run_old_search(args.query, args.agent_id)
        new_result = run_new_search(args.query, args.agent_id)
        
        print(f"\nOLD (scan): {old_result['latency_ms']:.1f}ms, {old_result['result_count']} results")
        if old_result["error"]:
            print(f"  Error: {old_result['error']}")
        
        print(f"\nNEW (indexed): {new_result['latency_ms']:.1f}ms, {new_result['result_count']} results")
        if new_result["error"]:
            print(f"  Error: {new_result['error']}")
        if new_result.get("note"):
            print(f"  Note: {new_result['note']}")
        
        comparison = compare_result_sets(old_result["result_ids"], new_result["result_ids"])
        print(f"\nRecall: {comparison['recall']:.2%}")
        print(f"Precision: {comparison['precision']:.2%}")
        print(f"F1: {comparison['f1']:.2%}")
        print(f"Missing: {comparison['missing_count']}, Extra: {comparison['extra_count']}")
        return
    
    # Build query list
    if args.query_file:
        with open(args.query_file) as f:
            base_queries = [line.strip() for line in f if line.strip()]
    elif args.test_queries:
        base_queries = DEFAULT_TEST_QUERIES
    else:
        base_queries = DEFAULT_TEST_QUERIES
    
    queries = generate_queries(args.queries, base_queries)
    
    # Run comparison
    report = run_comparison(queries, agent_id=args.agent_id, verbose=args.verbose)
    
    # Print report
    print_comparison_report(report)
    
    # Output JSON if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n💾 Detailed results saved to: {output_path}")
    
    # Exit code based on quality
    if report['quality']['recall_mean'] < 0.95:
        sys.exit(1)  # Failure - significant regression
    elif report['quality']['recall_mean'] < 0.99:
        sys.exit(2)  # Warning - minor regression
    else:
        sys.exit(0)  # Success


if __name__ == "__main__":
    main()
