/**
 * RLM Index Refresh Hook Handler (TypeScript Interface)
 * 
 * This is the TypeScript entry point for OpenClaw's hook system.
 * It delegates to the Python implementation for actual processing.
 * 
 * Event: session:transcript:update
 * Action: Trigger incremental index update with debounce
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import * as path from 'path';

const execAsync = promisify(exec);

// Hook configuration
const HOOK_CONFIG = {
  name: 'rlm-index-refresh',
  version: '1.0.0',
  events: ['session:transcript:update'],
  debounceMs: 5000,      // 5 second debounce
  cooldownMs: 30000,     // 30 second cooldown per session
};

// Paths
const PYTHON_HANDLER = path.join(__dirname, 'handler.py');

interface TranscriptUpdateEvent {
  type: 'session:transcript:update';
  sessionId: string;
  filePath: string;
  timestamp?: string;
  messageCount?: number;
}

interface HookResult {
  success: boolean;
  status: string;
  sessionId?: string;
  message?: string;
  error?: string;
  latencyMs?: number;
}

/**
 * Main hook handler entry point
 * Called by OpenClaw when session:transcript:update events fire
 */
export async function handleEvent(event: TranscriptUpdateEvent): Promise<HookResult> {
  const startTime = Date.now();
  
  try {
    // Validate event
    if (!event.sessionId || !event.filePath) {
      return {
        success: false,
        status: 'error',
        error: 'Missing sessionId or filePath in event',
      };
    }

    // Call Python handler
    const payload = JSON.stringify({
      session_id: event.sessionId,
      file_path: event.filePath,
    });

    const command = `python3 "${PYTHON_HANDLER}" --event session:transcript:update --payload '${payload}' --json`;
    
    const { stdout, stderr } = await execAsync(command, {
      timeout: 60000,  // 60 second timeout
      maxBuffer: 1024 * 1024,  // 1MB buffer
    });

    if (stderr) {
      console.error(`[rlm-index-refresh] stderr: ${stderr}`);
    }

    // Parse result
    const result = JSON.parse(stdout);
    const latencyMs = Date.now() - startTime;

    return {
      success: result.success,
      status: result.status || 'unknown',
      sessionId: event.sessionId,
      message: result.message || result.error,
      latencyMs,
    };

  } catch (error) {
    const latencyMs = Date.now() - startTime;
    
    return {
      success: false,
      status: 'error',
      sessionId: event.sessionId,
      error: error instanceof Error ? error.message : String(error),
      latencyMs,
    };
  }
}

/**
 * Hook metadata for OpenClaw registration
 */
export function getConfig() {
  return HOOK_CONFIG;
}

/**
 * Health check endpoint
 */
export async function healthCheck(): Promise<{ healthy: boolean; message?: string }> {
  try {
    const { stdout } = await execAsync(`python3 "${PYTHON_HANDLER}" --help`);
    return { healthy: true };
  } catch (error) {
    return {
      healthy: false,
      message: `Python handler not available: ${error}`,
    };
  }
}

// Default export for OpenClaw hook system
export default {
  handleEvent,
  getConfig,
  healthCheck,
};
