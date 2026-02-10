#!/usr/bin/env python3
"""
Live validation of context-memory skill against Claude Code session data.
Runs 50+ temporal_search queries and records results.
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

# Define test queries by category
TEST_QUERIES = {
    "project": [
        "ChessRT",
        "chess-realtime",
        "wlxc",
        "OpenClaw",
        "clawd workspace",
        "context-memory skill",
        "validation tests",
        "skills development",
        "agent projects",
        "project setup",
    ],
    "technical": [
        "Glicko-2",
        "Glicko-2 rating system",
        "WebSocket",
        "WebSocket implementation",
        "API design",
        "REST API",
        "JSON schema",
        "database queries",
        "async await",
        "error handling",
        "authentication",
        "rate limiting",
    ],
    "temporal": [
        "yesterday",
        "last week",
        "recent work",
        "today",
        "this morning",
        "this week",
        "past few days",
        "recently discussed",
        "earlier today",
        "two days ago",
    ],
    "adversarial": [
        "Stripe integration",
        "Kubernetes deployment",
        "AWS Lambda",
        "Docker Compose",
        "React components",
        "MongoDB aggregation",
        "Redis caching",
        "Terraform modules",
        "GraphQL resolvers",
        "blockchain smart contracts",
    ],
    "people": [
        "Fei Su",
        "Logan",
        "meeting notes",
        "discussed with",
        "Vicente",
        "collaboration",
        "team discussion",
        "code review",
        "pair programming",
        "feedback from",
    ],
}

def run_temporal_search(query):
    """Run temporal_search.py with the given query and return results."""
    script_path = Path(__file__).parent / "temporal_search.py"
    start_time = time.time()
    
    try:
        result = subprocess.run(
            ["python3", str(script_path), query],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        duration = time.time() - start_time
        
        # Parse output to determine if results were found
        output = result.stdout
        found = False
        num_results = 0
        
        # Check if results were found (look for "Found in" or result markers)
        if "Found in" in output or "🔍" in output or "📄" in output:
            found = True
            # Try to count results
            for line in output.split('\n'):
                if line.strip().startswith(('📄', '🔍', '-')):
                    num_results += 1
        
        return {
            "query": query,
            "found": found,
            "num_results": num_results,
            "duration_ms": round(duration * 1000, 2),
            "output_preview": output[:200] if output else "",
            "error": None
        }
        
    except subprocess.TimeoutExpired:
        return {
            "query": query,
            "found": False,
            "num_results": 0,
            "duration_ms": 30000,
            "output_preview": "",
            "error": "Timeout after 30s"
        }
    except Exception as e:
        return {
            "query": query,
            "found": False,
            "num_results": 0,
            "duration_ms": 0,
            "output_preview": "",
            "error": str(e)
        }

def main():
    print("🚀 Starting Claude Code Context-Memory Live Validation")
    print("=" * 60)
    
    results = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "total_queries": 0,
            "categories": list(TEST_QUERIES.keys())
        },
        "categories": {},
        "queries": []
    }
    
    total_queries = 0
    total_found = 0
    
    # Run queries by category
    for category, queries in TEST_QUERIES.items():
        print(f"\n📂 Testing category: {category.upper()}")
        print("-" * 60)
        
        category_results = {
            "queries": [],
            "total": len(queries),
            "found": 0,
            "avg_duration_ms": 0
        }
        
        category_durations = []
        
        for query in queries:
            print(f"  ⏳ Testing: {query[:50]}...")
            result = run_temporal_search(query)
            
            category_results["queries"].append(result)
            results["queries"].append({**result, "category": category})
            
            if result["found"]:
                category_results["found"] += 1
                total_found += 1
                print(f"    ✅ Found {result['num_results']} results in {result['duration_ms']}ms")
            else:
                print(f"    ❌ No results ({result['duration_ms']}ms)")
            
            category_durations.append(result["duration_ms"])
            total_queries += 1
            
            # Small delay to avoid overwhelming the system
            time.sleep(0.1)
        
        # Calculate category stats
        if category_durations:
            category_results["avg_duration_ms"] = round(
                sum(category_durations) / len(category_durations), 2
            )
        
        results["categories"][category] = category_results
        
        print(f"  📊 Category stats: {category_results['found']}/{category_results['total']} found")
    
    # Update metadata
    results["metadata"]["total_queries"] = total_queries
    results["metadata"]["total_found"] = total_found
    results["metadata"]["retrieval_rate"] = round(total_found / total_queries * 100, 2) if total_queries > 0 else 0
    
    # Save results
    output_dir = Path(__file__).parent.parent / "validation-results"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "claude-code-live-validation.json"
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "=" * 60)
    print("📊 VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total queries:     {total_queries}")
    print(f"Results found:     {total_found}")
    print(f"Retrieval rate:    {results['metadata']['retrieval_rate']}%")
    print(f"\nBreakdown by category:")
    for category, stats in results["categories"].items():
        print(f"  {category:15} {stats['found']:3}/{stats['total']:3} ({round(stats['found']/stats['total']*100, 1):5.1f}%) avg {stats['avg_duration_ms']:6.1f}ms")
    print(f"\n✅ Results saved to: {output_file}")

if __name__ == "__main__":
    main()
