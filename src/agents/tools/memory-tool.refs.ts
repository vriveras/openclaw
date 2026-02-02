import { Type } from "@sinclair/typebox";
import type { OpenClawConfig } from "../../config/config.js";
import type { AnyAgentTool } from "./common.js";
import { createInternalHookEvent, triggerInternalHook } from "../../hooks/internal-hooks.js";
import { getMemorySearchManager } from "../../memory/index.js";
import { resolveSessionAgentId } from "../agent-scope.js";
import { resolveMemorySearchConfig } from "../memory-search.js";
import { jsonResult, readNumberParam, readStringParam } from "./common.js";

const MemorySearchRefsSchema = Type.Object({
  query: Type.String(),
  maxResults: Type.Optional(Type.Number()),
  minScore: Type.Optional(Type.Number()),
  previewChars: Type.Optional(Type.Number()),
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
  if (s.length <= previewChars) return s;
  return s.slice(0, previewChars).trimEnd() + "…";
}

function toRefs(results: MemorySearchResult[], previewChars: number) {
  return results.map((r) => ({
    path: r.path,
    startLine: r.startLine,
    endLine: r.endLine,
    score: r.score,
    source: r.source,
    preview: makePreview(r.snippet ?? "", previewChars),
  }));
}

export function createMemorySearchRefsTool(options: {
  config?: OpenClawConfig;
  agentSessionKey?: string;
}): AnyAgentTool | null {
  const cfg = options.config;
  if (!cfg) return null;

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
        const results = (await manager.search(query, {
          maxResults,
          minScore,
          sessionKey: options.agentSessionKey,
        })) as unknown as MemorySearchResult[];

        const status = manager.status();
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
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return jsonResult({ refs: [], disabled: true, error: message });
      }
    },
  };
}
