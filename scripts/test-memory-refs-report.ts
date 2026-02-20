#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * Generates a JSON report for reference-first memory retrieval.
 *
 * - Loads ground truth cases from scripts/memory-refs-ground-truth.json
 * - Runs memory_search (baseline)
 * - Runs memory_search_refs (non-recursive)
 * - Runs memory_expand (top-k)
 * - Optionally runs memory_search_refs in bounded recursive mode
 * - Optional: parameter sweep to find best recursive defaults (maximize pass rate, then minimize tokens)
 *
 * Usage:
 *   node --import tsx scripts/test-memory-refs-report.ts
 *   node --import tsx scripts/test-memory-refs-report.ts --recursive
 *   node --import tsx scripts/test-memory-refs-report.ts --sweep
 *   node --import tsx scripts/test-memory-refs-report.ts --best --best-from memory/metrics/memory-refs-sweep-checkpoint.json
 */

import fs from "node:fs/promises";
import path from "node:path";
import { performance } from "node:perf_hooks";
import { createMemoryExpandTool } from "../src/agents/tools/memory-tool.expand.js";
import { createMemorySearchTool } from "../src/agents/tools/memory-tool.js";
import { createMemorySearchRefsTool } from "../src/agents/tools/memory-tool.refs.js";
import { loadConfig } from "../src/config/config.js";

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

type RecursiveCfg = {
  enabled: boolean;
  maxHops: number;
  maxRefsPerHop: number;
  expandTopK: number;
  defaultLines: number;
  maxCharsPerRef: number;
  maxTotalExpandedChars: number;
  derivedQueryMaxTerms: number;
  earlyStop: boolean;
};

function estTokensFromChars(chars: number) {
  return Math.ceil(chars / 4);
}

function jsonSize(obj: unknown) {
  const s = JSON.stringify(obj);
  return { chars: s.length, tokens: estTokensFromChars(s.length) };
}

function flattenText(block: any): string {
  if (!block) {
    return "";
  }
  if (typeof block === "string") {
    return block;
  }
  if (Array.isArray(block)) {
    return block.map(flattenText).join("\n");
  }
  if (typeof block === "object") {
    if (Array.isArray(block.content)) {
      return block.content
        .filter((c: any) => c?.type === "text")
        .map((c: any) => String(c.text || ""))
        .join("\n");
    }
    if (typeof block.text === "string") {
      return block.text;
    }
  }
  return "";
}

function normalizeLower(s: string) {
  return (s || "").toLowerCase();
}

function stats(values: number[]) {
  const xs = values
    .filter((v) => Number.isFinite(v))
    .slice()
    .toSorted((a, b) => a - b);
  const n = xs.length;
  if (n === 0) {
    return { n: 0, mean: 0, median: 0, p95: 0 };
  }
  const mean = xs.reduce((a, b) => a + b, 0) / n;
  const median = n % 2 ? xs[(n - 1) / 2] : (xs[n / 2 - 1] + xs[n / 2]) / 2;
  const p95 = xs[Math.min(n - 1, Math.ceil(0.95 * n) - 1)];
  return { n, mean, median, p95 };
}

function parseArgs(argv: string[]) {
  const set = new Set(argv);
  const valueOf = (flag: string) => {
    const i = argv.indexOf(flag);
    if (i >= 0 && i + 1 < argv.length) {
      return argv[i + 1];
    }
    return undefined;
  };
  return {
    recursive: set.has("--recursive"),
    sweep: set.has("--sweep"),
    best: set.has("--best"),
    quiet: set.has("--quiet"),
    out: valueOf("--out"),
    resume: valueOf("--resume"),
    bestFrom: valueOf("--best-from"),
    maxConfigs: valueOf("--max-configs") ? Number(valueOf("--max-configs")) : undefined,
  };
}

function defaultRecursive(maxHops = 3): RecursiveCfg {
  return {
    enabled: true,
    maxHops,
    maxRefsPerHop: 8,
    expandTopK: 2,
    defaultLines: 20,
    maxCharsPerRef: 8000,
    maxTotalExpandedChars: 12000,
    derivedQueryMaxTerms: 12,
    earlyStop: true,
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));

  const cfg = loadConfig();
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

  const runSuite = async (label: string, recursiveCfg?: RecursiveCfg) => {
    const suite: any = {
      label,
      recursiveCfg: recursiveCfg ? { ...recursiveCfg } : null,
      cases: [],
      summary: {},
    };

    let passCount = 0;
    const recPass: number[] = [];

    for (const tc of gt.cases) {
      const query = tc.query;
      if (!args.quiet) {
        console.log(`\n[${label}] [case] ${tc.id}: ${query}`);
      }

      const t0 = performance.now();

      // baseline
      const b0 = performance.now();
      const baseline = await search.execute("tc-baseline", {
        query,
        maxResults: gt.defaults.maxResults,
      });
      const baselineMs = performance.now() - b0;

      // refs (non-rec)
      const r0 = performance.now();
      const refsOut = await searchRefs.execute("tc-refs", {
        query,
        maxResults: gt.defaults.maxResults,
        previewChars: gt.defaults.previewChars,
      });
      const refsMs = performance.now() - r0;

      const refsDetails = (refsOut as any)?.details ?? {};
      const refs: any[] = Array.isArray(refsDetails.refs) ? refsDetails.refs : [];

      // expand (non-rec)
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

      // recursive refs (optional)
      let recursiveOut: any = null;
      let recursiveMs = 0;
      if (recursiveCfg) {
        const rr0 = performance.now();
        recursiveOut = await searchRefs.execute("tc-refs-rec", {
          query,
          maxResults: gt.defaults.maxResults,
          previewChars: gt.defaults.previewChars,
          recursive: recursiveCfg,
        });
        recursiveMs = performance.now() - rr0;
      }

      const totalMs = performance.now() - t0;

      const baselineText = flattenText(baseline);
      const refsText = flattenText(refsOut);
      const expandedText = flattenText(expanded);
      const recursiveText = recursiveOut ? flattenText(recursiveOut) : "";

      const expects = tc.expect.anyContains.map(normalizeLower);
      const okRefs = expects.some((e) => refsText.toLowerCase().includes(e));
      const okExpanded = expects.some((e) => expandedText.toLowerCase().includes(e));
      const okBaseline = expects.some((e) => baselineText.toLowerCase().includes(e));
      const okRecursive = recursiveOut
        ? expects.some((e) => recursiveText.toLowerCase().includes(e))
        : false;

      const ok = okRefs || okExpanded || okBaseline || okRecursive;
      if (ok) {
        passCount += 1;
      }
      if (recursiveOut) {
        recPass.push(okRecursive ? 1 : 0);
      }

      const recDetails = recursiveOut?.details?.recursive ?? null;

      suite.cases.push({
        id: tc.id,
        query,
        expect: tc.expect,
        ok,
        okByMode: {
          baseline: okBaseline,
          refs: okRefs,
          expanded: okExpanded,
          recursiveRefs: okRecursive,
        },
        sizes: {
          baseline: jsonSize(baseline),
          refs: jsonSize(refsOut),
          expanded: jsonSize(expanded),
          recursiveRefs: recursiveOut ? jsonSize(recursiveOut) : null,
        },
        latencyMs: {
          baseline: Math.round(baselineMs),
          refs: Math.round(refsMs),
          expand: Math.round(expandMs),
          recursiveRefs: recursiveOut ? Math.round(recursiveMs) : null,
          total: Math.round(totalMs),
        },
        counts: {
          refsReturned: refs.length,
          expandedRequested: toExpand.length,
        },
        recursiveMeta: recDetails,
        topRefs: refs.slice(0, 3),
      });
    }

    // aggregates
    const tokenBaseline = suite.cases.map((c: any) => c.sizes.baseline.tokens);
    const tokenRefs = suite.cases.map((c: any) => c.sizes.refs.tokens);
    const tokenExpanded = suite.cases.map((c: any) => c.sizes.expanded.tokens);

    const latencyBaseline = suite.cases.map((c: any) => c.latencyMs.baseline);
    const latencyRefs = suite.cases.map((c: any) => c.latencyMs.refs);
    const latencyExpand = suite.cases.map((c: any) => c.latencyMs.expand);

    const refsReturned = suite.cases.map((c: any) => c.counts.refsReturned);
    const expandedRequested = suite.cases.map((c: any) => c.counts.expandedRequested);

    const tokenRecursive = suite.cases
      .map((c: any) => c.sizes.recursiveRefs?.tokens)
      .filter((v: any) => typeof v === "number");
    const latencyRecursive = suite.cases
      .map((c: any) => c.latencyMs.recursiveRefs)
      .filter((v: any) => typeof v === "number");

    suite.summary = {
      total: gt.cases.length,
      passed: passCount,
      passRate: passCount / gt.cases.length,
      recursivePassRate: recPass.length
        ? recPass.reduce((a, b) => a + b, 0) / recPass.length
        : null,
      aggregates: {
        tokens: {
          baseline: stats(tokenBaseline),
          refs: stats(tokenRefs),
          expanded: stats(tokenExpanded),
          recursiveRefs: tokenRecursive.length ? stats(tokenRecursive) : null,
        },
        latencyMs: {
          baseline: stats(latencyBaseline),
          refs: stats(latencyRefs),
          expand: stats(latencyExpand),
          recursiveRefs: latencyRecursive.length ? stats(latencyRecursive) : null,
        },
        counts: {
          refsReturned: stats(refsReturned),
          expandedRequested: stats(expandedRequested),
        },
      },
    };

    return suite;
  };

  const outPath =
    args.out ?? args.resume ?? path.join(outDir, `memory-refs-report-sweep-${Date.now()}.json`);

  const report: any = args.resume
    ? JSON.parse(await fs.readFile(args.resume, "utf8"))
    : {
        generatedAt: new Date().toISOString(),
        groundTruth: { description: gt.description, version: gt.version },
        defaults: gt.defaults,
        suites: [],
        sweep: null,
      };

  const checkpoint = async () => {
    await fs.writeFile(outPath, JSON.stringify(report, null, 2));
    if (!args.quiet) {
      console.log(`checkpoint: ${outPath}`);
    }
  };

  // Always run the default suite (non-recursive refs-first with expand)
  if (!report.suites.some((s: any) => s.label === "default")) {
    report.suites.push(await runSuite("default"));
    await checkpoint();
  }

  if (args.recursive && !args.sweep) {
    if (!report.suites.some((s: any) => s.label === "recursive")) {
      report.suites.push(await runSuite("recursive", defaultRecursive(3)));
      await checkpoint();
    }
  }

  if (args.best) {
    const bestFrom = args.bestFrom ?? path.join(outDir, "memory-refs-sweep-checkpoint.json");
    const sweepData = JSON.parse(await fs.readFile(bestFrom, "utf8"));
    const best = sweepData?.sweep?.best?.cfg;
    if (!best) {
      throw new Error(`--best requested but no sweep.best.cfg found in ${bestFrom}`);
    }
    report.suites.push(await runSuite("recursive(best)", best as RecursiveCfg));
    report.bestFrom = bestFrom;
    report.best = sweepData.sweep.best;
    await checkpoint();
  }

  if (args.sweep) {
    const maxHops = 3;
    const expandTopKs = [1, 2, 3, 4];
    const defaultLines = [10, 20, 40];
    const maxTotalExpandedChars = [6000, 12000, 24000];

    const candidates: Array<{ cfg: RecursiveCfg; summary: any }> = [];

    let configsRun = 0;
    for (const k of expandTopKs) {
      for (const lines of defaultLines) {
        for (const totalChars of maxTotalExpandedChars) {
          const label = `sweep[maxHops=${maxHops},k=${k},lines=${lines},totalChars=${totalChars}]`;
          if (report.suites.some((s: any) => s.label === label)) {
            continue;
          }

          const rcfg: RecursiveCfg = {
            ...defaultRecursive(maxHops),
            expandTopK: k,
            defaultLines: lines,
            maxTotalExpandedChars: totalChars,
          };

          const suite = await runSuite(label, rcfg);
          report.suites.push(suite);
          candidates.push({ cfg: rcfg, summary: suite.summary });
          configsRun += 1;
          await checkpoint();

          if (args.maxConfigs && configsRun >= args.maxConfigs) {
            break;
          }
        }
        if (args.maxConfigs && configsRun >= args.maxConfigs) {
          break;
        }
      }
      if (args.maxConfigs && configsRun >= args.maxConfigs) {
        break;
      }
    }

    // Select best: maximize pass rate, then minimize mean tokens for recursiveRefs, then minimize p95 latency.
    const withRec = candidates
      .filter((c) => c.summary?.aggregates?.tokens?.recursiveRefs)
      .map((c) => ({
        cfg: c.cfg,
        passRate: c.summary.passRate,
        recTokensMean: c.summary.aggregates.tokens.recursiveRefs.mean,
        recLatencyP95:
          c.summary.aggregates.latencyMs.recursiveRefs?.p95 ?? Number.POSITIVE_INFINITY,
      }));

    const bestPass = Math.max(...withRec.map((c) => c.passRate));
    const bestCandidates = withRec.filter((c) => c.passRate === bestPass);
    bestCandidates.sort((a, b) => {
      if (a.recTokensMean !== b.recTokensMean) {
        return a.recTokensMean - b.recTokensMean;
      }
      return a.recLatencyP95 - b.recLatencyP95;
    });

    report.sweep = {
      grid: { maxHops, expandTopKs, defaultLines, maxTotalExpandedChars },
      objective:
        "maximize passRate, then minimize recursiveRefs.meanTokens, then minimize recursiveRefs.p95Latency",
      best: bestCandidates[0] ?? null,
    };
  }

  await checkpoint();

  if (!args.quiet) {
    console.log(`\nWrote report: ${outPath}`);
    if (report.sweep?.best) {
      console.log(`\nBest recursive config (tokens-first):`, report.sweep.best);
    }
  }
}

main().catch((err) => {
  console.error("\n❌ test-memory-refs-report failed:", err);
  process.exitCode = 1;
});
