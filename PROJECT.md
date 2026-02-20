# OpenClaw RLM Metrics & Option-2 Memory Tools

## Vision

Finalize the Option-2 “refs-first + lazy expand” memory tooling (`memory_search_refs`, `memory_expand`) in OpenClaw and produce reproducible measurements (accuracy, token savings, latency) that are strong enough to support a Part 3 blog post.

## Goals (MVP)

- [ ] Make `memory_search_refs` + `memory_expand` production-safe (hard budgets; blob/base64 safety; predictable output).
- [ ] Build a reproducible evaluation harness that outputs machine-readable metrics + charts.
- [ ] Establish baseline vs refs-first comparisons:
  - accuracy / pass rate on a ground-truth suite
  - token cost (approx + optionally true tokenization)
  - latency per query stage (search, refs, expand)
- [ ] Run the suite and produce a single “results bundle” (JSON + SVG charts) that can be referenced in the Part 3 post.

## Constraints

- Prefer small, safe changes; keep existing behavior intact.
- Avoid token explosions from long single lines (QR/base64 blobs): enforce `maxChars` and/or skip refs.
- Tests in the monorepo may fail due to missing optional extension deps; scope verification to what we can run reliably.
- Use `python3` for scripts.

## Out of Scope (v1)

- Full upstream merge to openclaw/openclaw (403 today).
- Perfect paper-grade RLM implementation (we’re measuring OpenClaw’s tools/hook path, not reimplementing their Python REPL loop).
