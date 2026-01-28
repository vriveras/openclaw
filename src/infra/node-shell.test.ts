import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { buildNodeShellCommand } from "./node-shell.js";

describe("buildNodeShellCommand", () => {
  describe("platform detection", () => {
    it("uses cmd.exe for win32", () => {
      expect(buildNodeShellCommand("echo hi", "win32")).toEqual([
        "cmd.exe",
        "/d",
        "/s",
        "/c",
        "echo hi",
      ]);
    });

    it("uses cmd.exe for windows labels", () => {
      expect(buildNodeShellCommand("echo hi", "windows")).toEqual([
        "cmd.exe",
        "/d",
        "/s",
        "/c",
        "echo hi",
      ]);
      expect(buildNodeShellCommand("echo hi", "Windows 11")).toEqual([
        "cmd.exe",
        "/d",
        "/s",
        "/c",
        "echo hi",
      ]);
    });

    it("uses /bin/sh for linux", () => {
      expect(buildNodeShellCommand("echo hi", "linux")).toEqual(["/bin/sh", "-lc", "echo hi"]);
    });

    it("uses /bin/sh for darwin", () => {
      expect(buildNodeShellCommand("echo hi", "darwin")).toEqual(["/bin/sh", "-lc", "echo hi"]);
    });

    it("uses /bin/sh when platform is null", () => {
      expect(buildNodeShellCommand("echo hi", null)).toEqual(["/bin/sh", "-lc", "echo hi"]);
    });

    it("uses /bin/sh when platform is omitted", () => {
      expect(buildNodeShellCommand("echo hi")).toEqual(["/bin/sh", "-lc", "echo hi"]);
    });
  });

  describe("feature flag CLAWDBOT_WINDOWS_NATIVE", () => {
    const originalEnv = process.env.CLAWDBOT_WINDOWS_NATIVE;

    afterEach(() => {
      // Restore original env
      if (originalEnv === undefined) {
        delete process.env.CLAWDBOT_WINDOWS_NATIVE;
      } else {
        process.env.CLAWDBOT_WINDOWS_NATIVE = originalEnv;
      }
    });

    it("win32 without flag uses cmd.exe (legacy behavior)", () => {
      delete process.env.CLAWDBOT_WINDOWS_NATIVE;
      expect(buildNodeShellCommand("echo hi", "win32")).toEqual([
        "cmd.exe",
        "/d",
        "/s",
        "/c",
        "echo hi",
      ]);
    });

    it("win32 with flag=false uses cmd.exe (legacy behavior)", () => {
      process.env.CLAWDBOT_WINDOWS_NATIVE = "false";
      expect(buildNodeShellCommand("echo hi", "win32")).toEqual([
        "cmd.exe",
        "/d",
        "/s",
        "/c",
        "echo hi",
      ]);
    });

    // Note: When CLAWDBOT_WINDOWS_NATIVE=true on win32, the code path
    // calls buildShellCommandArgv which uses PowerShell when available.
    // This is tested in windows-exec-shim.test.ts since it requires
    // mocking process.platform and PowerShell detection.

    it("linux ignores feature flag", () => {
      process.env.CLAWDBOT_WINDOWS_NATIVE = "true";
      expect(buildNodeShellCommand("echo hi", "linux")).toEqual(["/bin/sh", "-lc", "echo hi"]);
    });

    it("darwin ignores feature flag", () => {
      process.env.CLAWDBOT_WINDOWS_NATIVE = "true";
      expect(buildNodeShellCommand("echo hi", "darwin")).toEqual(["/bin/sh", "-lc", "echo hi"]);
    });
  });
});
