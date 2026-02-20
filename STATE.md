# State

## Position

- **Phase:** 4 (Recursive retrieval + quality uplift)
- **Status:** In progress

## Latest Results (25-case suite)

### Pass Rate

- **100%** (25/25)

### Token Cost (approx, chars/4)

| Stage                     | Mean | Median | p95  |
| ------------------------- | ---- | ------ | ---- |
| baseline (memory_search)  | 2576 | 3693   | 3851 |
| refs (memory_search_refs) | 959  | 1352   | 1400 |
| expanded (memory_expand)  | 1519 | 1786   | 2935 |

**Token savings (refs vs baseline): 62.8%**

### Latency (ms)

| Stage    | Mean | Median | p95  |
| -------- | ---- | ------ | ---- |
| baseline | 2363 | 2343   | 2512 |
| refs     | 2467 | 2325   | 3210 |
| expand   | 20   | 16     | 42   |
| total    | 4849 | 4734   | 5579 |

### Expansion Counts

- refs returned: mean 5.5, median 8
- refs expanded: mean 1.5, median 2

## Artifacts

- Ground truth suite (v2, 25 cases): `scripts/memory-refs-ground-truth.json`
- Report: `memory/metrics/memory-refs-report-1770000722024.json`
- Charts:
  - `memory/metrics/memory-refs-report-1770000722024-tokens.svg`
  - `memory/metrics/memory-refs-report-1770000722024-expansion-counts.svg`
  - `memory/metrics/memory-refs-report-1770000722024-latency.svg`

## What we have

- Option-2 tools: `memory_search_refs`, `memory_expand` (with maxChars cap)
- Harness: `scripts/test-memory-refs-report.ts` (latency + aggregates)
- Charts: `scripts/plot-memory-refs-metrics.py` (3 SVGs, stdlib-only)

## Decisions

- Accuracy metric: substring-evidence (automatic, working well)
- Suite size: 25 cases (blog-grade)
- Token savings measured at 62.8% for refs-first vs baseline
- Expansion is extremely cheap (~20ms) once refs are identified

## Next Steps (Phase 4: packaging for Part 3)

- [ ] Freeze results bundle (commit report + charts)
- [ ] Copy SVGs to gist-images for embedding in blog
- [ ] Draft Part 3 blog post outline
- [ ] Optional: trajectory-style JSONL logging (RLM repo inspired)
