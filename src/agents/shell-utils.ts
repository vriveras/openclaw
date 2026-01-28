import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import { shouldUseWindowsNative, buildWindowsShellCommand } from "../infra/windows-exec-shim.js";

function resolvePowerShellPath(): string {
  const systemRoot = process.env.SystemRoot || process.env.WINDIR;
  if (systemRoot) {
    const candidate = path.join(
      systemRoot,
      "System32",
      "WindowsPowerShell",
      "v1.0",
      "powershell.exe",
    );
    if (fs.existsSync(candidate)) return candidate;
  }
  return "powershell.exe";
}

/**
 * Get shell configuration for command execution.
 *
 * When CLAWDBOT_WINDOWS_NATIVE=true on Windows, uses the advanced Windows exec shim
 * which provides:
 * - PowerShell Core (pwsh) detection with fallback to Windows PowerShell
 * - Profile loading for predictable environment
 * - ExecutionPolicy bypass for scripts
 *
 * Otherwise falls back to standard behavior:
 * - Windows: Basic PowerShell detection via resolvePowerShellPath()
 * - Unix: User's $SHELL or fallback to sh (with fish → bash conversion)
 */
export function getShellConfig(): { shell: string; args: string[] } {
  // Use advanced Windows shim when feature flag enabled
  if (shouldUseWindowsNative()) {
    const result = buildWindowsShellCommand("");
    // Extract shell and args from the shim result
    // The shim returns { argv: [shell, ...args, command], shell, shellPath }
    // We need shell and the args without the final command placeholder
    return {
      shell: result.shellPath,
      args: result.argv.slice(1, -1), // Remove shell path and empty command
    };
  }

  if (process.platform === "win32") {
    // Legacy fallback: Use PowerShell instead of cmd.exe on Windows.
    // Problem: Many Windows system utilities (ipconfig, systeminfo, etc.) write
    // directly to the console via WriteConsole API, bypassing stdout pipes.
    // When Node.js spawns cmd.exe with piped stdio, these utilities produce no output.
    // PowerShell properly captures and redirects their output to stdout.
    return {
      shell: resolvePowerShellPath(),
      args: ["-NoProfile", "-NonInteractive", "-Command"],
    };
  }

  const envShell = process.env.SHELL?.trim();
  const shellName = envShell ? path.basename(envShell) : "";
  // Fish rejects common bashisms used by tools, so prefer bash when detected.
  if (shellName === "fish") {
    const bash = resolveShellFromPath("bash");
    if (bash) return { shell: bash, args: ["-c"] };
    const sh = resolveShellFromPath("sh");
    if (sh) return { shell: sh, args: ["-c"] };
  }
  const shell = envShell && envShell.length > 0 ? envShell : "sh";
  return { shell, args: ["-c"] };
}

function resolveShellFromPath(name: string): string | undefined {
  const envPath = process.env.PATH ?? "";
  if (!envPath) return undefined;
  const entries = envPath.split(path.delimiter).filter(Boolean);
  for (const entry of entries) {
    const candidate = path.join(entry, name);
    try {
      fs.accessSync(candidate, fs.constants.X_OK);
      return candidate;
    } catch {
      // ignore missing or non-executable entries
    }
  }
  return undefined;
}

export function sanitizeBinaryOutput(text: string): string {
  const scrubbed = text.replace(/[\p{Format}\p{Surrogate}]/gu, "");
  if (!scrubbed) return scrubbed;
  const chunks: string[] = [];
  for (const char of scrubbed) {
    const code = char.codePointAt(0);
    if (code == null) continue;
    if (code === 0x09 || code === 0x0a || code === 0x0d) {
      chunks.push(char);
      continue;
    }
    if (code < 0x20) continue;
    chunks.push(char);
  }
  return chunks.join("");
}

export function killProcessTree(pid: number): void {
  if (process.platform === "win32") {
    try {
      spawn("taskkill", ["/F", "/T", "/PID", String(pid)], {
        stdio: "ignore",
        detached: true,
      });
    } catch {
      // ignore errors if taskkill fails
    }
    return;
  }

  try {
    process.kill(-pid, "SIGKILL");
  } catch {
    try {
      process.kill(pid, "SIGKILL");
    } catch {
      // process already dead
    }
  }
}
