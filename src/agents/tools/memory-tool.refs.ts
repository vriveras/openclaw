import { Type } from "@sinclair/typebox";
import type { OpenClawConfig } from "../../config/config.js";
import type { AnyAgentTool } from "./common.js";
import { createInternalHookEvent, triggerInternalHook } from "../../hooks/internal-hooks.js";
import { getMemorySearchManager } from "../../memory/index.js";
import { resolveSessionAgentId } from "../agent-scope.js";
import { resolveMemorySearchConfig } from "../memory-search.js";
import { jsonResult, readNumberParam, readStringParam } from "./common.js";

type RecursiveRefsConfig = {
  enabled?: boolean;
  maxHops?: number;
  maxRefsPerHop?: number;
  expandTopK?: number;
  defaultLines?: number;
  maxCharsPerRef?: number;
  maxTotalExpandedChars?: number;
  derivedQueryMaxTerms?: number;
  earlyStop?: boolean;
};

const MemorySearchRefsSchema = Type.Object({
  query: Type.String(),
  maxResults: Type.Optional(Type.Number()),
  minScore: Type.Optional(Type.Number()),
  previewChars: Type.Optional(Type.Number()),
  // Experimental: bounded recursive retrieval for refs-first.
  recursive: Type.Optional(
    Type.Object({
      enabled: Type.Optional(Type.Boolean()),
      maxHops: Type.Optional(Type.Number()),
      maxRefsPerHop: Type.Optional(Type.Number()),
      expandTopK: Type.Optional(Type.Number()),
      defaultLines: Type.Optional(Type.Number()),
      maxCharsPerRef: Type.Optional(Type.Number()),
      maxTotalExpandedChars: Type.Optional(Type.Number()),
      derivedQueryMaxTerms: Type.Optional(Type.Number()),
      earlyStop: Type.Optional(Type.Boolean()),
    }),
  ),
});

type MemorySearchResult = {
  path: string;
  startLine: number;
  endLine: number;
  score: number;
  snippet: string;
  source?: string;
};

function makePreview(snippet: string, previewChars: number) {
  const s = snippet.replace(/\s+/g, " ").trim();
  if (s.length <= previewChars) {
    return s;
  }
  return s.slice(0, previewChars).trimEnd() + "…";
}

function looksBinaryOrBase64(preview: string) {
  const t = (preview || "").trim();
  // Long, no-spaces, base64-ish lines (QR / inline media artifacts)
  // Use a relatively low threshold; these blobs are toxic for expansion.
  if (t.length >= 40 && !t.includes(" ") && /^[A-Za-z0-9+/=]+$/.test(t)) {
    return true;
  }
  // Unicode replacement char often indicates binary-ish decoding artifacts
  if (t.includes("�")) {
    return true;
  }
  return false;
}

function toRefs(results: MemorySearchResult[], previewChars: number) {
  return (
    results
      .map((r) => ({
        path: r.path,
        startLine: r.startLine,
        endLine: r.endLine,
        score: r.score,
        source: r.source,
        preview: makePreview(r.snippet ?? "", previewChars),
      }))
      // Avoid returning refs that are likely gigantic/binary when expanded.
      .filter((r) => !looksBinaryOrBase64(r.preview))
  );
}

function normalizeRecursiveCfg(
  cfg: RecursiveRefsConfig | undefined,
): Required<RecursiveRefsConfig> {
  return {
    enabled: cfg?.enabled ?? false,
    maxHops: cfg?.maxHops ?? 1,
    maxRefsPerHop: cfg?.maxRefsPerHop ?? 8,
    expandTopK: cfg?.expandTopK ?? 2,
    defaultLines: cfg?.defaultLines ?? 20,
    maxCharsPerRef: cfg?.maxCharsPerRef ?? 8000,
    maxTotalExpandedChars: cfg?.maxTotalExpandedChars ?? 12000,
    derivedQueryMaxTerms: cfg?.derivedQueryMaxTerms ?? 12,
    earlyStop: cfg?.earlyStop ?? true,
  };
}

function uniq<T>(xs: T[]) {
  return Array.from(new Set(xs));
}

function deriveQueryFromText(text: string, maxTerms: number) {
  const t = text || "";

  // URLs
  const urls = t.match(/https?:\/\/[^\s)\]}>]+/g) ?? [];
  // file-like paths
  const paths = t.match(/\b[\w./-]+\.(?:md|ts|tsx|js|jsx|json|py|yml|yaml|toml|sh)\b/g) ?? [];
  // identifiers with separators
  const ids = t.match(/\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b/g) ?? [];

  const candidates = [...urls, ...paths, ...ids]
    .map((s) => s.trim())
    .filter(Boolean)
    // keep terms that are likely informative
    .filter((s) => s.length >= 4 && s.length <= 80)
    // drop super-common noise
    .filter(
      (s) =>
        !["http", "https", "from", "lines", "default", "true", "false"].includes(s.toLowerCase()),
    );

  return uniq(candidates).slice(0, maxTerms).join(" ");
}

export function createMemorySearchRefsTool(options: {
  config?: OpenClawConfig;
  agentSessionKey?: string;
}): AnyAgentTool | null {
  const cfg = options.config;
  if (!cfg) {
    return null;
  }

  const agentId = resolveSessionAgentId({
    sessionKey: options.agentSessionKey,
    config: cfg,
  });

  if (!resolveMemorySearchConfig(cfg, agentId)) {
    return null;
  }

  return {
    label: "Memory Search Refs",
    name: "memory_search_refs",
    description:
      "Reference-first memory search. Returns compact references (path + line range + short preview). Use memory_expand or memory_get to lazy-load details.",
    parameters: MemorySearchRefsSchema,
    execute: async (_toolCallId, params) => {
      const query = readStringParam(params, "query", { required: true });
      const maxResults = readNumberParam(params, "maxResults");
      const minScore = readNumberParam(params, "minScore");
      const previewChars = readNumberParam(params, "previewChars") ?? 140;

      const { manager, error } = await getMemorySearchManager({ cfg, agentId });
      if (!manager) {
        return jsonResult({ refs: [], disabled: true, error });
      }

      try {
        const status = manager.status();
        const msCfg = resolveMemorySearchConfig(cfg, agentId);

        const cfgRecursive = msCfg?.query?.recursiveRefs;
        const paramRecursive = (params?.recursive ?? undefined) as RecursiveRefsConfig | undefined;
        const mergedRecursive = normalizeRecursiveCfg({
          ...cfgRecursive,
          ...paramRecursive,
        });

        // Fast path: non-recursive refs-first.
        if (!mergedRecursive.enabled) {
          const results = (await manager.search(query, {
            maxResults,
            minScore,
            sessionKey: options.agentSessionKey,
          })) as unknown as MemorySearchResult[];

          const refs = toRefs(results, previewChars);

          // Allow skills to augment refs (e.g., add keyword/RLM refs)
          const hookEvent = createInternalHookEvent(
            "tool",
            "memory_search_refs:post",
            options.agentSessionKey ?? "",
            {
              query,
              refs,
              provider: status.provider,
              model: status.model,
              cfg,
              agentId,
            },
          );
          await triggerInternalHook(hookEvent);

          const augmentedRefs = hookEvent.context.augmentedRefs as typeof refs | undefined;

          return jsonResult({
            query,
            refs: augmentedRefs ?? refs,
            provider: status.provider,
            model: status.model,
            fallback: status.fallback,
          });
        }

        // Recursive mode: bounded multi-hop refs-first.
        const hopMeta: Array<{
          hop: number;
          query: string;
          derivedQuery?: string;
          newRefs: number;
        }> = [];

        const keyOf = (r: { path: string; startLine?: number; endLine?: number }) =>
          `${r.path}:${r.startLine ?? 0}:${r.endLine ?? 0}`;

        const allRefs = new Map<
          string,
          {
            path: string;
            startLine: number;
            endLine: number;
            score: number;
            source?: string;
            preview: string;
            hop: number;
          }
        >();

        let totalExpandedChars = 0;
        let currentQuery = query;

        for (let hop = 0; hop < mergedRecursive.maxHops; hop++) {
          const results = (await manager.search(currentQuery, {
            maxResults: mergedRecursive.maxRefsPerHop,
            minScore,
            sessionKey: options.agentSessionKey,
          })) as unknown as MemorySearchResult[];

          const refs = toRefs(results, previewChars)
            .slice(0, mergedRecursive.maxRefsPerHop)
            .map((r) => ({ ...r, hop }));

          const hookEvent = createInternalHookEvent(
            "tool",
            "memory_search_refs:post",
            options.agentSessionKey ?? "",
            {
              query: currentQuery,
              refs,
              provider: status.provider,
              model: status.model,
              cfg,
              agentId,
            },
          );
          await triggerInternalHook(hookEvent);

          const augmented = (hookEvent.context.augmentedRefs as typeof refs | undefined) ?? refs;

          let newCount = 0;
          for (const r of augmented) {
            const k = keyOf(r);
            if (!allRefs.has(k)) {
              allRefs.set(k, { ...(r as object), hop } as typeof r & { hop: number });
              newCount += 1;
            }
          }

          // Stop conditions
          if (mergedRecursive.earlyStop && newCount === 0) {
            hopMeta.push({ hop, query: currentQuery, newRefs: newCount });
            break;
          }
          if (hop >= mergedRecursive.maxHops - 1) {
            hopMeta.push({ hop, query: currentQuery, newRefs: newCount });
            break;
          }

          // Expand topK refs from this hop to derive a follow-up query.
          const top = augmented
            .slice()
            .toSorted((a, b) => (b.score ?? 0) - (a.score ?? 0))
            .slice(0, mergedRecursive.expandTopK);

          const expandedTexts: string[] = [];
          for (const r of top) {
            if (totalExpandedChars >= mergedRecursive.maxTotalExpandedChars) {
              break;
            }
            const from = r.startLine ?? 1;
            const lines =
              r.startLine != null && r.endLine != null
                ? Math.max(1, r.endLine - r.startLine + 1)
                : mergedRecursive.defaultLines;

            const out = await manager.readFile({ relPath: r.path, from, lines });
            let text = out.text;
            if (text.length > mergedRecursive.maxCharsPerRef) {
              text = text.slice(0, mergedRecursive.maxCharsPerRef) + "\n…TRUNCATED…";
            }

            const remaining = mergedRecursive.maxTotalExpandedChars - totalExpandedChars;
            if (text.length > remaining) {
              text = text.slice(0, remaining) + "\n…TRUNCATED…";
            }

            totalExpandedChars += text.length;
            expandedTexts.push(text);
          }

          const expandedJoined = expandedTexts.join("\n");
          const derived = deriveQueryFromText(expandedJoined, mergedRecursive.derivedQueryMaxTerms);

          hopMeta.push({
            hop,
            query: currentQuery,
            derivedQuery: derived || undefined,
            newRefs: newCount,
          });

          if (!derived) {
            break;
          }

          currentQuery = `${query} ${derived}`;
        }

        const finalRefs = Array.from(allRefs.values()).toSorted(
          (a, b) => (b.score ?? 0) - (a.score ?? 0),
        );

        return jsonResult({
          query,
          refs: finalRefs,
          provider: status.provider,
          model: status.model,
          fallback: status.fallback,
          recursive: {
            enabled: true,
            budget: {
              maxHops: mergedRecursive.maxHops,
              maxRefsPerHop: mergedRecursive.maxRefsPerHop,
              expandTopK: mergedRecursive.expandTopK,
              defaultLines: mergedRecursive.defaultLines,
              maxCharsPerRef: mergedRecursive.maxCharsPerRef,
              maxTotalExpandedChars: mergedRecursive.maxTotalExpandedChars,
              derivedQueryMaxTerms: mergedRecursive.derivedQueryMaxTerms,
              earlyStop: mergedRecursive.earlyStop,
            },
            hops: hopMeta,
            totalExpandedChars,
          },
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return jsonResult({ refs: [], disabled: true, error: message });
      }
    },
  };
}
