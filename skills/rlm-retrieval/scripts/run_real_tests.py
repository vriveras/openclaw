#!/usr/bin/env python3
"""
Run test cases against temporal_search and measure accuracy.

Metrics:
- has_results: Did search return any results?
- recall@10: Is expected session in top 10?
- relevance: Do results mention the key term?
"""

import json
import subprocess
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

SCRIPTS_DIR = Path(__file__).parent
TEST_FILE = SCRIPTS_DIR.parent / "tests" / "real_test_cases.json"

def run_search(query: str) -> dict:
    """Run temporal_search.py and parse results."""
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "temporal_search.py"), query, "--json", "--no-log"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            stdout = result.stdout
            json_start = stdout.find('{')
            if json_start >= 0:
                return json.loads(stdout[json_start:])
            return {"results": [], "error": "No JSON found"}
        return {"results": [], "error": result.stderr}
    except json.JSONDecodeError as e:
        return {"results": [], "error": f"JSON parse error: {e}"}
    except Exception as e:
        return {"results": [], "error": str(e)}

def check_relevance(results: list, source_value: str) -> bool:
    """Check if any result text contains the source value."""
    source_lower = source_value.lower()
    # For short terms, do exact word match
    for r in results:
        text = r.get("text", "").lower()
        if source_lower in text:
            return True
    return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run real test cases")
    parser.add_argument("--limit", type=int, default=1000, help="Max tests to run")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show details")
    args = parser.parse_args()
    
    with open(TEST_FILE) as f:
        data = json.load(f)
    
    cases = data["cases"][:args.limit]
    print(f"🧪 Running {len(cases)} test cases...\n", flush=True)
    
    metrics = {
        "has_results": {"passed": 0, "failed": 0},
        "recall_at_10": {"passed": 0, "failed": 0},
        "relevance": {"passed": 0, "failed": 0},
        "by_type": defaultdict(lambda: {"has_results": 0, "recall": 0, "relevance": 0, "total": 0}),
        "errors": 0,
        "no_results_queries": []
    }
    
    for i, tc in enumerate(cases):
        query = tc["query"]
        expected = tc["expected_session"]
        fact_type = tc["fact_type"]
        source_value = tc.get("source_value", query)
        
        if (i + 1) % 100 == 0:
            print(f"   ... {i+1}/{len(cases)}", flush=True)
        
        search_result = run_search(query)
        
        if search_result.get("error"):
            metrics["errors"] += 1
            continue
        
        results = search_result.get("results", [])
        all_sessions = [r.get("session") or r.get("session_id", "") for r in results]
        
        metrics["by_type"][fact_type]["total"] += 1
        
        # Metric 1: Has results?
        if results:
            metrics["has_results"]["passed"] += 1
            metrics["by_type"][fact_type]["has_results"] += 1
        else:
            metrics["has_results"]["failed"] += 1
            if len(metrics["no_results_queries"]) < 10:
                metrics["no_results_queries"].append(query[:50])
        
        # Metric 2: Recall@10 (expected session in results)
        if expected in all_sessions:
            metrics["recall_at_10"]["passed"] += 1
            metrics["by_type"][fact_type]["recall"] += 1
        else:
            metrics["recall_at_10"]["failed"] += 1
        
        # Metric 3: Relevance (results contain source value)
        if results and check_relevance(results, source_value):
            metrics["relevance"]["passed"] += 1
            metrics["by_type"][fact_type]["relevance"] += 1
        else:
            metrics["relevance"]["failed"] += 1
    
    # Report
    total = len(cases) - metrics["errors"]
    
    print(f"\n{'='*60}")
    print(f"📊 RESULTS ({total} tests)")
    print(f"{'='*60}")
    
    for metric_name in ["has_results", "recall_at_10", "relevance"]:
        m = metrics[metric_name]
        p, f = m["passed"], m["failed"]
        acc = p / (p + f) * 100 if (p + f) > 0 else 0
        bar = "█" * int(acc / 5) + "░" * (20 - int(acc / 5))
        labels = {
            "has_results": "Has Results    ",
            "recall_at_10": "Recall@10      ",
            "relevance": "Relevance      "
        }
        print(f"{labels[metric_name]} {bar} {acc:5.1f}% ({p}/{p+f})")
    
    print(f"\n⚠️  Errors: {metrics['errors']}")
    print(f"{'='*60}")
    
    print(f"\n📈 By fact type:")
    print(f"{'Type':<20} {'Results':>10} {'Recall':>10} {'Relevance':>10}")
    print("-" * 50)
    for fact_type, counts in sorted(metrics["by_type"].items()):
        t = counts["total"]
        if t == 0:
            continue
        hr = counts["has_results"] / t * 100
        rc = counts["recall"] / t * 100
        rv = counts["relevance"] / t * 100
        print(f"{fact_type:<20} {hr:>9.1f}% {rc:>9.1f}% {rv:>9.1f}%")
    
    if args.verbose and metrics["no_results_queries"]:
        print(f"\n❌ Queries with no results:")
        for q in metrics["no_results_queries"]:
            print(f"   {q}")
    
    # Save
    output_file = SCRIPTS_DIR.parent / "tests" / "real_test_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_cases": len(cases),
            "errors": metrics["errors"],
            "has_results": metrics["has_results"],
            "recall_at_10": metrics["recall_at_10"],
            "relevance": metrics["relevance"],
            "by_type": {k: dict(v) for k, v in metrics["by_type"].items()}
        }, f, indent=2)
    print(f"\n💾 Saved to {output_file}")

if __name__ == "__main__":
    main()
