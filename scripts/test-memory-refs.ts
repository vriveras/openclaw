#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * Local validation harness for the reference-first memory tools.
 *
 * Runs a set of queries against:
 * - memory_search (snippet-heavy)
 * - memory_search_refs (refs-first)
 *
 * Then expands top refs via memory_expand and prints rough token estimates.
 *
 * Usage:
 *   node --import tsx scripts/test-memory-refs.ts
 */

import { createMemoryExpandTool } from "../src/agents/tools/memory-tool.expand.js";
import { createMemorySearchTool } from "../src/agents/tools/memory-tool.js";
import { createMemorySearchRefsTool } from "../src/agents/tools/memory-tool.refs.js";
import { loadConfig } from "../src/config/config.js";

function estTokensFromChars(chars: number) {
  // crude but stable; good enough for before/after.
  return Math.ceil(chars / 4);
}

function jsonSize(obj: unknown) {
  const s = JSON.stringify(obj);
  return { chars: s.length, tokens: estTokensFromChars(s.length) };
}

type Ref = {
  path: string;
  startLine?: number;
  endLine?: number;
  from?: number;
  lines?: number;
  preview?: string;
};

async function main() {
  const cfg = loadConfig();
  const sessionKey = "agent:main:main";

  const search = createMemorySearchTool({ config: cfg, agentSessionKey: sessionKey });
  const searchRefs = createMemorySearchRefsTool({ config: cfg, agentSessionKey: sessionKey });
  const expand = createMemoryExpandTool({ config: cfg, agentSessionKey: sessionKey });

  if (!search || !searchRefs || !expand) {
    throw new Error("Memory tools not available (check config / build).");
  }

  const queries = [
    "WhatsApp gateway connected",
    "rlm-augment",
    "ChessRT pending features",
    "queue analysis job",
    "Glicko-2",
  ];

  console.log("\n=== Memory Refs Test Harness ===\n");

  for (const query of queries) {
    console.log(`\n--- Query: ${query} ---`);

    // 1) Snippet-heavy
    const full = await search.execute("toolcall-1", { query, maxResults: 5 });
    const fullSize = jsonSize(full);

    // 2) Refs-first
    const refsOut = await searchRefs.execute("toolcall-2", {
      query,
      maxResults: 8,
      previewChars: 140,
    });
    const refsSize = jsonSize(refsOut);

    // pull refs
    const parsed = refsOut as any;
    const refs: Ref[] = Array.isArray(parsed?.details?.refs) ? parsed.details.refs : [];

    // 3) Expand top 2
    const looksBase64 = (s: string) => {
      const t = (s || "").trim();
      // Long, no-spaces, base64-ish lines
      if (t.length >= 60 && !t.includes(" ") && /^[A-Za-z0-9+/=]+$/.test(t)) {
        return true;
      }
      return false;
    };
    const safeRefs = refs.filter((r) => !looksBase64(r.preview ?? ""));

    const toExpand = safeRefs.slice(0, 2).map((r) => ({
      path: r.path,
      startLine: r.startLine,
      endLine: r.endLine,
    }));

    const expanded = await expand.execute("toolcall-3", {
      refs: toExpand,
      defaultLines: 20,
      maxRefs: 2,
      maxChars: 4000,
    });

    const expandedSize = jsonSize(expanded);

    console.log(
      `snippet-heavy:  ~${fullSize.tokens} tok (${fullSize.chars} chars) | refs: ~${refsSize.tokens} tok (${refsSize.chars} chars) | expand(top2): ~${expandedSize.tokens} tok (${expandedSize.chars} chars)`,
    );

    console.log(`refs returned: ${refs.length}`);
    for (const [i, r] of refs.slice(0, 3).entries()) {
      console.log(
        `  [${i + 1}] ${r.path}:${r.startLine}-${r.endLine} :: ${(r.preview ?? "").slice(0, 120)}`,
      );
    }
  }

  console.log("\nDone.");
}

main().catch((err) => {
  console.error("\n❌ test-memory-refs failed:", err);
  process.exitCode = 1;
});
