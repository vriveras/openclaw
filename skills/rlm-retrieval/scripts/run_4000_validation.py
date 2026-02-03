#!/usr/bin/env python3
"""
Run full 4,000 test validation - simplified version
"""

import json
import time
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from temporal_search import temporal_search, load_sessions_index

# Load test cases
TEST_PATH = Path.home() / "clawd" / "private-test-data" / "test-cases-4000.json"
print(f"Loading test cases from {TEST_PATH}")

with open(TEST_PATH, 'r') as f:
    data = json.load(f)

test_cases = data['testCases']
print(f"Loaded {len(test_cases)} test cases")

# Load sessions index
skill_root = Path(__file__).parent.parent
sessions_index = load_sessions_index(skill_root, "main", auto_create=True)
print(f"Loaded {len(sessions_index.get('sessions', {}))} sessions")

# Run all 4,000 tests
results = []
start_time = time.time()

print(f"\nRunning {len(test_cases)} tests...")
print("-" * 60)

for i, test in enumerate(test_cases):
    if (i + 1) % 500 == 0:
        elapsed = time.time() - start_time
        rate = (i + 1) / elapsed
        remaining = (len(test_cases) - i - 1) / rate
        print(f"Progress: {i+1}/{len(test_cases)} | {rate:.1f} tests/sec | ETA: {remaining/60:.1f} min")
    
    query = test['query']
    category = test.get('category', 'unknown')
    
    try:
        start = time.perf_counter()
        result = temporal_search(query, agent_id='main')
        latency_ms = (time.perf_counter() - start) * 1000
        
        results.append({
            'id': test.get('id', f'tc{i}'),
            'category': category,
            'query': query,
            'latency_ms': round(latency_ms, 2),
            'result_count': len(result.get('results', [])),
            'index_hit': result.get('index_hit', False),
            'success': True
        })
    except Exception as e:
        results.append({
            'id': test.get('id', f'tc{i}'),
            'category': category,
            'query': query,
            'error': str(e),
            'success': False
        })

# Calculate statistics
total_time = time.time() - start_time
successful = [r for r in results if r.get('success', False)]
latencies = [r['latency_ms'] for r in successful]

import statistics

report = {
    'timestamp': datetime.now().isoformat(),
    'total_tests': len(test_cases),
    'successful': len(successful),
    'failed': len(test_cases) - len(successful),
    'total_time_seconds': round(total_time, 2),
    'latency_stats': {
        'mean_ms': round(statistics.mean(latencies), 2) if latencies else 0,
        'median_ms': round(statistics.median(latencies), 2) if latencies else 0,
        'p95_ms': round(sorted(latencies)[int(len(latencies)*0.95)], 2) if latencies else 0,
        'p99_ms': round(sorted(latencies)[int(len(latencies)*0.99)], 2) if latencies else 0,
        'min_ms': round(min(latencies), 2) if latencies else 0,
        'max_ms': round(max(latencies), 2) if latencies else 0,
    },
    'by_category': {}
}

# Category breakdown
for cat in set(r['category'] for r in successful):
    cat_times = [r['latency_ms'] for r in successful if r['category'] == cat]
    report['by_category'][cat] = {
        'count': len(cat_times),
        'mean_ms': round(statistics.mean(cat_times), 2) if cat_times else 0,
        'median_ms': round(statistics.median(cat_times), 2) if cat_times else 0
    }

# Save report
report_path = skill_root / "memory" / "validation-4000-full.json"
with open(report_path, 'w') as f:
    json.dump(report, f, indent=2)

print(f"\n{'='*60}")
print(f"✅ COMPLETE: {len(successful)}/{len(test_cases)} tests")
print(f"⏱️  Total time: {total_time/60:.1f} minutes")
print(f"📊 Mean latency: {report['latency_stats']['mean_ms']:.1f}ms")
print(f"📊 Median latency: {report['latency_stats']['median_ms']:.1f}ms")
print(f"📊 P95 latency: {report['latency_stats']['p95_ms']:.1f}ms")
print(f"📁 Report saved: {report_path}")
print(f"{'='*60}")
