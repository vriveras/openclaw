#!/usr/bin/env node
/**
 * Generates a JSON report for reference-first memory retrieval.
 *
 * - Loads ground truth cases from scripts/memory-refs-ground-truth.json
 * - Runs memory_search (baseline) + memory_search_refs + memory_expand
 * - Records sizes (chars + approx tokens) + expansion counts
 * - Performs a simple correctness check: expected substrings appear in previews/expanded
 * - Writes report JSON and prints a short summary
 *
 * Usage:
 *   node --import tsx scripts/test-memory-refs-report.ts
 */

import fs from "node:fs/promises";
import path from "node:path";
import { performance } from "node:perf_hooks";
import { loadConfig } from "../src/config/config.js";
import { createMemorySearchTool } from "../src/agents/tools/memory-tool.js";
import { createMemorySearchRefsTool } from "../src/agents/tools/memory-tool.refs.js";
import { createMemoryExpandTool } from "../src/agents/tools/memory-tool.expand.js";

type GroundTruth = {
  description: string;
  version: number;
  defaults: {
    maxResults: number;
    previewChars: number;
    expand: { maxRefs: number; defaultLines: number; maxChars: number };
  };
  cases: Array<{
    id: string;
    query: string;
    expect: { anyContains: string[]; pathsLike?: string[] };
  }>;
};

function estTokensFromChars(chars: number) {
  return Math.ceil(chars / 4);
}

function jsonSize(obj: unknown) {
  const s = JSON.stringify(obj);
  return { chars: s.length, tokens: estTokensFromChars(s.length) };
}

function flattenText(block: any): string {
  if (!block) return "";
  if (typeof block === "string") return block;
  if (Array.isArray(block)) return block.map(flattenText).join("\n");
  if (typeof block === "object") {
    // tool results are AgentToolResult-like: {content:[{type:'text',text:'...'}], details:{...}}
    if (Array.isArray(block.content)) {
      return block.content
        .filter((c: any) => c?.type === "text")
        .map((c: any) => String(c.text || ""))
        .join("\n");
    }
    if (typeof block.text === "string") return block.text;
  }
  return "";
}

function normalizeLower(s: string) {
  return (s || "").toLowerCase();
}

function stats(values: number[]) {
  const xs = values.filter((v) => Number.isFinite(v)).slice().sort((a, b) => a - b);
  const n = xs.length;
  if (n === 0) return { n: 0, mean: 0, median: 0, p95: 0 };
  const mean = xs.reduce((a, b) => a + b, 0) / n;
  const median = n % 2 ? xs[(n - 1) / 2] : (xs[n / 2 - 1] + xs[n / 2]) / 2;
  const p95 = xs[Math.min(n - 1, Math.ceil(0.95 * n) - 1)];
  return { n, mean, median, p95 };
}

async function main() {
  const cfg = await loadConfig();
  const sessionKey = "agent:main:main";

  const search = createMemorySearchTool({ config: cfg, agentSessionKey: sessionKey });
  const searchRefs = createMemorySearchRefsTool({ config: cfg, agentSessionKey: sessionKey });
  const expand = createMemoryExpandTool({ config: cfg, agentSessionKey: sessionKey });
  if (!search || !searchRefs || !expand) {
    throw new Error("Memory tools not available (check config/build).");
  }

  const gtPath = path.join("scripts", "memory-refs-ground-truth.json");
  const gt = JSON.parse(await fs.readFile(gtPath, "utf8")) as GroundTruth;

  const outDir = path.join("memory", "metrics");
  await fs.mkdir(outDir, { recursive: true });

  const report: any = {
    generatedAt: new Date().toISOString(),
    groundTruth: { description: gt.description, version: gt.version },
    defaults: gt.defaults,
    cases: [],
    summary: {},
  };

  let passCount = 0;

  for (const tc of gt.cases) {
    const query = tc.query;
    console.log(`\n[case] ${tc.id}: ${query}`);

    const t0 = performance.now();

    const b0 = performance.now();
    const baseline = await search.execute("tc-baseline", {
      query,
      maxResults: gt.defaults.maxResults,
    });
    const baselineMs = performance.now() - b0;

    const r0 = performance.now();
    const refsOut = await searchRefs.execute("tc-refs", {
      query,
      maxResults: gt.defaults.maxResults,
      previewChars: gt.defaults.previewChars,
    });
    const refsMs = performance.now() - r0;

    const refsDetails = (refsOut as any)?.details ?? {};
    const refs: any[] = Array.isArray(refsDetails.refs) ? refsDetails.refs : [];

    const toExpand = refs.slice(0, gt.defaults.expand.maxRefs).map((r) => ({
      path: r.path,
      startLine: r.startLine,
      endLine: r.endLine,
    }));

    const e0 = performance.now();
    const expanded = await expand.execute("tc-expand", {
      refs: toExpand,
      defaultLines: gt.defaults.expand.defaultLines,
      maxRefs: gt.defaults.expand.maxRefs,
      maxChars: gt.defaults.expand.maxChars,
    });
    const expandMs = performance.now() - e0;

    const totalMs = performance.now() - t0;

    const baselineText = flattenText(baseline);
    const refsText = flattenText(refsOut);
    const expandedText = flattenText(expanded);

    const expects = tc.expect.anyContains.map(normalizeLower);
    const okRefs = expects.some((e) => refsText.toLowerCase().includes(e));
    const okExpanded = expects.some((e) => expandedText.toLowerCase().includes(e));
    const okBaseline = expects.some((e) => baselineText.toLowerCase().includes(e));

    const ok = okRefs || okExpanded || okBaseline;
    if (ok) passCount += 1;

    report.cases.push({
      id: tc.id,
      query,
      expect: tc.expect,
      ok,
      sizes: {
        baseline: jsonSize(baseline),
        refs: jsonSize(refsOut),
        expanded: jsonSize(expanded),
      },
      latencyMs: {
        baseline: Math.round(baselineMs),
        refs: Math.round(refsMs),
        expand: Math.round(expandMs),
        total: Math.round(totalMs),
      },
      counts: {
        refsReturned: refs.length,
        expandedRequested: toExpand.length,
      },
      topRefs: refs.slice(0, 3),
    });
  }

  const tokenBaseline = report.cases.map((c: any) => c.sizes.baseline.tokens);
  const tokenRefs = report.cases.map((c: any) => c.sizes.refs.tokens);
  const tokenExpanded = report.cases.map((c: any) => c.sizes.expanded.tokens);

  const latencyBaseline = report.cases.map((c: any) => c.latencyMs.baseline);
  const latencyRefs = report.cases.map((c: any) => c.latencyMs.refs);
  const latencyExpand = report.cases.map((c: any) => c.latencyMs.expand);
  const latencyTotal = report.cases.map((c: any) => c.latencyMs.total);

  const refsReturned = report.cases.map((c: any) => c.counts.refsReturned);
  const expandedRequested = report.cases.map((c: any) => c.counts.expandedRequested);

  report.summary = {
    total: gt.cases.length,
    passed: passCount,
    passRate: passCount / gt.cases.length,
    aggregates: {
      tokens: {
        baseline: stats(tokenBaseline),
        refs: stats(tokenRefs),
        expanded: stats(tokenExpanded),
      },
      latencyMs: {
        baseline: stats(latencyBaseline),
        refs: stats(latencyRefs),
        expand: stats(latencyExpand),
        total: stats(latencyTotal),
      },
      counts: {
        refsReturned: stats(refsReturned),
        expandedRequested: stats(expandedRequested),
      },
    },
  };

  const outPath = path.join(outDir, `memory-refs-report-${Date.now()}.json`);
  await fs.writeFile(outPath, JSON.stringify(report, null, 2));

  console.log(`Wrote report: ${outPath}`);
  console.log(`Pass rate: ${(report.summary.passRate * 100).toFixed(1)}% (${report.summary.passed}/${report.summary.total})`);

  // Print a tiny table
  for (const c of report.cases) {
    console.log(
      `${c.ok ? "✅" : "❌"} ${c.id} | refs=${c.counts.refsReturned} | tok baseline=${c.sizes.baseline.tokens} refs=${c.sizes.refs.tokens} expand=${c.sizes.expanded.tokens}`,
    );
  }
}

main().catch((err) => {
  console.error("❌ test-memory-refs-report failed:", err);
  process.exitCode = 1;
});
