/**
 * Windows Exec Shim
 *
 * Provides a cross-platform shell execution abstraction that enables native
 * Windows support when the CLAWDBOT_WINDOWS_NATIVE feature flag is enabled.
 *
 * When enabled on Windows:
 * - Uses PowerShell (pwsh or powershell.exe) as the primary shell
 * - Loads user profile for predictable environment
 * - Falls back to cmd.exe if PowerShell unavailable
 * - Handles path normalization (WSL ↔ Windows)
 *
 * When disabled or on non-Windows:
 * - Uses existing behavior (/bin/sh -lc)
 */

import { existsSync } from "node:fs";
import { execSync } from "node:child_process";

import { resolvePathForExec, isWslMountPath, wslToWindows } from "./windows-paths.js";
import { maybeTranslateCmdToPs } from "./windows-cmd-compat.js";

// Feature flag check
const WINDOWS_NATIVE_ENV = "CLAWDBOT_WINDOWS_NATIVE";

/**
 * Check if Windows native mode is enabled
 */
export function isWindowsNativeEnabled(): boolean {
  const envValue = process.env[WINDOWS_NATIVE_ENV]?.toLowerCase().trim();
  return envValue === "true" || envValue === "1" || envValue === "yes";
}

/**
 * Check if running on Windows platform
 */
export function isWindowsPlatform(): boolean {
  return process.platform === "win32";
}

/**
 * Check if we should use Windows native execution
 */
export function shouldUseWindowsNative(): boolean {
  return isWindowsPlatform() && isWindowsNativeEnabled();
}

/**
 * PowerShell detection result
 */
export type PowerShellInfo = {
  available: boolean;
  path: string | null;
  variant: "pwsh" | "powershell" | null;
};

// Cache for PowerShell detection
let cachedPowerShellInfo: PowerShellInfo | null = null;

/**
 * Detect available PowerShell installation
 * Prefers pwsh (PowerShell Core) over powershell.exe (Windows PowerShell)
 */
export function detectPowerShell(): PowerShellInfo {
  if (cachedPowerShellInfo !== null) {
    return cachedPowerShellInfo;
  }

  // Try pwsh (PowerShell Core) first - cross-platform, newer
  const pwshPaths = [
    "C:\\Program Files\\PowerShell\\7\\pwsh.exe",
    "C:\\Program Files\\PowerShell\\pwsh.exe",
    // Check if pwsh is in PATH
  ];

  for (const pwshPath of pwshPaths) {
    if (existsSync(pwshPath)) {
      cachedPowerShellInfo = {
        available: true,
        path: pwshPath,
        variant: "pwsh",
      };
      return cachedPowerShellInfo;
    }
  }

  // Try to find pwsh in PATH
  try {
    const result = execSync("where pwsh.exe", {
      encoding: "utf8",
      timeout: 5000,
      stdio: ["ignore", "pipe", "ignore"],
    });
    const path = result.trim().split("\n")[0]?.trim();
    if (path && existsSync(path)) {
      cachedPowerShellInfo = {
        available: true,
        path,
        variant: "pwsh",
      };
      return cachedPowerShellInfo;
    }
  } catch {
    // pwsh not in PATH
  }

  // Fallback to Windows PowerShell (powershell.exe)
  const powerShellPaths = [
    "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
    "C:\\Windows\\SysWOW64\\WindowsPowerShell\\v1.0\\powershell.exe",
  ];

  for (const psPath of powerShellPaths) {
    if (existsSync(psPath)) {
      cachedPowerShellInfo = {
        available: true,
        path: psPath,
        variant: "powershell",
      };
      return cachedPowerShellInfo;
    }
  }

  // Try to find powershell.exe in PATH
  try {
    const result = execSync("where powershell.exe", {
      encoding: "utf8",
      timeout: 5000,
      stdio: ["ignore", "pipe", "ignore"],
    });
    const path = result.trim().split("\n")[0]?.trim();
    if (path && existsSync(path)) {
      cachedPowerShellInfo = {
        available: true,
        path,
        variant: "powershell",
      };
      return cachedPowerShellInfo;
    }
  } catch {
    // powershell.exe not in PATH
  }

  // No PowerShell found
  cachedPowerShellInfo = {
    available: false,
    path: null,
    variant: null,
  };
  return cachedPowerShellInfo;
}

/**
 * Reset PowerShell cache (for testing)
 */
export function resetPowerShellCache(): void {
  cachedPowerShellInfo = null;
}

/**
 * Shell type used for execution
 */
export type ShellType = "powershell" | "pwsh" | "cmd" | "sh";

/**
 * Result of building a shell command
 */
export type ShellCommand = {
  argv: string[];
  shell: ShellType;
  shellPath: string;
};

/**
 * Build shell command for Windows native execution
 *
 * Priority:
 * 1. pwsh (PowerShell Core) - if available
 * 2. powershell.exe (Windows PowerShell) - if available
 * 3. cmd.exe - fallback
 *
 * PowerShell args:
 * - -NoLogo: Cleaner output
 * - -ExecutionPolicy Bypass: Avoid policy blocks for scripts
 * - -Command: Execute the command string
 *
 * Note: We intentionally load the profile for predictable environment.
 * Use -NoProfile if you need faster startup without user customizations.
 *
 * CMD compatibility: When using PowerShell, CMD-style commands are
 * automatically translated (e.g., `dir /b` → `Get-ChildItem -Name`).
 */
export function buildWindowsShellCommand(command: string): ShellCommand {
  const psInfo = detectPowerShell();

  if (psInfo.available && psInfo.path) {
    // Translate CMD-style commands to PowerShell equivalents
    const { translated } = maybeTranslateCmdToPs(command);

    // Use PowerShell with profile loading
    // -NoLogo: Skip the PowerShell banner
    // -ExecutionPolicy Bypass: Allow running scripts
    // -Command: Run the command
    // Note: NOT using -NoProfile so user profile loads (predictable environment)
    return {
      argv: [psInfo.path, "-NoLogo", "-ExecutionPolicy", "Bypass", "-Command", translated],
      shell: psInfo.variant!,
      shellPath: psInfo.path,
    };
  }

  // Fallback to cmd.exe (no translation needed)
  return {
    argv: ["cmd.exe", "/d", "/s", "/c", command],
    shell: "cmd",
    shellPath: "cmd.exe",
  };
}

/**
 * Build shell command for Unix execution (existing behavior)
 */
export function buildUnixShellCommand(command: string): ShellCommand {
  const shell = process.env.SHELL?.trim() || "/bin/sh";
  return {
    argv: [shell, "-lc", command],
    shell: "sh",
    shellPath: shell,
  };
}

/**
 * Build the appropriate shell command based on platform and feature flags
 *
 * This is the main entry point for the shim. Use this instead of
 * directly calling buildNodeShellCommand().
 *
 * @param command - The command string to execute
 * @param options - Optional overrides
 * @returns Shell command with argv and metadata
 */
export function buildShellCommand(
  command: string,
  options?: {
    /** Force a specific platform (for testing) */
    platform?: string;
    /** Force Windows native mode (for testing) */
    forceWindowsNative?: boolean;
  },
): ShellCommand {
  const platform = options?.platform ?? process.platform;
  const isWindows = platform === "win32" || platform.toLowerCase().startsWith("win");
  const useWindowsNative = options?.forceWindowsNative ?? isWindowsNativeEnabled();

  if (isWindows && useWindowsNative) {
    return buildWindowsShellCommand(command);
  }

  if (isWindows) {
    // Windows but not native mode - use cmd.exe (legacy behavior)
    return {
      argv: ["cmd.exe", "/d", "/s", "/c", command],
      shell: "cmd",
      shellPath: "cmd.exe",
    };
  }

  // Unix/Linux/macOS
  return buildUnixShellCommand(command);
}

/**
 * Get shell command as simple argv array (for compatibility with existing code)
 *
 * This matches the signature of the existing buildNodeShellCommand() function.
 */
export function buildShellCommandArgv(command: string, platform?: string | null): string[] {
  const result = buildShellCommand(command, {
    platform: platform ?? undefined,
  });
  return result.argv;
}

/**
 * Resolve working directory for Windows execution.
 * Converts WSL paths to Windows paths when needed.
 */
export function resolveWindowsWorkdir(cwd?: string): string | undefined {
  if (!cwd) return undefined;

  // Convert WSL mount paths to Windows paths
  if (isWslMountPath(cwd)) {
    const converted = wslToWindows(cwd);
    if (converted) return converted;
  }

  return cwd;
}

/**
 * Log which shell is being used (for debugging)
 */
export function getShellInfo(): {
  platform: string;
  windowsNativeEnabled: boolean;
  shouldUseWindowsNative: boolean;
  powerShell: PowerShellInfo;
} {
  return {
    platform: process.platform,
    windowsNativeEnabled: isWindowsNativeEnabled(),
    shouldUseWindowsNative: shouldUseWindowsNative(),
    powerShell: detectPowerShell(),
  };
}
