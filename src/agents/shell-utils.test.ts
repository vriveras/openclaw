import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getShellConfig } from "./shell-utils.js";
import * as windowsExecShim from "../infra/windows-exec-shim.js";

const isWin = process.platform === "win32";

describe("getShellConfig", () => {
  const originalShell = process.env.SHELL;
  const originalPath = process.env.PATH;
  const tempDirs: string[] = [];

  const createTempBin = (files: string[]) => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "moltbot-shell-"));
    tempDirs.push(dir);
    for (const name of files) {
      const filePath = path.join(dir, name);
      fs.writeFileSync(filePath, "");
      fs.chmodSync(filePath, 0o755);
    }
    return dir;
  };

  beforeEach(() => {
    if (!isWin) {
      process.env.SHELL = "/usr/bin/fish";
    }
  });

  afterEach(() => {
    if (originalShell == null) {
      delete process.env.SHELL;
    } else {
      process.env.SHELL = originalShell;
    }
    if (originalPath == null) {
      delete process.env.PATH;
    } else {
      process.env.PATH = originalPath;
    }
    for (const dir of tempDirs.splice(0)) {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  if (isWin) {
    it("uses PowerShell on Windows", () => {
      const { shell } = getShellConfig();
      expect(shell.toLowerCase()).toContain("powershell");
    });
    return;
  }

  it("prefers bash when fish is default and bash is on PATH", () => {
    const binDir = createTempBin(["bash"]);
    process.env.PATH = binDir;
    const { shell } = getShellConfig();
    expect(shell).toBe(path.join(binDir, "bash"));
  });

  it("falls back to sh when fish is default and bash is missing", () => {
    const binDir = createTempBin(["sh"]);
    process.env.PATH = binDir;
    const { shell } = getShellConfig();
    expect(shell).toBe(path.join(binDir, "sh"));
  });

  it("falls back to env shell when fish is default and no sh is available", () => {
    process.env.PATH = "";
    const { shell } = getShellConfig();
    expect(shell).toBe("/usr/bin/fish");
  });

  it("uses sh when SHELL is unset", () => {
    delete process.env.SHELL;
    process.env.PATH = "";
    const { shell } = getShellConfig();
    expect(shell).toBe("sh");
  });
});

describe("getShellConfig - Windows native feature flag", () => {
  const originalWindowsNative = process.env.CLAWDBOT_WINDOWS_NATIVE;

  afterEach(() => {
    vi.restoreAllMocks();
    if (originalWindowsNative == null) {
      delete process.env.CLAWDBOT_WINDOWS_NATIVE;
    } else {
      process.env.CLAWDBOT_WINDOWS_NATIVE = originalWindowsNative;
    }
  });

  it("uses Windows shim when flag is ON and shouldUseWindowsNative returns true", () => {
    // Mock shouldUseWindowsNative to return true (simulates Windows + flag enabled)
    vi.spyOn(windowsExecShim, "shouldUseWindowsNative").mockReturnValue(true);
    vi.spyOn(windowsExecShim, "buildWindowsShellCommand").mockReturnValue({
      argv: ["C:\\pwsh.exe", "-NoLogo", "-ExecutionPolicy", "Bypass", "-Command", ""],
      shell: "pwsh",
      shellPath: "C:\\pwsh.exe",
    });

    const { shell, args } = getShellConfig();

    expect(windowsExecShim.shouldUseWindowsNative).toHaveBeenCalled();
    expect(windowsExecShim.buildWindowsShellCommand).toHaveBeenCalledWith("");
    expect(shell).toBe("C:\\pwsh.exe");
    expect(args).toEqual(["-NoLogo", "-ExecutionPolicy", "Bypass", "-Command"]);
  });

  it("does NOT use shim when flag is OFF (shouldUseWindowsNative returns false)", () => {
    // Mock shouldUseWindowsNative to return false (flag disabled or not on Windows)
    vi.spyOn(windowsExecShim, "shouldUseWindowsNative").mockReturnValue(false);
    const buildSpy = vi.spyOn(windowsExecShim, "buildWindowsShellCommand");

    const { shell } = getShellConfig();

    expect(windowsExecShim.shouldUseWindowsNative).toHaveBeenCalled();
    // buildWindowsShellCommand should NOT be called when flag is off
    expect(buildSpy).not.toHaveBeenCalled();
    // On Linux test runner, should fall back to $SHELL logic
    expect(shell).toBeDefined();
  });

  it("Linux ignores flag entirely - uses $SHELL regardless", () => {
    // Even if somehow the flag check passed, Linux behavior shouldn't change
    // This tests that shouldUseWindowsNative correctly returns false on Linux
    process.env.CLAWDBOT_WINDOWS_NATIVE = "true";

    // Don't mock - let it run naturally to verify Linux isn't affected
    const result = windowsExecShim.shouldUseWindowsNative();

    // On Linux, shouldUseWindowsNative should return false regardless of env var
    // because isWindowsPlatform() returns false
    if (process.platform !== "win32") {
      expect(result).toBe(false);
    }
  });
});

describe("shouldUseWindowsNative - unit tests", () => {
  const originalWindowsNative = process.env.CLAWDBOT_WINDOWS_NATIVE;

  afterEach(() => {
    vi.restoreAllMocks();
    if (originalWindowsNative == null) {
      delete process.env.CLAWDBOT_WINDOWS_NATIVE;
    } else {
      process.env.CLAWDBOT_WINDOWS_NATIVE = originalWindowsNative;
    }
  });

  it("returns false when not on Windows", () => {
    // On the Linux test runner, this should always be false
    if (process.platform !== "win32") {
      process.env.CLAWDBOT_WINDOWS_NATIVE = "true";
      expect(windowsExecShim.shouldUseWindowsNative()).toBe(false);
    }
  });

  it("isWindowsNativeEnabled returns true for 'true'", () => {
    process.env.CLAWDBOT_WINDOWS_NATIVE = "true";
    expect(windowsExecShim.isWindowsNativeEnabled()).toBe(true);
  });

  it("isWindowsNativeEnabled returns true for '1'", () => {
    process.env.CLAWDBOT_WINDOWS_NATIVE = "1";
    expect(windowsExecShim.isWindowsNativeEnabled()).toBe(true);
  });

  it("isWindowsNativeEnabled returns true for 'yes'", () => {
    process.env.CLAWDBOT_WINDOWS_NATIVE = "yes";
    expect(windowsExecShim.isWindowsNativeEnabled()).toBe(true);
  });

  it("isWindowsNativeEnabled returns false for 'false'", () => {
    process.env.CLAWDBOT_WINDOWS_NATIVE = "false";
    expect(windowsExecShim.isWindowsNativeEnabled()).toBe(false);
  });

  it("isWindowsNativeEnabled returns false when unset", () => {
    delete process.env.CLAWDBOT_WINDOWS_NATIVE;
    expect(windowsExecShim.isWindowsNativeEnabled()).toBe(false);
  });

  it("isWindowsNativeEnabled handles case insensitivity", () => {
    process.env.CLAWDBOT_WINDOWS_NATIVE = "TRUE";
    expect(windowsExecShim.isWindowsNativeEnabled()).toBe(true);

    process.env.CLAWDBOT_WINDOWS_NATIVE = "True";
    expect(windowsExecShim.isWindowsNativeEnabled()).toBe(true);

    process.env.CLAWDBOT_WINDOWS_NATIVE = "YES";
    expect(windowsExecShim.isWindowsNativeEnabled()).toBe(true);
  });

  it("isWindowsNativeEnabled handles whitespace", () => {
    process.env.CLAWDBOT_WINDOWS_NATIVE = "  true  ";
    expect(windowsExecShim.isWindowsNativeEnabled()).toBe(true);
  });
});
