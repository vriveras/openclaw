/**
 * RLM Augment Hook Handler
 *
 * Augments memory_search results with RLM keyword retrieval
 */

import { exec } from "node:child_process";
import * as path from "node:path";
import { promisify } from "node:util";
import type { OpenClawConfig } from "../../../config/config.js";
import type { MemorySearchResult } from "../../../memory/types.js";
import type { InternalHookHandler } from "../../internal-hooks.js";
import { resolveAgentWorkspaceDir } from "../../../agents/agent-scope.js";

const execAsync = promisify(exec);

type RLMResult = {
  session: string;
  date: string;
  role: "user" | "assistant";
  snippet: string;
  score?: number;
};

/**
 * Parse RLM search output
 */
function parseRLMOutput(stdout: string): RLMResult[] {
  const results: RLMResult[] = [];
  const lines = stdout.split("\n");

  let currentResult: Partial<RLMResult> | null = null;

  for (const line of lines) {
    // Match session headers: 🧠 (YYYY-MM-DD) 🤖 or 👤
    const sessionMatch = line.match(/🧠 \(([\d-]+)\) (🤖|👤)/);
    if (sessionMatch) {
      if (currentResult && currentResult.snippet) {
        results.push(currentResult as RLMResult);
      }
      currentResult = {
        date: sessionMatch[1],
        role: sessionMatch[2] === "🤖" ? "assistant" : "user",
        session: "",
        snippet: "",
      };
      continue;
    }

    // Collect snippet lines
    if (currentResult && line.trim() && !line.startsWith("──")) {
      currentResult.snippet = (currentResult.snippet || "") + line + "\n";
    }
  }

  // Add last result
  if (currentResult && currentResult.snippet) {
    results.push(currentResult as RLMResult);
  }

  return results;
}

/**
 * Merge semantic and RLM results
 */
function mergeResults(
  semanticResults: MemorySearchResult[],
  rlmResults: RLMResult[],
): MemorySearchResult[] {
  const merged = [...semanticResults];
  const semanticSnippets = new Set(semanticResults.map((r) => r.snippet.toLowerCase()));

  // Add RLM results that aren't duplicates
  for (const rlm of rlmResults) {
    const snippetLower = rlm.snippet.toLowerCase();

    // Check for substantial overlap with existing results
    let isDuplicate = false;
    const snippetsArray = Array.from(semanticSnippets);
    for (const existing of snippetsArray) {
      if (
        snippetLower.includes(existing.substring(0, 50)) ||
        existing.includes(snippetLower.substring(0, 50))
      ) {
        isDuplicate = true;
        break;
      }
    }

    if (!isDuplicate) {
      merged.push({
        path: `memory/transcripts/${rlm.date}.md`,
        startLine: 0,
        endLine: 0,
        score: rlm.score ?? 0.5,
        snippet: rlm.snippet.trim(),
        source: "sessions" as const,
      });
    }
  }

  return merged;
}

function makePreview(snippet: string, previewChars: number) {
  const s = snippet.replace(/\s+/g, " ").trim();
  if (s.length <= previewChars) {
    return s;
  }
  return s.slice(0, previewChars).trimEnd() + "…";
}

function mergeRefs(
  semanticRefs: Array<{
    path: string;
    startLine: number;
    endLine: number;
    score: number;
    preview: string;
    source?: string;
  }>,
  rlmResults: RLMResult[],
  previewChars: number,
) {
  const merged = [...semanticRefs];
  const previews = new Set(semanticRefs.map((r) => r.preview.toLowerCase()));

  for (const rlm of rlmResults) {
    const preview = makePreview(rlm.snippet, previewChars);
    const previewLower = preview.toLowerCase();

    let isDuplicate = false;
    for (const existing of previews) {
      if (
        previewLower.includes(existing.substring(0, 40)) ||
        existing.includes(previewLower.substring(0, 40))
      ) {
        isDuplicate = true;
        break;
      }
    }

    if (!isDuplicate) {
      merged.push({
        path: `memory/transcripts/${rlm.date}.md`,
        startLine: 0,
        endLine: 0,
        score: rlm.score ?? 0.5,
        preview,
        source: "sessions" as const,
      });
      previews.add(previewLower);
    }
  }

  return merged;
}

/**
 * Hook handler that augments memory_search with RLM retrieval
 */
const augmentMemorySearch: InternalHookHandler = async (event) => {
  // Handle both snippet-heavy search and reference-first search.
  if (
    event.type !== "tool" ||
    (event.action !== "memory_search:post" && event.action !== "memory_search_refs:post")
  ) {
    return;
  }

  const context = event.context;
  const query = context.query as string;
  const results = context.results as MemorySearchResult[] | undefined;
  const refs = context.refs as
    | Array<{
        path: string;
        startLine: number;
        endLine: number;
        score: number;
        preview: string;
        source?: string;
      }>
    | undefined;
  const cfg = context.cfg as OpenClawConfig | undefined;
  const agentId = context.agentId as string | undefined;

  if (!query || !cfg || !agentId) {
    return;
  }

  const isRefsMode = event.action === "memory_search_refs:post";
  const previewChars = 140;

  try {
    const workspaceDir = resolveAgentWorkspaceDir(cfg, agentId);
    const skillPath = path.join(workspaceDir, "skills", "rlm-retrieval");
    const scriptPath = path.join(skillPath, "scripts", "temporal_search.py");

    // Check if skill exists
    try {
      await import("node:fs/promises").then((fs) => fs.access(scriptPath));
    } catch {
      // Skill not installed, skip augmentation
      return;
    }

    // Run RLM search
    const { stdout } = await execAsync(`python3 "${scriptPath}" "${query.replace(/"/g, '\\"')}"`, {
      cwd: workspaceDir,
      timeout: 10000, // 10 second timeout
      maxBuffer: 1024 * 1024, // 1MB max output
    });

    // Parse RLM results
    const rlmResults = parseRLMOutput(stdout);

    if (isRefsMode) {
      const semanticRefs = refs ?? [];
      const augmentedRefs = mergeRefs(semanticRefs, rlmResults, previewChars);
      context.augmentedRefs = augmentedRefs;
    } else {
      const semanticResults = results ?? [];
      const augmentedResults = mergeResults(semanticResults, rlmResults);
      context.augmentedResults = augmentedResults;
    }
  } catch (err) {
    // Silent failure - if RLM augmentation fails, we still have semantic results
    console.error("[rlm-augment] Hook failed:", err);
  }
};

export default augmentMemorySearch;
