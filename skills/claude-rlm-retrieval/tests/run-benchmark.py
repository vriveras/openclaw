#!/usr/bin/env python3
"""
Run accuracy benchmark for Claude Code context-memory skill.

Usage:
    # Generate test data and run benchmark
    python generate-test-chunks.py --output /tmp/test-claude-memory --chunks 30 --tests 500
    python run-benchmark.py --input /tmp/test-claude-memory
    
    # Or run all-in-one
    python run-benchmark.py --generate --chunks 50 --tests 1000
"""

import argparse
import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

# Add scripts dir to path
SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from search import search, MEMORY_DIR
from temporal_parser import parse_temporal_query


def run_test_case(test_case: dict, test_dir: Path) -> dict:
    """Run a single test case and return result."""
    query = test_case["query"]
    should_match = test_case.get("shouldMatch", True)
    expected_keywords = test_case.get("expectedKeywords", [])
    
    # Change to test directory so search finds .claude-memory/
    original_cwd = os.getcwd()
    os.chdir(test_dir)
    
    try:
        # Run search
        result = search(query, max_chunks=20, max_results=10)
        
        # Determine if we got a match
        got_match = result.get("chunks_with_matches", 0) > 0 or len(result.get("top_results", [])) > 0
        
        # Check keywords in results
        keywords_found = []
        for r in result.get("top_results", []):
            snippet = r.get("snippet", "").lower()
            for kw in expected_keywords:
                if kw.lower() in snippet:
                    keywords_found.append(kw)
        
        keywords_found = list(set(keywords_found))
        
        # Determine correctness
        if should_match:
            correct = got_match
        else:
            correct = not got_match
        
        return {
            "id": test_case["id"],
            "query": query,
            "category": test_case.get("category", "unknown"),
            "shouldMatch": should_match,
            "gotMatch": got_match,
            "correct": correct,
            "keywordsExpected": expected_keywords,
            "keywordsFound": keywords_found,
            "chunksSearched": result.get("searched_chunks", 0),
            "matchCount": result.get("chunks_with_matches", 0),
        }
    
    finally:
        os.chdir(original_cwd)


def run_benchmark(test_dir: Path, verbose: bool = False) -> dict:
    """Run full benchmark on test cases."""
    
    # Load test cases
    test_file = test_dir / "test-cases.json"
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return None
    
    with open(test_file) as f:
        data = json.load(f)
    
    test_cases = data["testCases"]
    print(f"Running {len(test_cases)} test cases...")
    
    results = []
    correct_count = 0
    
    for i, tc in enumerate(test_cases):
        result = run_test_case(tc, test_dir)
        results.append(result)
        
        if result["correct"]:
            correct_count += 1
        elif verbose:
            print(f"  ❌ {result['id']}: '{result['query'][:50]}' - expected {'match' if tc.get('shouldMatch') else 'no match'}, got {'match' if result['gotMatch'] else 'no match'}")
        
        # Progress
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i + 1}/{len(test_cases)}")
    
    # Calculate stats
    total = len(results)
    accuracy = 100 * correct_count / total if total > 0 else 0
    
    # By category
    by_category = {}
    for r in results:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = {"total": 0, "correct": 0}
        by_category[cat]["total"] += 1
        if r["correct"]:
            by_category[cat]["correct"] += 1
    
    # True/false positives/negatives
    tp = sum(1 for r in results if r["shouldMatch"] and r["gotMatch"])
    tn = sum(1 for r in results if not r["shouldMatch"] and not r["gotMatch"])
    fp = sum(1 for r in results if not r["shouldMatch"] and r["gotMatch"])
    fn = sum(1 for r in results if r["shouldMatch"] and not r["gotMatch"])
    
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total": total,
        "correct": correct_count,
        "accuracy": round(accuracy, 2),
        "truePositives": tp,
        "trueNegatives": tn,
        "falsePositives": fp,
        "falseNegatives": fn,
        "byCategory": {
            cat: {
                "total": stats["total"],
                "correct": stats["correct"],
                "accuracy": round(100 * stats["correct"] / stats["total"], 1) if stats["total"] > 0 else 0,
            }
            for cat, stats in by_category.items()
        },
    }
    
    return {
        "summary": summary,
        "results": results,
    }


def print_summary(summary: dict):
    """Print human-readable summary."""
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    print(f"\nOverall Accuracy: {summary['correct']}/{summary['total']} = {summary['accuracy']}%")
    print(f"\nConfusion Matrix:")
    print(f"  True Positives:  {summary['truePositives']}")
    print(f"  True Negatives:  {summary['trueNegatives']}")
    print(f"  False Positives: {summary['falsePositives']}")
    print(f"  False Negatives: {summary['falseNegatives']}")
    
    print(f"\nBy Category:")
    for cat, stats in sorted(summary["byCategory"].items()):
        print(f"  {cat}: {stats['correct']}/{stats['total']} = {stats['accuracy']}%")


def main():
    parser = argparse.ArgumentParser(description="Run Claude Code context-memory benchmark")
    parser.add_argument("--input", "-i", default="/tmp/test-claude-memory", help="Test directory")
    parser.add_argument("--output", "-o", help="Output file for results (JSON)")
    parser.add_argument("--generate", "-g", action="store_true", help="Generate test data first")
    parser.add_argument("--chunks", type=int, default=30, help="Chunks to generate (with --generate)")
    parser.add_argument("--tests", type=int, default=500, help="Test cases to generate (with --generate)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show failed test details")
    
    args = parser.parse_args()
    test_dir = Path(args.input)
    
    # Generate test data if requested
    if args.generate:
        print("Generating test data...")
        gen_script = Path(__file__).parent / "generate-test-chunks.py"
        subprocess.run([
            sys.executable, str(gen_script),
            "--output", str(test_dir),
            "--chunks", str(args.chunks),
            "--tests", str(args.tests),
        ], check=True)
        print()
    
    # Check test dir exists
    if not test_dir.exists():
        print(f"❌ Test directory not found: {test_dir}")
        print("Run with --generate to create test data first")
        return 1
    
    # Run benchmark
    benchmark = run_benchmark(test_dir, verbose=args.verbose)
    
    if benchmark:
        print_summary(benchmark["summary"])
        
        # Save results
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = test_dir / "benchmark-results.json"
        
        with open(output_path, "w") as f:
            json.dump(benchmark, f, indent=2)
        
        print(f"\n✅ Results saved to {output_path}")
        
        return 0 if benchmark["summary"]["accuracy"] >= 95 else 1
    
    return 1


if __name__ == "__main__":
    sys.exit(main())
