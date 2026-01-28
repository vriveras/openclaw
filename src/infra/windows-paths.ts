/**
 * Windows path conversion utilities for WSL ↔ Windows interoperability.
 *
 * @module windows-paths
 */

/**
 * Platform target for path normalization.
 */
export type Platform = "windows" | "unix";

/**
 * Options for resolving paths for execution context.
 */
export interface ResolvePathOptions {
  /** Target platform for the path */
  targetPlatform: Platform;
  /** Whether to expand environment variables (Windows only) */
  expandEnvVars?: boolean;
  /** Environment variables to use for expansion (defaults to process.env) */
  env?: Record<string, string | undefined>;
}

/**
 * Check if a path is a WSL mount path (e.g., /mnt/c/, /mnt/d/).
 *
 * @param path - The path to check
 * @returns True if the path is a WSL mount path
 *
 * @example
 * isWslMountPath("/mnt/c/Users") // true
 * isWslMountPath("/home/user") // false
 * isWslMountPath("") // false
 */
export function isWslMountPath(path: string | null | undefined): boolean {
  if (!path || typeof path !== "string") {
    return false;
  }
  // Match /mnt/X/ where X is a single letter (drive letter)
  return /^\/mnt\/[a-zA-Z](\/|$)/.test(path);
}

/**
 * Check if a path is an absolute Windows path (e.g., C:\, D:\).
 *
 * @param path - The path to check
 * @returns True if the path is an absolute Windows path
 *
 * @example
 * isAbsoluteWindowsPath("C:\\Users") // true
 * isAbsoluteWindowsPath("C:/Users") // true
 * isAbsoluteWindowsPath("/home/user") // false
 * isAbsoluteWindowsPath("") // false
 */
export function isAbsoluteWindowsPath(path: string | null | undefined): boolean {
  if (!path || typeof path !== "string") {
    return false;
  }
  // Match X:\ or X:/ where X is a single letter
  return /^[a-zA-Z]:[\\/]/.test(path);
}

/**
 * Check if a path is a UNC path (e.g., \\server\share).
 *
 * @param path - The path to check
 * @returns True if the path is a UNC path
 *
 * @example
 * isUncPath("\\\\server\\share") // true
 * isUncPath("//server/share") // true
 * isUncPath("C:\\Users") // false
 * isUncPath("") // false
 */
export function isUncPath(path: string | null | undefined): boolean {
  if (!path || typeof path !== "string") {
    return false;
  }
  // Match \\server\share or //server/share
  return /^(\\\\|\/\/)[^\\\/]+[\\\/][^\\\/]/.test(path);
}

/**
 * Convert a WSL path to a Windows path.
 *
 * @param wslPath - The WSL path to convert (e.g., /mnt/c/Users/foo)
 * @returns The Windows path (e.g., C:\Users\foo), or the original path if not a WSL mount path
 *
 * @example
 * wslToWindows("/mnt/c/Users/foo") // "C:\\Users\\foo"
 * wslToWindows("/mnt/d/projects") // "D:\\projects"
 * wslToWindows("/home/user") // "/home/user" (unchanged)
 * wslToWindows("") // ""
 * wslToWindows(null) // ""
 */
export function wslToWindows(wslPath: string | null | undefined): string {
  if (!wslPath || typeof wslPath !== "string") {
    return "";
  }

  if (!isWslMountPath(wslPath)) {
    return wslPath;
  }

  // Extract drive letter and remaining path
  const match = wslPath.match(/^\/mnt\/([a-zA-Z])(\/.*)?$/);
  if (!match) {
    return wslPath;
  }

  const driveLetter = match[1].toUpperCase();
  const remainingPath = match[2] || "";

  // Convert forward slashes to backslashes
  const windowsPath = remainingPath.replace(/\//g, "\\");

  return `${driveLetter}:${windowsPath || "\\"}`;
}

/**
 * Convert a Windows path to a WSL path.
 *
 * @param winPath - The Windows path to convert (e.g., C:\Users\foo)
 * @returns The WSL path (e.g., /mnt/c/Users/foo), or the original path if not a Windows path
 *
 * @example
 * windowsToWsl("C:\\Users\\foo") // "/mnt/c/Users/foo"
 * windowsToWsl("D:/projects") // "/mnt/d/projects"
 * windowsToWsl("/home/user") // "/home/user" (unchanged)
 * windowsToWsl("") // ""
 * windowsToWsl(null) // ""
 */
export function windowsToWsl(winPath: string | null | undefined): string {
  if (!winPath || typeof winPath !== "string") {
    return "";
  }

  if (!isAbsoluteWindowsPath(winPath)) {
    return winPath;
  }

  // Extract drive letter
  const driveLetter = winPath[0].toLowerCase();

  // Get the path after the drive letter and colon
  let remainingPath = winPath.slice(2);

  // Convert backslashes to forward slashes
  remainingPath = remainingPath.replace(/\\/g, "/");

  // Ensure path starts with /
  if (!remainingPath.startsWith("/")) {
    remainingPath = "/" + remainingPath;
  }

  // Handle root path (just the drive)
  if (remainingPath === "/") {
    return `/mnt/${driveLetter}`;
  }

  return `/mnt/${driveLetter}${remainingPath}`;
}

/**
 * Normalize path slashes for the target platform.
 *
 * @param path - The path to normalize
 * @param platform - The target platform ("windows" or "unix")
 * @returns The normalized path with appropriate slashes
 *
 * @example
 * normalizePath("/mnt/c/Users/foo", "windows") // "\\mnt\\c\\Users\\foo"
 * normalizePath("C:\\Users\\foo", "unix") // "C:/Users/foo"
 * normalizePath("", "windows") // ""
 * normalizePath(null, "unix") // ""
 */
export function normalizePath(path: string | null | undefined, platform: Platform): string {
  if (!path || typeof path !== "string") {
    return "";
  }

  if (platform === "windows") {
    return path.replace(/\//g, "\\");
  }

  return path.replace(/\\/g, "/");
}

/**
 * Expand Windows environment variables in a path.
 * Variables are in the format %VARNAME%.
 *
 * @param path - The path containing environment variables
 * @param env - Optional environment object (defaults to process.env)
 * @returns The path with environment variables expanded
 *
 * @example
 * expandWindowsEnvVars("%USERPROFILE%\\Documents") // "C:\\Users\\foo\\Documents"
 * expandWindowsEnvVars("%TEMP%\\file.txt") // "C:\\Users\\foo\\AppData\\Local\\Temp\\file.txt"
 * expandWindowsEnvVars("no-vars-here") // "no-vars-here"
 * expandWindowsEnvVars("") // ""
 * expandWindowsEnvVars(null) // ""
 */
export function expandWindowsEnvVars(
  path: string | null | undefined,
  env: Record<string, string | undefined> = process.env,
): string {
  if (!path || typeof path !== "string") {
    return "";
  }

  // Replace %VARNAME% patterns with their values
  return path.replace(/%([^%]+)%/g, (_match, varName: string) => {
    // Try exact match first
    const value = env[varName];
    if (value !== undefined) {
      return value;
    }

    // Try case-insensitive match (Windows env vars are case-insensitive)
    const upperVarName = varName.toUpperCase();
    for (const [key, val] of Object.entries(env)) {
      if (key.toUpperCase() === upperVarName && val !== undefined) {
        return val;
      }
    }

    // Return original if not found
    return `%${varName}%`;
  });
}

/**
 * Resolve a path for execution in a specific context.
 * Automatically converts between WSL and Windows paths as needed,
 * and optionally expands environment variables.
 *
 * @param path - The path to resolve
 * @param options - Resolution options
 * @returns The resolved path appropriate for the target platform
 *
 * @example
 * // Convert WSL path to Windows
 * resolvePathForExec("/mnt/c/Users/foo", { targetPlatform: "windows" })
 * // Returns: "C:\\Users\\foo"
 *
 * // Convert Windows path to WSL
 * resolvePathForExec("C:\\Users\\foo", { targetPlatform: "unix" })
 * // Returns: "/mnt/c/Users/foo"
 *
 * // Expand environment variables
 * resolvePathForExec("%USERPROFILE%\\Documents", {
 *   targetPlatform: "windows",
 *   expandEnvVars: true
 * })
 * // Returns: "C:\\Users\\foo\\Documents"
 */
export function resolvePathForExec(
  path: string | null | undefined,
  options: ResolvePathOptions,
): string {
  if (!path || typeof path !== "string") {
    return "";
  }

  const { targetPlatform, expandEnvVars = false, env = process.env } = options;

  let result = path;

  // Expand environment variables first if requested (for Windows-style %VAR%)
  if (expandEnvVars) {
    result = expandWindowsEnvVars(result, env);
  }

  if (targetPlatform === "windows") {
    // Convert WSL paths to Windows paths
    if (isWslMountPath(result)) {
      result = wslToWindows(result);
    }
    // Normalize to Windows slashes
    result = normalizePath(result, "windows");
  } else {
    // targetPlatform === "unix"
    // Convert Windows paths to WSL paths
    if (isAbsoluteWindowsPath(result)) {
      result = windowsToWsl(result);
    }
    // Normalize to Unix slashes
    result = normalizePath(result, "unix");
  }

  return result;
}
