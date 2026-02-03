#!/usr/bin/env python3
"""
Quick Validation: 100 Test Cases
Compare three-tier search vs baseline scan performance.
"""

import json
import time
import sys
import statistics
from pathlib import Path
from datetime import datetime

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from temporal_search import temporal_search, load_sessions_index

# Configuration
TEST_CASES_PATH = Path.home() / "clawd" / "private-test-data" / "test-cases-4000.json"
OUTPUT_PATH = SCRIPTS_DIR.parent / "memory" / "validation-100-sample.json"
CATEGORIES = [
    'adversarial', 'technical', 'project', 'variation', 'decision',
    'vague', 'partial', 'identity', 'metadata', 'temporal'
]
BASELINE_ESTIMATE_MS = 500  # Estimated baseline scan time


def load_test_cases():
    """Load test cases from JSON file."""
    with open(TEST_CASES_PATH) as f:
        data = json.load(f)
    return data['testCases']


def select_tests(test_cases):
    """Select 10 tests from each category (100 total)."""
    selected = []
    for cat in CATEGORIES:
        cat_tests = [t for t in test_cases if t['category'] == cat][:10]
        if len(cat_tests) < 10:
            print(f"  ⚠️  Category '{cat}' has only {len(cat_tests)} tests (expected 10)")
        selected.extend(cat_tests)
    return selected


def run_comparison(test, agent_id='main'):
    """Run both three-tier and baseline search for a single test."""
    query = test['query']
    category = test['category']
    
    # Three-tier search
    start = time.perf_counter()
    result_three = temporal_search(query, agent_id=agent_id, use_three_tier=True)
    time_three = (time.perf_counter() - start) * 1000
    
    # Baseline (legacy) search
    start = time.perf_counter()
    result_baseline = temporal_search(query, agent_id=agent_id, use_three_tier=False)
    time_baseline = (time.perf_counter() - start) * 1000
    
    # Extract results for comparison
    three_results = result_three.get('results', [])
    baseline_results = result_baseline.get('results', [])
    
    # Check if top results match (same session IDs in top 3)
    three_sessions = [r['session'] for r in three_results[:3]]
    baseline_sessions = [r['session'] for r in baseline_results[:3]]
    
    # Calculate overlap
    if baseline_sessions:
        matches = sum(1 for s in three_sessions if s in baseline_sessions)
        match_ratio = matches / len(baseline_sessions)
    else:
        match_ratio = 1.0 if not three_sessions else 0.0
    
    return {
        'query': query,
        'category': category,
        'test_id': test.get('id', 'unknown'),
        'three_tier_ms': round(time_three, 2),
        'baseline_ms': round(time_baseline, 2),
        'speedup_factor': round(time_baseline / max(time_three, 0.1), 2),
        'three_tier_results': len(three_results),
        'baseline_results': len(baseline_results),
        'top3_match_ratio': round(match_ratio, 2),
        'three_tier_path': result_three.get('search_path', 'unknown'),
        'baseline_path': result_baseline.get('search_path', 'unknown'),
    }


def calculate_stats(times):
    """Calculate statistics for timing data."""
    if not times:
        return {}
    
    sorted_times = sorted(times)
    n = len(sorted_times)
    
    return {
        'mean': round(statistics.mean(sorted_times), 2),
        'median': round(statistics.median(sorted_times), 2),
        'p95': round(sorted_times[int(n * 0.95)], 2),
        'p99': round(sorted_times[int(n * 0.99)], 2),
        'min': round(min(sorted_times), 2),
        'max': round(max(sorted_times), 2),
    }


def main():
    print("=" * 70)
    print("🔬 THREE-TIER SEARCH VALIDATION (100 TESTS)")
    print("=" * 70)
    print()
    
    # Load test cases
    print(f"📂 Loading test cases from {TEST_CASES_PATH}")
    test_cases = load_test_cases()
    print(f"   Total test cases: {len(test_cases)}")
    
    # Select 100 tests (10 per category)
    print(f"🎯 Selecting 100 tests (10 from each of {len(CATEGORIES)} categories)")
    selected_tests = select_tests(test_cases)
    print(f"   Selected: {len(selected_tests)} tests")
    print()
    
    # Ensure index exists
    print("📊 Loading sessions index...")
    skill_root = SCRIPTS_DIR.parent
    index = load_sessions_index(skill_root, 'main', auto_create=True)
    if not index:
        print("❌ Failed to load sessions index")
        sys.exit(1)
    print(f"   Sessions indexed: {len(index.get('sessions', {}))}")
    print()
    
    # Run tests
    print("🏃 Running comparison tests...")
    results = []
    
    for i, test in enumerate(selected_tests, 1):
        print(f"  Test {i}/100: [{test['category']}] {test['query'][:50]}...", end=' ')
        
        try:
            result = run_comparison(test)
            results.append(result)
            print(f"✓ {result['three_tier_ms']:.1f}ms vs {result['baseline_ms']:.1f}ms ({result['speedup_factor']:.1f}x)")
        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({
                'query': test['query'],
                'category': test['category'],
                'test_id': test.get('id', 'unknown'),
                'error': str(e)
            })
    
    print()
    print("=" * 70)
    print("📊 RESULTS SUMMARY")
    print("=" * 70)
    
    # Calculate overall statistics
    three_tier_times = [r['three_tier_ms'] for r in results if 'error' not in r]
    baseline_times = [r['baseline_ms'] for r in results if 'error' not in r]
    speedups = [r['speedup_factor'] for r in results if 'error' not in r]
    match_ratios = [r['top3_match_ratio'] for r in results if 'error' not in r]
    
    three_tier_stats = calculate_stats(three_tier_times)
    baseline_stats = calculate_stats(baseline_times)
    
    print("\n⏱️  TIMING COMPARISON")
    print("-" * 50)
    print(f"{'Metric':<15} {'Three-Tier':>12} {'Baseline':>12} {'Speedup':>10}")
    print("-" * 50)
    
    for metric in ['mean', 'median', 'p95', 'p99', 'min', 'max']:
        tt_val = three_tier_stats.get(metric, 0)
        bl_val = baseline_stats.get(metric, 0)
        speedup = bl_val / max(tt_val, 0.1)
        print(f"{metric.capitalize():<15} {tt_val:>10.1f}ms {bl_val:>10.1f}ms {speedup:>9.1f}x")
    
    # Results by category
    print("\n📁 RESULTS BY CATEGORY")
    print("-" * 70)
    print(f"{'Category':<15} {'Count':>8} {'3-Tier Mean':>12} {'Baseline Mean':>14} {'Avg Speedup':>12}")
    print("-" * 70)
    
    category_stats = {}
    for cat in CATEGORIES:
        cat_results = [r for r in results if r.get('category') == cat and 'error' not in r]
        if cat_results:
            cat_three_times = [r['three_tier_ms'] for r in cat_results]
            cat_baseline_times = [r['baseline_ms'] for r in cat_results]
            cat_speedups = [r['speedup_factor'] for r in cat_results]
            
            cat_three_mean = statistics.mean(cat_three_times)
            cat_baseline_mean = statistics.mean(cat_baseline_times)
            cat_speedup_mean = statistics.mean(cat_speedups)
            
            category_stats[cat] = {
                'count': len(cat_results),
                'three_tier_mean_ms': round(cat_three_mean, 2),
                'baseline_mean_ms': round(cat_baseline_mean, 2),
                'avg_speedup': round(cat_speedup_mean, 2),
            }
            
            print(f"{cat:<15} {len(cat_results):>8} {cat_three_mean:>11.1f}ms {cat_baseline_mean:>13.1f}ms {cat_speedup_mean:>11.1f}x")
    
    # Match quality
    avg_match_ratio = statistics.mean(match_ratios) if match_ratios else 0
    print(f"\n🎯 RESULT MATCH QUALITY")
    print("-" * 50)
    print(f"Average top-3 match ratio: {avg_match_ratio*100:.1f}%")
    print(f"Min match ratio: {min(match_ratios)*100:.1f}%" if match_ratios else "N/A")
    print(f"Max match ratio: {max(match_ratios)*100:.1f}%" if match_ratios else "N/A")
    
    # Success criteria
    print(f"\n✅ SUCCESS CRITERIA")
    print("-" * 50)
    median_target = 75
    mean_target = 150
    recall_target = 0.95
    
    median_pass = three_tier_stats.get('median', 999) <= median_target
    mean_pass = three_tier_stats.get('mean', 999) <= mean_target
    recall_pass = avg_match_ratio >= recall_target
    
    print(f"Median ≤ {median_target}ms: {'✅ PASS' if median_pass else '❌ FAIL'} ({three_tier_stats.get('median', 0):.1f}ms)")
    print(f"Mean ≤ {mean_target}ms: {'✅ PASS' if mean_pass else '❌ FAIL'} ({three_tier_stats.get('mean', 0):.1f}ms)")
    print(f"Match ratio ≥ {recall_target*100:.0f}%: {'✅ PASS' if recall_pass else '❌ FAIL'} ({avg_match_ratio*100:.1f}%)")
    
    overall_pass = median_pass and mean_pass and recall_pass
    print(f"\n{'🎉 OVERALL: PASS' if overall_pass else '⚠️  OVERALL: NEEDS IMPROVEMENT'}")
    
    # Generate report
    report = {
        'generated_at': datetime.now().isoformat(),
        'total_tests': len(results),
        'successful_tests': len([r for r in results if 'error' not in r]),
        'failed_tests': len([r for r in results if 'error' in r]),
        'three_tier_stats': three_tier_stats,
        'baseline_stats': baseline_stats,
        'speedup': {
            'mean': round(statistics.mean(speedups), 2) if speedups else 0,
            'median': round(statistics.median(speedups), 2) if speedups else 0,
            'min': round(min(speedups), 2) if speedups else 0,
            'max': round(max(speedups), 2) if speedups else 0,
        },
        'match_quality': {
            'avg_top3_match_ratio': round(avg_match_ratio, 4),
            'min_match_ratio': round(min(match_ratios), 4) if match_ratios else 0,
            'max_match_ratio': round(max(match_ratios), 4) if match_ratios else 0,
        },
        'category_breakdown': category_stats,
        'criteria_passed': {
            'median': median_pass,
            'mean': mean_pass,
            'recall': recall_pass,
            'overall': overall_pass
        },
        'estimated_baseline_ms': BASELINE_ESTIMATE_MS,
        'estimated_speedup_vs_baseline': round(BASELINE_ESTIMATE_MS / max(three_tier_stats.get('median', 100), 1), 1),
        'test_results': results
    }
    
    # Save report
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n💾 Report saved to: {OUTPUT_PATH}")
    print("=" * 70)


if __name__ == '__main__':
    main()
