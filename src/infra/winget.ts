/**
 * Windows Package Manager Utilities
 *
 * Detection and helpers for winget (Windows Package Manager) and
 * chocolatey as a fallback. Mirrors the pattern in brew.ts.
 */

import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

/**
 * Check if running on Windows
 */
export function isWindowsPlatform(): boolean {
  return process.platform === "win32";
}

function isExecutable(filePath: string): boolean {
  try {
    fs.accessSync(filePath, fs.constants.X_OK);
    return true;
  } catch {
    // On Windows, check if file exists (X_OK not reliable)
    if (isWindowsPlatform()) {
      return fs.existsSync(filePath);
    }
    return false;
  }
}

function findInPath(executable: string): string | undefined {
  if (!isWindowsPlatform()) return undefined;

  try {
    const result = execSync(`where ${executable}`, {
      encoding: "utf8",
      timeout: 5000,
      stdio: ["ignore", "pipe", "ignore"],
    });
    const firstLine = result.trim().split("\n")[0]?.trim();
    if (firstLine && fs.existsSync(firstLine)) {
      return firstLine;
    }
  } catch {
    // Not found in PATH
  }
  return undefined;
}

/**
 * Resolve the path to winget.exe
 *
 * Checks:
 * 1. %LOCALAPPDATA%\Microsoft\WindowsApps\winget.exe
 * 2. PATH via `where winget`
 */
export function resolveWingetExecutable(opts?: { env?: NodeJS.ProcessEnv }): string | undefined {
  if (!isWindowsPlatform()) return undefined;

  const env = opts?.env ?? process.env;
  const candidates: string[] = [];

  // Primary location: WindowsApps
  const localAppData = env.LOCALAPPDATA;
  if (localAppData) {
    candidates.push(path.join(localAppData, "Microsoft", "WindowsApps", "winget.exe"));
  }

  // Also check Program Files (for some installs)
  const programFiles = env["ProgramFiles"];
  if (programFiles) {
    candidates.push(path.join(programFiles, "WindowsApps", "winget.exe"));
  }

  // Check candidates
  for (const candidate of candidates) {
    if (isExecutable(candidate)) return candidate;
  }

  // Fallback: check PATH
  return findInPath("winget.exe") ?? findInPath("winget");
}

/**
 * Resolve the path to choco.exe (Chocolatey)
 *
 * Checks:
 * 1. C:\ProgramData\chocolatey\bin\choco.exe
 * 2. PATH via `where choco`
 */
export function resolveChocoExecutable(opts?: { env?: NodeJS.ProcessEnv }): string | undefined {
  if (!isWindowsPlatform()) return undefined;

  const env = opts?.env ?? process.env;
  const candidates: string[] = [];

  // Standard Chocolatey install location
  const programData = env.ProgramData ?? "C:\\ProgramData";
  candidates.push(path.join(programData, "chocolatey", "bin", "choco.exe"));

  // Alternative: ChocolateyInstall env var
  const chocoInstall = env.ChocolateyInstall;
  if (chocoInstall) {
    candidates.push(path.join(chocoInstall, "bin", "choco.exe"));
  }

  // Check candidates
  for (const candidate of candidates) {
    if (isExecutable(candidate)) return candidate;
  }

  // Fallback: check PATH
  return findInPath("choco.exe") ?? findInPath("choco");
}

/**
 * Windows package manager info
 */
export type WindowsPackageManager = {
  manager: "winget" | "choco";
  path: string;
} | null;

/**
 * Get the best available Windows package manager
 *
 * Preference order:
 * 1. winget (built into Windows 10+)
 * 2. chocolatey (fallback, wider package coverage)
 *
 * Returns null if neither is available.
 */
export function getWindowsPackageManager(opts?: {
  env?: NodeJS.ProcessEnv;
}): WindowsPackageManager {
  if (!isWindowsPlatform()) return null;

  // Prefer winget
  const wingetPath = resolveWingetExecutable(opts);
  if (wingetPath) {
    return { manager: "winget", path: wingetPath };
  }

  // Fallback to chocolatey
  const chocoPath = resolveChocoExecutable(opts);
  if (chocoPath) {
    return { manager: "choco", path: chocoPath };
  }

  return null;
}

/**
 * Build winget install command
 *
 * @param packageId - The winget package ID (e.g., "GitHub.cli")
 * @returns Command argv array
 */
export function buildWingetInstallCommand(packageId: string): string[] {
  return [
    "winget",
    "install",
    "--id",
    packageId,
    "--exact",
    "--accept-source-agreements",
    "--accept-package-agreements",
    "--silent",
  ];
}

/**
 * Build chocolatey install command
 *
 * @param packageName - The choco package name (e.g., "gh")
 * @returns Command argv array
 */
export function buildChocoInstallCommand(packageName: string): string[] {
  return ["choco", "install", packageName, "-y", "--no-progress"];
}

/**
 * Check if winget is available
 */
export function hasWinget(opts?: { env?: NodeJS.ProcessEnv }): boolean {
  return resolveWingetExecutable(opts) !== undefined;
}

/**
 * Check if chocolatey is available
 */
export function hasChoco(opts?: { env?: NodeJS.ProcessEnv }): boolean {
  return resolveChocoExecutable(opts) !== undefined;
}
