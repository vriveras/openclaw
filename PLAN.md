<plan phase="2" name="Evaluation harness: latency + aggregation">

<task id="2.1" type="auto">
  <name>Add latency measurement to report</name>
  <files>scripts/test-memory-refs-report.ts</files>
  <action>
    Measure wall-clock time (ms) for each stage per test case:
    - baseline memory_search
    - memory_search_refs
    - memory_expand
    Store per-stage latency + total latency in the JSON report.
    Also store simple flags:
      - didExpand (bool)
      - truncatedCount (from expand.details if present)
  </action>
  <verify>
    Run: node --import tsx scripts/test-memory-refs-report.ts
    Confirm report JSON includes latency fields and prints them in console summary.
  </verify>
  <done>
    Report JSON has latencyMs.{baseline,refs,expand,total} for each case.
  </done>
</task>

<task id="2.2" type="auto">
  <name>Add aggregation stats (mean/median/p95) + per-suite summary</name>
  <files>scripts/test-memory-refs-report.ts</files>
  <action>
    Compute aggregate statistics across cases for:
    - tokens (baseline/refs/expand)
    - latency (baseline/refs/expand/total)
    - expansion counts
    Include mean, median, and p95.
  </action>
  <verify>
    Run the report and confirm summary includes these aggregates.
  </verify>
  <done>
    Report summary has aggregates for token + latency + expansions.
  </done>
</task>

<task id="2.3" type="auto">
  <name>Update plotting script to include latency chart</name>
  <files>scripts/plot-memory-refs-metrics.py</files>
  <action>
    Add a third SVG chart for latency (baseline vs refs vs expand) per query.
    If latency fields are missing, print a clear error and exit non-zero.
  </action>
  <verify>
    Run plot script on the new report JSON; confirm three SVGs are written.
  </verify>
  <done>
    plot script writes *-latency.svg in addition to tokens + expansion-counts.
  </done>
</task>

<task id="2.4" type="manual">
  <name>Define the ground-truth suite size + accuracy criteria</name>
  <files>scripts/memory-refs-ground-truth.json</files>
  <action>
    Decide whether we want a blog-grade suite (e.g., 25–100 cases) vs the current 6-case sanity suite.
    Define what 'accuracy' means:
    - substring evidence (current)
    - or strict path/line evidence
    - or human-labeled correctness.
  </action>
  <verify>Agreement in chat.</verify>
  <done>We have an agreed target suite size + metric definition.</done>
</task>

</plan>
