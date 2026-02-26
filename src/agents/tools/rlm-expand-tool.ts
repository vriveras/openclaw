import { Type } from "@sinclair/typebox";
import fs from "node:fs/promises";
import path from "node:path";
import type { OpenClawConfig } from "../../config/config.js";
import { resolveSessionTranscriptsDirForAgent } from "../../config/sessions/paths.js";
import { resolveSessionAgentId } from "../agent-scope.js";
import { jsonResult, readNumberParam, readStringParam, type AnyAgentTool } from "./common.js";

const RlmGetSchema = Type.Object({
  path: Type.String({
    description: "Session transcript path in the form sessions/<file>.jsonl",
  }),
  from: Type.Optional(Type.Number({ description: "1-indexed line number" })),
  lines: Type.Optional(Type.Number({ description: "Number of lines to read" })),
});

const RlmExpandSchema = Type.Object({
  refs: Type.Array(
    Type.Object({
      path: Type.String(),
      startLine: Type.Optional(Type.Number()),
      endLine: Type.Optional(Type.Number()),
    }),
  ),
  defaultLines: Type.Optional(Type.Number()),
  maxRefs: Type.Optional(Type.Number()),
  maxChars: Type.Optional(Type.Number()),
});

function clampInt(n: number, min: number, max: number) {
  if (!Number.isFinite(n)) {
    return min;
  }
  return Math.max(min, Math.min(max, Math.floor(n)));
}

async function readLines(absPath: string, from: number, lines: number): Promise<string> {
  const text = await fs.readFile(absPath, "utf8");
  const all = text.split(/\r?\n/);
  const start = clampInt(from, 1, all.length);
  const end = clampInt(start + lines - 1, start, all.length);
  return all.slice(start - 1, end).join("\n");
}

function resolveSessionFileAbs(params: { agentId: string; relPath: string }): string {
  // relPath expected: sessions/<file>
  const rel = params.relPath.replace(/^[./]+/, "");
  const m = rel.match(/^sessions\/(.+)$/);
  if (!m) {
    throw new Error("path must start with sessions/");
  }
  const file = m[1];
  if (!file.endsWith(".jsonl")) {
    throw new Error("session path must end with .jsonl");
  }
  // prevent traversal
  if (file.includes("..") || file.includes("/") || file.includes("\\")) {
    throw new Error("invalid session filename");
  }
  const sessionsDir = resolveSessionTranscriptsDirForAgent(params.agentId);
  return path.join(sessionsDir, file);
}

export function createRlmGetTool(options: {
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

  return {
    label: "RLM Get",
    name: "rlm_get",
    description:
      "Read lines from a session transcript (jsonl) for RLM-only workflows. Use after rlm_search_refs to expand a hit with exact context.",
    parameters: RlmGetSchema,
    execute: async (_toolCallId, params) => {
      const relPath = readStringParam(params, "path", { required: true });
      const from = readNumberParam(params, "from", { integer: true }) ?? 1;
      const lines = readNumberParam(params, "lines", { integer: true }) ?? 80;

      try {
        const absPath = resolveSessionFileAbs({ agentId, relPath });
        const text = await readLines(absPath, from, clampInt(lines, 1, 400));
        return jsonResult({ path: relPath, from, lines, text });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return jsonResult({ path: relPath, text: "", disabled: true, error: message });
      }
    },
  };
}

export function createRlmExpandTool(options: {
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

  return {
    label: "RLM Expand",
    name: "rlm_expand",
    description:
      "Expand rlm_search_refs results by reading small windows around the matched jsonl line numbers. Keeps context tight and deterministic.",
    parameters: RlmExpandSchema,
    execute: async (_toolCallId, params) => {
      const raw = params as unknown as { refs?: unknown };
      const refs = Array.isArray(raw.refs)
        ? (raw.refs as Array<{ path: string; startLine?: number; endLine?: number }>)
        : [];
      const defaultLines = readNumberParam(params, "defaultLines", { integer: true }) ?? 60;
      const maxRefs = readNumberParam(params, "maxRefs", { integer: true }) ?? 5;
      const maxChars = readNumberParam(params, "maxChars", { integer: true }) ?? 8000;

      const results: Array<{ path: string; from: number; lines: number; text: string }> = [];
      let remaining = maxChars;

      for (const ref of refs.slice(0, clampInt(maxRefs, 1, 20))) {
        if (!ref?.path) {
          continue;
        }
        const center = clampInt(ref.startLine ?? ref.endLine ?? 1, 1, 10_000_000);
        const lines = clampInt(defaultLines, 1, 400);
        const from = Math.max(1, center - Math.floor(lines / 2));

        try {
          const absPath = resolveSessionFileAbs({ agentId, relPath: ref.path });
          const text = await readLines(absPath, from, lines);
          const clipped = text.slice(0, Math.max(0, remaining));
          results.push({ path: ref.path, from, lines, text: clipped });
          remaining -= clipped.length;
          if (remaining <= 0) {
            break;
          }
        } catch {
          continue;
        }
      }

      return jsonResult({ results });
    },
  };
}
