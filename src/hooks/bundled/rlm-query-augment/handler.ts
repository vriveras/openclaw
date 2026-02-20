/**
 * RLM Query Augment Hook Handler
 *
 * Automatically detects context-seeking queries and pre-fetches
 * relevant context before the agent processes the message.
 */

import { execFile } from "node:child_process";
import * as path from "node:path";
import { promisify } from "node:util";
import { resolveAgentWorkspaceDir } from "../../../agents/agent-scope.js";
import type { OpenClawConfig } from "../../../config/config.js";
import type { InternalHookHandler } from "../../internal-hooks.js";

const execFileAsync = promisify(execFile);

// Context-seeking patterns to auto-trigger search
type Pattern = {
  regex: RegExp;
  extractQuery: (match: RegExpMatchArray, content: string) => string;
};

const CONTEXT_PATTERNS: Pattern[] = [
  // "What did we do yesterday/about X?"
  {
    regex: /what\s+did\s+we\s+do\s+(yesterday|about|with|on)\s+(.+?)(?:\?|$)/i,
    extractQuery: (m) => `${m[2]} ${m[1]}`,
  },
  // "Where did we leave off?"
  {
    regex: /where\s+did\s+we\s+leave\s+off/i,
    extractQuery: () => "yesterday left off",
  },
  // "Status of X?" / "What's the status of X?"
  {
    regex: /(?:what\s+(?:is|was)\s+)?(?:the\s+)?status\s+(?:of\s+)?(.+?)(?:\?|$)/i,
    extractQuery: (m) => `${m[1]} status`,
  },
  // "What did we decide about X?"
  {
    regex: /what\s+did\s+we\s+(?:decide|agree)\s+(?:about|on)\s+(.+?)(?:\?|$)/i,
    extractQuery: (m) => `${m[1]} decision conclusion`,
  },
  // "How did we fix X?"
  {
    regex: /how\s+did\s+we\s+(?:fix|solve|resolve|handle)\s+(.+?)(?:\?|$)/i,
    extractQuery: (m) => `${m[1]} fix solution`,
  },
  // "Remember when we X?"
  {
    regex: /remember\s+(?:when\s+)?we\s+(.+?)(?:\?|$)/i,
    extractQuery: (m) => m[1],
  },
  // "About X..." (contextual follow-up)
  {
    regex: /^(?:about|regarding|as\s+for)\s+(.+?)(?:[.]|$)/i,
    extractQuery: (m) => m[1],
  },
];

type ContextSearchResult = {
  source: string;
  score: number;
  content: string;
  date?: string;
  path?: string;
};

/**
 * Check if message is context-seeking and extract search query
 */
function detectContextQuery(content: string): { shouldSearch: boolean; query: string } | null {
  for (const pattern of CONTEXT_PATTERNS) {
    const match = content.match(pattern.regex);
    if (match) {
      const query = pattern.extractQuery(match, content);
      return { shouldSearch: true, query: query.slice(0, 100) }; // Limit query length
    }
  }
  return null;
}

/**
 * Run rlm_context_search via the context-search.py script
 */
async function runContextSearch(
  query: string,
  cfg: OpenClawConfig,
  agentId: string,
  limit: number = 5,
): Promise<ContextSearchResult[]> {
  const workspaceDir = resolveAgentWorkspaceDir(cfg, agentId);
  const scriptPath = path.join(
    workspaceDir,
    "skills",
    "rlm-retrieval",
    "scripts",
    "context-search.py",
  );

  try {
    // Check if script exists
    await import("node:fs/promises").then((fs) => fs.access(scriptPath));
  } catch {
    // Skill not installed
    return [];
  }

  try {
    const { stdout } = await execFileAsync(
      "python3",
      [scriptPath, query, "--json", "--limit", String(limit), "--agent", agentId],
      {
        cwd: workspaceDir,
        timeout: 15000,
        maxBuffer: 5 * 1024 * 1024,
      },
    );

    const raw = String(stdout ?? "").trim();
    if (!raw) {
      return [];
    }

    return JSON.parse(raw) as ContextSearchResult[];
  } catch (err) {
    console.error("[rlm-query-augment] Search failed:", err);
    return [];
  }
}

/**
 * Format results for injection into context
 */
function formatResults(results: ContextSearchResult[], query: string): string {
  if (results.length === 0) {
    return "";
  }

  let formatted = `\n🔍 Auto-retrieved context for: "${query}"\n`;
  formatted += `Found ${results.length} relevant items:\n\n`;

  for (let i = 0; i < results.length; i++) {
    const r = results[i];
    const source = r.source || "unknown";
    const date = r.date || "unknown date";
    const score = typeof r.score === "number" ? r.score.toFixed(1) : "?";
    const content = (r.content || "").slice(0, 300).trim();

    formatted += `[${i + 1}] ${source} (${date}): Score ${score}\n`;
    formatted += `    "${content}${r.content && r.content.length > 300 ? "..." : ""}"\n\n`;
  }

  return formatted;
}

/**
 * Hook handler that auto-fetches context for context-seeking queries
 */
const queryAugmentHook: InternalHookHandler = async (event) => {
  if (event.type !== "message" || event.action !== "received") {
    return;
  }

  const context = event.context as {
    from: string;
    content: string;
    channelId: string;
    cfg?: OpenClawConfig;
    agentId?: string;
    // Can be used to inject context for the agent
    injectedContext?: string;
  };

  const content = context.content;
  if (!content || content.length < 3) {
    return;
  }

  // Detect if this is a context-seeking query
  const detection = detectContextQuery(content);
  if (!detection || !detection.shouldSearch) {
    return;
  }

  const { query } = detection;
  const cfg = context.cfg;
  const agentId = context.agentId;

  if (!cfg || !agentId) {
    return;
  }

  // Run the search
  const results = await runContextSearch(query, cfg, agentId, 5);

  if (results.length > 0) {
    // Format and inject context into the event (deterministic, not LLM-dependent)
    const formatted = formatResults(results, query);
    event.injectedContext = event.injectedContext ?? [];
    event.injectedContext.push({
      role: "system",
      content: formatted,
    });

    // Log for debugging
    console.log(`[rlm-query-augment] Injected ${results.length} results for: "${query}"`);
  }
};

export default queryAugmentHook;
