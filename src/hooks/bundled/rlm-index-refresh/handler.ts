/**
 * RLM Index Refresh Hook
 *
 * Refreshes the RLM sessions index when transcripts update.
 */

import { exec } from "node:child_process";
import * as path from "node:path";
import { promisify } from "node:util";
import type { InternalHookHandler } from "../../internal-hooks.js";
import { resolveAgentWorkspaceDir } from "../../../agents/agent-scope.js";
import { loadConfig } from "../../../config/io.js";

const execAsync = promisify(exec);

const DEBOUNCE_MS = 60_000; // 1 minute
const COOLDOWN_MS = 5 * 60_000; // 5 minutes

const pending = new Map<string, NodeJS.Timeout>();
const lastRun = new Map<string, number>();

function extractAgentId(sessionFile: string): string | null {
  const match = sessionFile.match(/agents\/([^/]+)\/sessions\/[^/]+\.jsonl$/);
  return match?.[1] ?? null;
}

async function refreshIndex(agentId: string, workspaceDir: string): Promise<void> {
  const scriptPath = path.join(
    workspaceDir,
    "skills",
    "rlm-retrieval",
    "scripts",
    "index-sessions.py",
  );
  await execAsync(`python3 "${scriptPath}" --agent-id ${agentId}`, {
    cwd: workspaceDir,
    timeout: 30_000,
    maxBuffer: 1024 * 1024,
  });
}

const refreshOnTranscriptUpdate: InternalHookHandler = async (event) => {
  if (event.type !== "session" || event.action !== "transcript:update") {
    return;
  }

  const sessionFile = event.context.sessionFile as string | undefined;
  if (!sessionFile) {
    return;
  }

  const agentId = extractAgentId(sessionFile) ?? "main";
  const now = Date.now();
  const last = lastRun.get(agentId) ?? 0;
  if (now - last < COOLDOWN_MS) {
    return;
  }

  // debounce per agent
  if (pending.has(agentId)) {
    clearTimeout(pending.get(agentId));
  }

  const timer = setTimeout(async () => {
    try {
      const cfg = loadConfig();
      const workspaceDir = resolveAgentWorkspaceDir(cfg, agentId);
      await refreshIndex(agentId, workspaceDir);
      lastRun.set(agentId, Date.now());
    } catch (err) {
      console.error("[rlm-index-refresh] Hook failed:", err);
    }
  }, DEBOUNCE_MS);

  pending.set(agentId, timer);
};

export default refreshOnTranscriptUpdate;
