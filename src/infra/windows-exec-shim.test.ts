import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

import {
  isWindowsNativeEnabled,
  isWindowsPlatform,
  shouldUseWindowsNative,
  buildShellCommand,
  buildShellCommandArgv,
  buildWindowsShellCommand,
  buildUnixShellCommand,
  resetPowerShellCache,
  getShellInfo,
} from "./windows-exec-shim.js";

describe("windows-exec-shim", () => {
  const originalEnv = process.env;
  const originalPlatform = process.platform;

  beforeEach(() => {
    // Reset environment and caches
    process.env = { ...originalEnv };
    delete process.env.CLAWDBOT_WINDOWS_NATIVE;
    resetPowerShellCache();
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  describe("isWindowsNativeEnabled", () => {
    it("returns false when env not set", () => {
      delete process.env.CLAWDBOT_WINDOWS_NATIVE;
      expect(isWindowsNativeEnabled()).toBe(false);
    });

    it("returns true when env is 'true'", () => {
      process.env.CLAWDBOT_WINDOWS_NATIVE = "true";
      expect(isWindowsNativeEnabled()).toBe(true);
    });

    it("returns true when env is 'TRUE'", () => {
      process.env.CLAWDBOT_WINDOWS_NATIVE = "TRUE";
      expect(isWindowsNativeEnabled()).toBe(true);
    });

    it("returns true when env is '1'", () => {
      process.env.CLAWDBOT_WINDOWS_NATIVE = "1";
      expect(isWindowsNativeEnabled()).toBe(true);
    });

    it("returns true when env is 'yes'", () => {
      process.env.CLAWDBOT_WINDOWS_NATIVE = "yes";
      expect(isWindowsNativeEnabled()).toBe(true);
    });

    it("returns false when env is 'false'", () => {
      process.env.CLAWDBOT_WINDOWS_NATIVE = "false";
      expect(isWindowsNativeEnabled()).toBe(false);
    });

    it("returns false when env is empty", () => {
      process.env.CLAWDBOT_WINDOWS_NATIVE = "";
      expect(isWindowsNativeEnabled()).toBe(false);
    });
  });

  describe("isWindowsPlatform", () => {
    it("returns true on win32", () => {
      // This test will pass/fail based on actual platform
      // We test the function exists and returns boolean
      expect(typeof isWindowsPlatform()).toBe("boolean");
    });
  });

  describe("buildShellCommand", () => {
    it("uses cmd.exe on windows without native flag", () => {
      const result = buildShellCommand("echo hello", {
        platform: "win32",
        forceWindowsNative: false,
      });

      expect(result.shell).toBe("cmd");
      expect(result.argv).toEqual(["cmd.exe", "/d", "/s", "/c", "echo hello"]);
    });

    it("uses /bin/sh on linux", () => {
      process.env.SHELL = "/bin/bash";
      const result = buildShellCommand("echo hello", {
        platform: "linux",
      });

      expect(result.shell).toBe("sh");
      expect(result.argv[0]).toBe("/bin/bash");
      expect(result.argv[1]).toBe("-lc");
      expect(result.argv[2]).toBe("echo hello");
    });

    it("uses /bin/sh on darwin", () => {
      process.env.SHELL = "/bin/zsh";
      const result = buildShellCommand("echo hello", {
        platform: "darwin",
      });

      expect(result.shell).toBe("sh");
      expect(result.argv[0]).toBe("/bin/zsh");
    });

    it("falls back to /bin/sh when SHELL not set", () => {
      delete process.env.SHELL;
      const result = buildShellCommand("echo hello", {
        platform: "linux",
      });

      expect(result.argv[0]).toBe("/bin/sh");
    });
  });

  describe("buildShellCommandArgv", () => {
    it("returns argv array for compatibility", () => {
      const result = buildShellCommandArgv("echo hello", "linux");

      expect(Array.isArray(result)).toBe(true);
      expect(result.length).toBeGreaterThan(0);
    });

    it("handles null platform", () => {
      const result = buildShellCommandArgv("echo hello", null);

      expect(Array.isArray(result)).toBe(true);
    });
  });

  describe("buildUnixShellCommand", () => {
    it("uses SHELL env var", () => {
      process.env.SHELL = "/usr/bin/fish";
      const result = buildUnixShellCommand("ls");

      expect(result.argv[0]).toBe("/usr/bin/fish");
      expect(result.argv[1]).toBe("-lc");
      expect(result.argv[2]).toBe("ls");
      expect(result.shell).toBe("sh");
    });

    it("falls back to /bin/sh", () => {
      delete process.env.SHELL;
      const result = buildUnixShellCommand("ls");

      expect(result.argv[0]).toBe("/bin/sh");
    });
  });

  describe("buildWindowsShellCommand", () => {
    // Note: These tests run on any platform but test the logic
    // Actual PowerShell detection will vary by machine

    it("returns a valid shell command structure", () => {
      const result = buildWindowsShellCommand("echo hello");

      expect(result).toHaveProperty("argv");
      expect(result).toHaveProperty("shell");
      expect(result).toHaveProperty("shellPath");
      expect(Array.isArray(result.argv)).toBe(true);
      expect(result.argv.length).toBeGreaterThan(0);
    });

    it("includes the command in argv", () => {
      const result = buildWindowsShellCommand("echo hello");

      // Command should be in the argv somewhere
      expect(result.argv.some((arg) => arg.includes("echo hello"))).toBe(true);
    });

    it("translates CMD-style dir /b to PowerShell Get-ChildItem -Name", () => {
      const result = buildWindowsShellCommand("dir /b");

      // If PowerShell is available, command should be translated
      // If cmd.exe fallback, original command is used
      if (result.shell === "pwsh" || result.shell === "powershell") {
        expect(result.argv.some((arg) => arg.includes("Get-ChildItem -Name"))).toBe(true);
      } else {
        expect(result.argv.some((arg) => arg.includes("dir /b"))).toBe(true);
      }
    });

    it("translates CMD-style del /q to PowerShell Remove-Item -Force", () => {
      const result = buildWindowsShellCommand("del /q file.txt");

      if (result.shell === "pwsh" || result.shell === "powershell") {
        expect(result.argv.some((arg) => arg.includes("Remove-Item -Force"))).toBe(true);
      }
    });

    it("passes through PowerShell commands unchanged", () => {
      const result = buildWindowsShellCommand("Get-ChildItem -Recurse");

      expect(result.argv.some((arg) => arg.includes("Get-ChildItem -Recurse"))).toBe(true);
    });
  });

  describe("getShellInfo", () => {
    it("returns shell information object", () => {
      const info = getShellInfo();

      expect(info).toHaveProperty("platform");
      expect(info).toHaveProperty("windowsNativeEnabled");
      expect(info).toHaveProperty("shouldUseWindowsNative");
      expect(info).toHaveProperty("powerShell");
      expect(typeof info.platform).toBe("string");
      expect(typeof info.windowsNativeEnabled).toBe("boolean");
    });
  });
});
