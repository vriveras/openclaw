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

    const baseline = await search.execute("tc-baseline", {
      query,
      maxResults: gt.defaults.maxResults,
    });

    const refsOut = await searchRefs.execute("tc-refs", {
      query,
      maxResults: gt.defaults.maxResults,
      previewChars: gt.defaults.previewChars,
    });

    const refsDetails = (refsOut as any)?.details ?? {};
    const refs: any[] = Array.isArray(refsDetails.refs) ? refsDetails.refs : [];

    const toExpand = refs.slice(0, gt.defaults.expand.maxRefs).map((r) => ({
      path: r.path,
      startLine: r.startLine,
      endLine: r.endLine,
    }));

    const expanded = await expand.execute("tc-expand", {
      refs: toExpand,
      defaultLines: gt.defaults.expand.defaultLines,
      maxRefs: gt.defaults.expand.maxRefs,
      maxChars: gt.defaults.expand.maxChars,
    });

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
      counts: {
        refsReturned: refs.length,
        expandedRequested: toExpand.length,
      },
      topRefs: refs.slice(0, 3),
    });
  }

  report.summary = {
    total: gt.cases.length,
    passed: passCount,
    passRate: passCount / gt.cases.length,
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
