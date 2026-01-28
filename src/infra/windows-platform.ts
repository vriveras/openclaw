import { execFileSync } from "child_process";

/**
 * Check if the current platform is Windows.
 */
export function isWindows(): boolean {
  return process.platform === "win32";
}

// Cache for PowerShell availability check
let powerShellAvailable: boolean | null = null;

/**
 * Check if PowerShell is available on the system.
 * Result is cached after first check.
 */
export function isPowerShellAvailable(): boolean {
  if (powerShellAvailable !== null) {
    return powerShellAvailable;
  }

  try {
    execFileSync("powershell.exe", ["-Command", "exit 0"], {
      timeout: 2000,
      stdio: "ignore",
    });
    powerShellAvailable = true;
  } catch {
    powerShellAvailable = false;
  }

  return powerShellAvailable;
}

/**
 * Shell configuration for Windows command execution.
 */
export interface WindowsShellInfo {
  shell: string;
  args: string[];
}

/**
 * Get the preferred Windows shell configuration.
 * Returns PowerShell if available, otherwise falls back to cmd.exe.
 */
export function getWindowsShell(): WindowsShellInfo {
  if (isPowerShellAvailable()) {
    return {
      shell: "powershell.exe",
      args: ["-NoProfile", "-Command"],
    };
  }

  return {
    shell: "cmd.exe",
    args: ["/d", "/s", "/c"],
  };
}
