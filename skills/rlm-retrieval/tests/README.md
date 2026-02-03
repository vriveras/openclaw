# Context Memory Tests

Validation tests and benchmarks for the context-memory skill.

## Files

- **test-cases-example.json** - Sanitized example test cases (safe for public)
- **benchmark-results.json** - Latency benchmark results
- **Charts (*.png, *.svg)** - Visualization of accuracy and performance

## Scripts

- **run-baseline-2000.py** - Run validation against test cases
- **generate-2000-tests.py** - Generate test cases from your session history
- **benchmark_latency.py** - Measure retrieval latency
- **generate-*-chart.py** - Generate visualization charts

## Full Test Suite

The full test dataset (4000 cases from real conversations) is in a separate private repo:
- [context-memory-tests](https://github.com/vriveras/context-memory-tests) (private)

To use your own test data:

```bash
# Generate tests from your sessions
python generate-2000-tests.py --count 2000 --output my-tests.json

# Run validation
python run-baseline-2000.py --input my-tests.json
```

## Results Summary

From 4000-test validation (private dataset):

| Method | Accuracy | False Positives |
|--------|----------|-----------------|
| Semantic only | ~75% | Low |
| RLM only | ~85% | Medium |
| **Hybrid** | **99.8%** | **Very Low** |

The hybrid approach combines the precision of keyword matching with semantic understanding.
