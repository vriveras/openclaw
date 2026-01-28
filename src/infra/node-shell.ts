import { shouldUseWindowsNative, buildShellCommandArgv } from "./windows-exec-shim.js";

export function buildNodeShellCommand(command: string, platform?: string | null) {
  const normalized = String(platform ?? process.platform)
    .trim()
    .toLowerCase();

  const isWindows = normalized.startsWith("win") || normalized === "win32";

  // Use advanced shim when feature flag enabled on Windows
  if (isWindows && shouldUseWindowsNative()) {
    return buildShellCommandArgv(command, normalized);
  }

  // Legacy behavior
  if (isWindows) {
    return ["cmd.exe", "/d", "/s", "/c", command];
  }
  return ["/bin/sh", "-lc", command];
}
