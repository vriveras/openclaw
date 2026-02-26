import { Type } from "@sinclair/typebox";
import { execFile } from "node:child_process";
import path from "node:path";
import { performance } from "node:perf_hooks";
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

type TemporalSearchJsonResult = {
  search_path?: "index" | "fallback" | "hybrid";
  query_time_ms?: number;
  total_time_ms?: number;
  results?: Array<{
    session?: string;
    file?: string;
    line?: number;
    role?: "user" | "assistant";
    text?: string;
    match_score?: number;
  }>;
};

type RlmResult = {
  sessionId: string;
  file: string;
  line: number;
  role: "user" | "assistant";
  snippet: string;
  score?: number;
};

function parseTemporalSearchJson(stdout: string): TemporalSearchJsonResult {
  const raw = String(stdout ?? "").trim();
  if (!raw) {
    return {};
  }
  return JSON.parse(raw) as TemporalSearchJsonResult;
}

function normalizeResults(parsedJson: TemporalSearchJsonResult): RlmResult[] {
  return (parsedJson.results ?? [])
    .filter(
      (r) =>
        typeof r.session === "string" && typeof r.file === "string" && typeof r.text === "string",
    )
    .map((r) => ({
      sessionId: r.session as string,
      file: r.file as string,
      line:
        typeof r.line === "number" && Number.isFinite(r.line) ? Math.max(1, Math.floor(r.line)) : 1,
      role: r.role === "user" || r.role === "assistant" ? r.role : "assistant",
      snippet: r.text as string,
      score: typeof r.match_score === "number" ? r.match_score : undefined,
    }));
}

function makePreview(snippet: string, previewChars: number): string {
  const s = snippet.replace(/\s+/g, " ").trim();
  if (s.length <= previewChars) {
    return s;
  }
  return s.slice(0, previewChars).trimEnd() + "…";
}

function resolveScriptPath(
  cfg: OpenClawConfig,
  agentId: string,
): {
  scriptPath: string;
  timeoutMs: number;
  defaultMaxResults: number;
  disabled: boolean;
} {
  const rlmCfg = cfg.memory?.rlm;
  if (rlmCfg?.enabled === false) {
    return { scriptPath: "", timeoutMs: 0, defaultMaxResults: 0, disabled: true };
  }

  const workspaceDir = resolveAgentWorkspaceDir(cfg, agentId);
  const scriptRel = rlmCfg?.script?.trim() || "skills/rlm-retrieval/scripts/temporal_search.py";
  const scriptPath = path.isAbsolute(scriptRel) ? scriptRel : path.join(workspaceDir, scriptRel);

  const timeoutMs = typeof rlmCfg?.timeoutMs === "number" ? rlmCfg.timeoutMs : 30_000;
  const defaultMaxResults =
    typeof rlmCfg?.defaultMaxResults === "number" && Number.isFinite(rlmCfg.defaultMaxResults)
      ? rlmCfg.defaultMaxResults
      : 10;

  return { scriptPath, timeoutMs, defaultMaxResults, disabled: false };
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

      const resolved = resolveScriptPath(cfg, agentId);
      if (resolved.disabled) {
        return jsonResult({ results: [], disabled: true, error: "rlm_search disabled by config" });
      }

      const toolT0 = performance.now();
      try {
        const execT0 = performance.now();
        const { stdout } = await execFileAsync("python3", [resolved.scriptPath, "--json", query], {
          timeout: resolved.timeoutMs,
          maxBuffer: 10 * 1024 * 1024,
        });
        const execMs = performance.now() - execT0;

        const parseT0 = performance.now();
        const parsedJson = parseTemporalSearchJson(String(stdout ?? ""));
        const parsed = normalizeResults(parsedJson);
        const parseMs = performance.now() - parseT0;

        const limit =
          typeof maxResults === "number" && Number.isFinite(maxResults) && maxResults > 0
            ? maxResults
            : resolved.defaultMaxResults;

        const results = parsed.slice(0, limit).map((r, idx) => ({
          path: `sessions/${r.file}`,
          startLine: r.line,
          endLine: r.line,
          score: typeof r.score === "number" ? r.score : 0.55 - idx * 0.001,
          snippet: `🔍 ${r.snippet.trim()}\n\nSource: sessions/${r.file}#L${r.line}`,
          source: "sessions" as const,
          sessionId: r.sessionId,
        }));

        const toolMs = performance.now() - toolT0;
        return jsonResult({
          results,
          provider: "rlm",
          model: "temporal_search.py",
          meta: {
            timings: {
              toolMs,
              execMs,
              parseMs,
            },
            searchPath: parsedJson.search_path,
            scriptQueryTimeMs: parsedJson.query_time_ms,
            scriptTotalTimeMs: parsedJson.total_time_ms,
          },
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

      const resolved = resolveScriptPath(cfg, agentId);
      if (resolved.disabled) {
        return jsonResult({
          query,
          refs: [],
          disabled: true,
          error: "rlm_search_refs disabled by config",
        });
      }

      const toolT0 = performance.now();
      try {
        const execT0 = performance.now();
        const { stdout } = await execFileAsync("python3", [resolved.scriptPath, "--json", query], {
          timeout: resolved.timeoutMs,
          maxBuffer: 10 * 1024 * 1024,
        });
        const execMs = performance.now() - execT0;

        const parseT0 = performance.now();
        const parsedJson = parseTemporalSearchJson(String(stdout ?? ""));
        const parsed = normalizeResults(parsedJson);
        const parseMs = performance.now() - parseT0;

        const limit =
          typeof maxResults === "number" && Number.isFinite(maxResults) && maxResults > 0
            ? maxResults
            : resolved.defaultMaxResults;

        const previewLimit =
          typeof previewChars === "number" && Number.isFinite(previewChars) && previewChars > 0
            ? previewChars
            : 200;

        const refs = parsed.slice(0, limit).map((r, idx) => ({
          path: `sessions/${r.file}`,
          startLine: r.line,
          endLine: r.line,
          score: typeof r.score === "number" ? r.score : 0.55 - idx * 0.001,
          source: "sessions" as const,
          preview: `🔍 ${makePreview(r.snippet, previewLimit)}`,
          sessionId: r.sessionId,
        }));

        const toolMs = performance.now() - toolT0;
        return jsonResult({
          query,
          refs,
          provider: "rlm",
          model: "temporal_search.py",
          meta: {
            timings: {
              toolMs,
              execMs,
              parseMs,
            },
            searchPath: parsedJson.search_path,
            scriptQueryTimeMs: parsedJson.query_time_ms,
            scriptTotalTimeMs: parsedJson.total_time_ms,
          },
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return jsonResult({ query, refs: [], disabled: true, error: message });
      }
    },
  };
}
