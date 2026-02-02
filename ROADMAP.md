# Roadmap — OpenClaw RLM Metrics & Option-2 Memory Tools

## Phase 1: Stabilize tool contracts + safety budgets
**Goal:** Ensure `memory_search_refs` and `memory_expand` have enforceable budgets and stable outputs.
- Confirm blob/base64 filtering is applied to the right field (not just preview text).
- Ensure `memory_expand` maxChars cap is always honored per ref and surfaced in output.
- Add explicit truncation markers + flags.

## Phase 2: Evaluation harness (reproducible)
**Goal:** Produce deterministic-ish, machine-readable metrics.
- Ground-truth suite format + versioning.
- Report JSON schema (sizes, latency, expansions, truncation).
- Chart generation (SVG).

## Phase 3: Baselines + measurement
**Goal:** Compute meaningful comparisons.
- Baseline: `memory_search` token/latency.
- Refs-first: `memory_search_refs` token/latency.
- Expand: top-k expansion token/latency.
- Aggregate summary (mean/median/p95) and per-case results.

## Phase 4: Final verification + packaging for Part 3
**Goal:** A single “results bundle” + notes ready to paste into blog.
- Freeze query suite and results artifact.
- Document how to run locally.
- Optional: trajectory-style JSONL logging (RLM repo inspired).
