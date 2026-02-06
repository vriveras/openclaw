import { Type } from "@sinclair/typebox";
import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";
import type { OpenClawConfig } from "../../config/config.js";
import { resolveAgentWorkspaceDir } from "../agent-scope.js";
import { resolveSessionAgentId } from "../agent-scope.js";
import { jsonResult, readNumberParam, readStringParam, type AnyAgentTool } from "./common.js";

const execFileAsync = promisify(execFile);

const RlmSearchSchema = Type.Object({
  query: Type.String(),
  maxResults: Type.Optional(Type.Number()),
});

const RlmSearchRefsSchema = Type.Object({
  query: Type.String(),
  maxResults: Type.Optional(Type.Number()),
  previewChars: Type.Optional(Type.Number()),
});

type RlmResult = {
  date: string;
  role: "user" | "assistant";
  snippet: string;
  score?: number;
};

function parseTemporalSearchOutput(stdout: string): RlmResult[] {
  // Match headers like: 🧠 (YYYY-MM-DD) 🤖 or 👤
  const results: RlmResult[] = [];
  const lines = stdout.split("\n");

  let current: Partial<RlmResult> | null = null;

  for (const line of lines) {
    const m = line.match(/🧠 \(([\d-]+)\) (🤖|👤)/);
    if (m) {
      if (current?.snippet?.trim()) {
        results.push(current as RlmResult);
      }
      current = {
        date: m[1],
        role: m[2] === "🤖" ? "assistant" : "user",
        snippet: "",
      };
      continue;
    }

    if (current && line.trim() && !line.startsWith("──")) {
      current.snippet = (current.snippet ?? "") + line + "\n";
    }
  }

  if (current?.snippet?.trim()) {
    results.push(current as RlmResult);
  }

  return results;
}

function makePreview(snippet: string, previewChars: number): string {
  const s = snippet.replace(/\s+/g, " ").trim();
  if (s.length <= previewChars) {
    return s;
  }
  return s.slice(0, previewChars).trimEnd() + "…";
}

export function createRlmSearchTool(options: {
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
    label: "RLM Search",
    name: "rlm_search",
    description:
      "RLM-only retrieval (no semantic embeddings). Uses the rlm-retrieval skill index for exact/keyword matching. Useful for testing and for workflows that want deterministic recall without embedding calls.",
    parameters: RlmSearchSchema,
    execute: async (_toolCallId, params) => {
      const query = readStringParam(params, "query", { required: true });
      const maxResults = readNumberParam(params, "maxResults", { integer: true });

      const rlmCfg = cfg.memory?.rlm;
      if (rlmCfg?.enabled === false) {
        return jsonResult({ results: [], disabled: true, error: "rlm_search disabled by config" });
      }

      const workspaceDir = resolveAgentWorkspaceDir(cfg, agentId);
      const scriptRel = rlmCfg?.script?.trim() || "skills/rlm-retrieval/scripts/temporal_search.py";
      const scriptPath = path.isAbsolute(scriptRel)
        ? scriptRel
        : path.join(workspaceDir, scriptRel);

      const timeoutMs = typeof rlmCfg?.timeoutMs === "number" ? rlmCfg.timeoutMs : 30_000;

      try {
        const { stdout } = await execFileAsync("python3", [scriptPath, query], {
          timeout: timeoutMs,
          maxBuffer: 10 * 1024 * 1024,
        });

        const parsed = parseTemporalSearchOutput(String(stdout ?? ""));

        const defaultMax =
          typeof rlmCfg?.defaultMaxResults === "number" && Number.isFinite(rlmCfg.defaultMaxResults)
            ? rlmCfg.defaultMaxResults
            : 10;

        const limit =
          typeof maxResults === "number" && Number.isFinite(maxResults) && maxResults > 0
            ? maxResults
            : defaultMax;

        const results = parsed.slice(0, limit).map((r, idx) => ({
          path: `memory/transcripts/${r.date}.md`,
          startLine: 0,
          endLine: 0,
          score: typeof r.score === "number" ? r.score : 0.55 - idx * 0.001,
          snippet: `🔍 ${r.snippet.trim()}`,
          source: "sessions" as const,
        }));

        return jsonResult({
          results,
          provider: "rlm",
          model: "temporal_search.py",
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return jsonResult({ results: [], disabled: true, error: message });
      }
    },
  };
}

export function createRlmSearchRefsTool(options: {
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
    label: "RLM Search Refs",
    name: "rlm_search_refs",
    description:
      "RLM-only reference-first retrieval. Returns lightweight refs (path + preview) suitable for selective expansion.",
    parameters: RlmSearchRefsSchema,
    execute: async (_toolCallId, params) => {
      const query = readStringParam(params, "query", { required: true });
      const maxResults = readNumberParam(params, "maxResults", { integer: true });
      const previewChars = readNumberParam(params, "previewChars", { integer: true });

      const rlmCfg = cfg.memory?.rlm;
      if (rlmCfg?.enabled === false) {
        return jsonResult({
          query,
          refs: [],
          disabled: true,
          error: "rlm_search_refs disabled by config",
        });
      }

      const workspaceDir = resolveAgentWorkspaceDir(cfg, agentId);
      const scriptRel = rlmCfg?.script?.trim() || "skills/rlm-retrieval/scripts/temporal_search.py";
      const scriptPath = path.isAbsolute(scriptRel)
        ? scriptRel
        : path.join(workspaceDir, scriptRel);

      const timeoutMs = typeof rlmCfg?.timeoutMs === "number" ? rlmCfg.timeoutMs : 30_000;

      try {
        const { stdout } = await execFileAsync("python3", [scriptPath, query], {
          timeout: timeoutMs,
          maxBuffer: 10 * 1024 * 1024,
        });

        const parsed = parseTemporalSearchOutput(String(stdout ?? ""));

        const defaultMax =
          typeof rlmCfg?.defaultMaxResults === "number" && Number.isFinite(rlmCfg.defaultMaxResults)
            ? rlmCfg.defaultMaxResults
            : 10;

        const limit =
          typeof maxResults === "number" && Number.isFinite(maxResults) && maxResults > 0
            ? maxResults
            : defaultMax;
        const previewLimit =
          typeof previewChars === "number" && Number.isFinite(previewChars) && previewChars > 0
            ? previewChars
            : 200;

        const refs = parsed.slice(0, limit).map((r, idx) => ({
          path: `memory/transcripts/${r.date}.md`,
          startLine: 0,
          endLine: 0,
          score: typeof r.score === "number" ? r.score : 0.55 - idx * 0.001,
          source: "sessions" as const,
          preview: `🔍 ${makePreview(r.snippet, previewLimit)}`,
        }));

        return jsonResult({
          query,
          refs,
          provider: "rlm",
          model: "temporal_search.py",
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return jsonResult({ query, refs: [], disabled: true, error: message });
      }
    },
  };
}
