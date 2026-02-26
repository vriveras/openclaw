<plan phase="4" name="Recursive retrieval (bounded) + harness before/after">

<task id="4.1" type="auto">
  <name>Implement bounded recursive retrieval loop for refs-first</name>
  <files>
    src/hooks/bundled/rlm-augment/handler.ts,
    src/agents/tools/memory-tool.refs.ts,
    src/agents/tools/memory-tool.expand.ts
  </files>
  <action>
    Add a bounded multi-hop retrieval loop that can be enabled for refs-first flows.

    Proposed behavior (safe-by-default):
    - Start with the user query (hop 0) and run memory_search_refs (already exists).
    - Expand topK refs (default 2) with a strict budget (maxRefs, defaultLines, maxChars).
    - Derive follow-up query terms from expanded text (simple heuristic:
      - extract capitalized identifiers, file paths, URLs, issue/PR numbers, or quoted phrases
      - optionally include the original query)
    - Run memory_search_refs again for hop 1 with the derived query.
    - Merge refs across hops with de-dupe by (path,startLine,endLine) and preview overlap.

    Hard budgets:
    - maxHops (default 2)
    - maxRefsPerHop (default 8)
    - expandTopK (default 2)
    - maxTotalExpandedChars (global cap across hops)

    Surface metadata:
    - include hop index per ref (hop: 0|1|2)
    - include derivedQuery per hop in tool details for debugging

    Ensure this is opt-in (config flag or env) so existing behavior is unchanged.

  </action>
  <verify>
    Add/adjust tests or local script run to show that enabling recursion changes refs output and remains within budgets.
  </verify>
  <done>
    Recursive mode exists, bounded, and produces merged refs with hop metadata.
  </done>
</task>

<task id="4.2" type="auto">
  <name>Extend evaluation harness to compare baseline vs refs vs refs+recursive</name>
  <files>scripts/test-memory-refs-report.ts, scripts/memory-refs-ground-truth.json</files>
  <action>
    Update the harness so it can run the full Part 1/ground-truth suite in two modes:
    - current refs-first (non-recursive)
    - recursive refs-first (enabled)

    The report should include separate sections/fields for:
    - accuracy/pass rate per mode
    - tokens per mode (baseline/refs/expand + recursive totals)
    - latency per stage per mode

    Output: a single report JSON that clearly shows before/after.

  </action>
  <verify>
    Run: node --import tsx scripts/test-memory-refs-report.ts
    Confirm the output JSON includes both modes and prints a side-by-side summary.
  </verify>
  <done>
    Report JSON captures before/after, ready for blog charts.
  </done>
</task>

<task id="4.3" type="auto">
  <name>Update plotting to include recursive mode</name>
  <files>scripts/plot-memory-refs-metrics.py</files>
  <action>
    Extend charts to show baseline vs refs vs refs+recursive (and expand, if separate).
    Ensure charts remain readable (grouped bars or separate panels).
  </action>
  <verify>
    Run plotting script against the new report; confirm updated SVGs are produced.
  </verify>
  <done>
    SVGs include the recursive line/bars and are blog-embeddable.
  </done>
</task>

<task id="4.4" type="manual">
  <name>Confirm recursion tuning defaults for the blog</name>
  <files>PROJECT.md, ROADMAP.md, PLAN.md</files>
  <action>
    Confirm the defaults we will ship and claim in the Part 3 writeup:
    - maxHops (suggest 2)
    - expandTopK (suggest 2–3)
    - defaultLines (suggest 20)
    - maxTotalExpandedChars (suggest 8k–16k)

    Also confirm how we define “quality improvement”:
    - higher pass rate on ground-truth
    - or fewer manual follow-ups
    - or better ref ranking (correct ref appears in top N)

  </action>
  <verify>Agreement in chat.</verify>
  <done>Defaults + metric are locked for implementation and reporting.</done>
</task>

</plan>
