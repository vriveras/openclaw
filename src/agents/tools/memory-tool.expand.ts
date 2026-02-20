import { Type } from "@sinclair/typebox";
import type { OpenClawConfig } from "../../config/config.js";
import type { AnyAgentTool } from "./common.js";
import { createInternalHookEvent, triggerInternalHook } from "../../hooks/internal-hooks.js";
import { getMemorySearchManager } from "../../memory/index.js";
import { resolveSessionAgentId } from "../agent-scope.js";
import { resolveMemorySearchConfig } from "../memory-search.js";
import { jsonResult, readNumberParam } from "./common.js";

const MemoryExpandSchema = Type.Object({
  refs: Type.Array(
    Type.Object({
      path: Type.String(),
      startLine: Type.Optional(Type.Number()),
      endLine: Type.Optional(Type.Number()),
      from: Type.Optional(Type.Number()),
      lines: Type.Optional(Type.Number()),
    }),
  ),
  defaultLines: Type.Optional(Type.Number()),
  maxRefs: Type.Optional(Type.Number()),
  maxChars: Type.Optional(Type.Number()),
});

type Ref = {
  path: string;
  startLine?: number;
  endLine?: number;
  from?: number;
  lines?: number;
};

function normalizeRef(ref: Ref, defaultLines: number) {
  const from = ref.from ?? ref.startLine ?? 1;
  const lines =
    ref.lines ??
    (ref.startLine != null && ref.endLine != null
      ? Math.max(1, ref.endLine - ref.startLine + 1)
      : defaultLines);
  return { path: ref.path, from, lines };
}

export function createMemoryExpandTool(options: {
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
    label: "Memory Expand",
    name: "memory_expand",
    description:
      "Expand memory_search_refs references. Enforces a strict budget by limiting number of refs and lines. Use this to lazy-load details only when needed.",
    parameters: MemoryExpandSchema,
    execute: async (_toolCallId, params) => {
      const defaultLines = readNumberParam(params, "defaultLines", { integer: true }) ?? 60;
      const maxRefs = readNumberParam(params, "maxRefs", { integer: true }) ?? 2;
      // Hard safety cap: a single line can be enormous (e.g. base64 blobs). Cap per-ref output.
      const maxChars = readNumberParam(params, "maxChars", { integer: true }) ?? 8000;

      const refs = params?.refs as Ref[] | undefined;
      if (!Array.isArray(refs) || refs.length === 0) {
        return jsonResult({ results: [], error: "refs must be a non-empty array" });
      }

      const limitedRefs = refs.slice(0, maxRefs);

      const { manager, error } = await getMemorySearchManager({ cfg, agentId });
      if (!manager) {
        return jsonResult({ results: [], disabled: true, error });
      }

      try {
        const expanded = [] as Array<{ path: string; from: number; lines: number; text: string }>;
        for (const ref of limitedRefs) {
          const nr = normalizeRef(ref, defaultLines);
          const out = await manager.readFile({
            relPath: nr.path,
            from: nr.from,
            lines: nr.lines,
          });
          const text =
            out.text.length > maxChars ? out.text.slice(0, maxChars) + "\n…TRUNCATED…" : out.text;
          expanded.push({ path: nr.path, from: nr.from, lines: nr.lines, text });
        }

        const hookEvent = createInternalHookEvent(
          "tool",
          "memory_expand:post",
          options.agentSessionKey ?? "",
          {
            refs: limitedRefs,
            expanded,
            cfg,
            agentId,
          },
        );
        await triggerInternalHook(hookEvent);

        const augmented = hookEvent.context.augmentedExpanded as typeof expanded | undefined;

        return jsonResult({
          results: augmented ?? expanded,
          budget: { maxRefs, defaultLines, maxChars },
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return jsonResult({ results: [], disabled: true, error: message });
      }
    },
  };
}
