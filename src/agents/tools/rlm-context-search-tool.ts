import { execFile } from "node:child_process";
import path from "node:path";
import { performance } from "node:perf_hooks";
import { promisify } from "node:util";
import { Type } from "@sinclair/typebox";
import type { OpenClawConfig } from "../../config/config.js";
import { resolveAgentWorkspaceDir } from "../agent-scope.js";
import { resolveSessionAgentId } from "../agent-scope.js";
import { jsonResult, readNumberParam, readStringParam, type AnyAgentTool } from "./common.js";

const execFileAsync = promisify(execFile);

const RlmContextSearchSchema = Type.Object({
  query: Type.String({
    description: "Search query for context across all sources (sessions, memory, state)",
  }),
  limit: Type.Optional(
    Type.Number({
      description: "Max results to return (default: 5)",
    }),
  ),
});

type ContextSearchResult = {
  source: string;
  score: number;
  content: string;
  date?: string;
  path?: string;
};

function parseContextSearchJson(stdout: string): ContextSearchResult[] {
  const raw = String(stdout ?? "").trim();
  if (!raw) {
    return [];
  }
  try {
    return JSON.parse(raw) as ContextSearchResult[];
  } catch {
    return [];
  }
}

export function createRlmContextSearchTool(options: {
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
    label: "RLM Context Search",
    name: "rlm_context_search",
    description:
      "One-shot RLM search across ALL context sources (sessions, memory files, state). Returns pre-expanded content ready to read. Use this for quick context recovery without multiple tool calls.",
    parameters: RlmContextSearchSchema,
    execute: async (_toolCallId, params) => {
      const query = readStringParam(params, "query", { required: true });
      const limit = readNumberParam(params, "limit", { integer: true }) ?? 5;

      const workspaceDir = resolveAgentWorkspaceDir(cfg, agentId);
      const scriptPath = path.join(workspaceDir, "skills/rlm-retrieval/scripts/context-search.py");

      const toolT0 = performance.now();
      try {
        const { stdout } = await execFileAsync(
          "python3",
          [scriptPath, query, "--json", "--limit", String(limit), "--agent", agentId],
          {
            timeout: 30000,
            maxBuffer: 10 * 1024 * 1024,
          },
        );

        const results = parseContextSearchJson(String(stdout ?? ""));

        // Format for easy reading
        const formatted = results.map((r, i) => ({
          rank: i + 1,
          source: r.source,
          date: r.date || "unknown",
          score: r.score,
          content: r.content?.slice(0, 400) + (r.content?.length > 400 ? "..." : ""),
          path: r.path,
        }));

        const toolMs = performance.now() - toolT0;

        return jsonResult({
          query,
          results: formatted,
          total: results.length,
          meta: {
            toolMs: Math.round(toolMs),
            sourcesSearched: ["sessions", "memory", "state"],
          },
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return jsonResult({
          query,
          results: [],
          disabled: true,
          error: message,
          hint: "Is the rlm-retrieval skill installed in skills/rlm-retrieval/?",
        });
      }
    },
  };
}
