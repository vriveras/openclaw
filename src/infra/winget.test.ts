import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import {
  isWindowsPlatform,
  resolveWingetExecutable,
  resolveChocoExecutable,
  getWindowsPackageManager,
  buildWingetInstallCommand,
  buildChocoInstallCommand,
  hasWinget,
  hasChoco,
} from "./winget.js";

describe("winget", () => {
  describe("isWindowsPlatform", () => {
    it("returns a boolean", () => {
      expect(typeof isWindowsPlatform()).toBe("boolean");
    });

    it("returns true on win32", () => {
      // This test documents expected behavior
      // Actual result depends on platform running tests
      const result = isWindowsPlatform();
      if (process.platform === "win32") {
        expect(result).toBe(true);
      } else {
        expect(result).toBe(false);
      }
    });
  });

  describe("resolveWingetExecutable", () => {
    it("returns undefined on non-Windows", () => {
      if (process.platform !== "win32") {
        expect(resolveWingetExecutable()).toBeUndefined();
      }
    });

    it("returns string or undefined", () => {
      const result = resolveWingetExecutable();
      expect(result === undefined || typeof result === "string").toBe(true);
    });

    it("checks LOCALAPPDATA path", () => {
      // On Windows, should check the WindowsApps directory
      if (process.platform === "win32") {
        const result = resolveWingetExecutable();
        // May or may not find winget, but shouldn't throw
        expect(result === undefined || result.includes("winget")).toBe(true);
      }
    });
  });

  describe("resolveChocoExecutable", () => {
    it("returns undefined on non-Windows", () => {
      if (process.platform !== "win32") {
        expect(resolveChocoExecutable()).toBeUndefined();
      }
    });

    it("returns string or undefined", () => {
      const result = resolveChocoExecutable();
      expect(result === undefined || typeof result === "string").toBe(true);
    });
  });

  describe("getWindowsPackageManager", () => {
    it("returns null on non-Windows", () => {
      if (process.platform !== "win32") {
        expect(getWindowsPackageManager()).toBeNull();
      }
    });

    it("returns correct shape when available", () => {
      const result = getWindowsPackageManager();
      if (result !== null) {
        expect(result).toHaveProperty("manager");
        expect(result).toHaveProperty("path");
        expect(["winget", "choco"]).toContain(result.manager);
        expect(typeof result.path).toBe("string");
      }
    });

    it("prefers winget over choco", () => {
      // If both are available, winget should be preferred
      const result = getWindowsPackageManager();
      if (result !== null && process.platform === "win32") {
        // If winget is available, it should be chosen
        const wingetPath = resolveWingetExecutable();
        if (wingetPath) {
          expect(result.manager).toBe("winget");
        }
      }
    });
  });

  describe("buildWingetInstallCommand", () => {
    it("builds correct command for package ID", () => {
      const result = buildWingetInstallCommand("GitHub.cli");

      expect(result).toContain("winget");
      expect(result).toContain("install");
      expect(result).toContain("--id");
      expect(result).toContain("GitHub.cli");
      expect(result).toContain("--exact");
      expect(result).toContain("--accept-source-agreements");
      expect(result).toContain("--accept-package-agreements");
    });

    it("includes silent flag", () => {
      const result = buildWingetInstallCommand("test.package");
      expect(result).toContain("--silent");
    });
  });

  describe("buildChocoInstallCommand", () => {
    it("builds correct command for package name", () => {
      const result = buildChocoInstallCommand("gh");

      expect(result).toContain("choco");
      expect(result).toContain("install");
      expect(result).toContain("gh");
      expect(result).toContain("-y");
    });

    it("includes no-progress flag", () => {
      const result = buildChocoInstallCommand("test");
      expect(result).toContain("--no-progress");
    });
  });

  describe("hasWinget", () => {
    it("returns boolean", () => {
      expect(typeof hasWinget()).toBe("boolean");
    });

    it("returns false on non-Windows", () => {
      if (process.platform !== "win32") {
        expect(hasWinget()).toBe(false);
      }
    });
  });

  describe("hasChoco", () => {
    it("returns boolean", () => {
      expect(typeof hasChoco()).toBe("boolean");
    });

    it("returns false on non-Windows", () => {
      if (process.platform !== "win32") {
        expect(hasChoco()).toBe(false);
      }
    });
  });
});
