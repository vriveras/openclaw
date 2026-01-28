/**
 * Tests for Windows path conversion utilities.
 *
 * @module windows-paths.test
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import {
  isWslMountPath,
  isAbsoluteWindowsPath,
  isUncPath,
  wslToWindows,
  windowsToWsl,
  normalizePath,
  expandWindowsEnvVars,
  resolvePathForExec,
} from "./windows-paths.js";

describe("windows-paths", () => {
  describe("isWslMountPath", () => {
    it("should detect valid WSL mount paths", () => {
      expect(isWslMountPath("/mnt/c/Users")).toBe(true);
      expect(isWslMountPath("/mnt/d/projects")).toBe(true);
      expect(isWslMountPath("/mnt/z/")).toBe(true);
      expect(isWslMountPath("/mnt/C/Users")).toBe(true); // uppercase
      expect(isWslMountPath("/mnt/c")).toBe(true); // drive root (end of string matches)
    });

    it("should return false for non-WSL paths", () => {
      expect(isWslMountPath("/home/user")).toBe(false);
      expect(isWslMountPath("/usr/local/bin")).toBe(false);
      expect(isWslMountPath("C:\\Users")).toBe(false);
      expect(isWslMountPath("relative/path")).toBe(false);
    });

    it("should handle edge cases", () => {
      expect(isWslMountPath("")).toBe(false);
      expect(isWslMountPath(null)).toBe(false);
      expect(isWslMountPath(undefined)).toBe(false);
      expect(isWslMountPath("/mnt/")).toBe(false); // no drive letter
      expect(isWslMountPath("/mnt/cc/")).toBe(false); // two-letter drive
    });
  });

  describe("isAbsoluteWindowsPath", () => {
    it("should detect valid Windows paths with backslashes", () => {
      expect(isAbsoluteWindowsPath("C:\\Users")).toBe(true);
      expect(isAbsoluteWindowsPath("D:\\projects\\foo")).toBe(true);
      expect(isAbsoluteWindowsPath("Z:\\")).toBe(true);
    });

    it("should detect valid Windows paths with forward slashes", () => {
      expect(isAbsoluteWindowsPath("C:/Users")).toBe(true);
      expect(isAbsoluteWindowsPath("D:/projects/foo")).toBe(true);
      expect(isAbsoluteWindowsPath("z:/")).toBe(true);
    });

    it("should return false for non-Windows paths", () => {
      expect(isAbsoluteWindowsPath("/mnt/c/Users")).toBe(false);
      expect(isAbsoluteWindowsPath("/home/user")).toBe(false);
      expect(isAbsoluteWindowsPath("relative\\path")).toBe(false);
      expect(isAbsoluteWindowsPath("C:file.txt")).toBe(false); // no slash after colon
    });

    it("should handle edge cases", () => {
      expect(isAbsoluteWindowsPath("")).toBe(false);
      expect(isAbsoluteWindowsPath(null)).toBe(false);
      expect(isAbsoluteWindowsPath(undefined)).toBe(false);
    });
  });

  describe("isUncPath", () => {
    it("should detect valid UNC paths with backslashes", () => {
      expect(isUncPath("\\\\server\\share")).toBe(true);
      expect(isUncPath("\\\\server\\share\\folder")).toBe(true);
      expect(isUncPath("\\\\192.168.1.1\\folder")).toBe(true);
    });

    it("should detect valid UNC paths with forward slashes", () => {
      expect(isUncPath("//server/share")).toBe(true);
      expect(isUncPath("//server/share/folder")).toBe(true);
    });

    it("should return false for non-UNC paths", () => {
      expect(isUncPath("C:\\Users")).toBe(false);
      expect(isUncPath("/mnt/c/Users")).toBe(false);
      expect(isUncPath("\\server")).toBe(false); // only one backslash
      expect(isUncPath("\\\\server")).toBe(false); // no share
    });

    it("should handle edge cases", () => {
      expect(isUncPath("")).toBe(false);
      expect(isUncPath(null)).toBe(false);
      expect(isUncPath(undefined)).toBe(false);
    });
  });

  describe("wslToWindows", () => {
    it("should convert WSL mount paths to Windows paths", () => {
      expect(wslToWindows("/mnt/c/Users/foo")).toBe("C:\\Users\\foo");
      expect(wslToWindows("/mnt/d/projects")).toBe("D:\\projects");
      expect(wslToWindows("/mnt/z/deep/nested/path")).toBe("Z:\\deep\\nested\\path");
    });

    it("should handle drive root paths", () => {
      expect(wslToWindows("/mnt/c/")).toBe("C:\\");
      expect(wslToWindows("/mnt/c")).toBe("C:\\"); // drive root without trailing slash
    });

    it("should preserve non-WSL paths", () => {
      expect(wslToWindows("/home/user")).toBe("/home/user");
      expect(wslToWindows("/usr/local/bin")).toBe("/usr/local/bin");
      expect(wslToWindows("C:\\Users")).toBe("C:\\Users");
      expect(wslToWindows("relative/path")).toBe("relative/path");
    });

    it("should handle edge cases", () => {
      expect(wslToWindows("")).toBe("");
      expect(wslToWindows(null)).toBe("");
      expect(wslToWindows(undefined)).toBe("");
    });

    it("should uppercase drive letters", () => {
      expect(wslToWindows("/mnt/c/Users")).toBe("C:\\Users");
      expect(wslToWindows("/mnt/C/Users")).toBe("C:\\Users");
    });
  });

  describe("windowsToWsl", () => {
    it("should convert Windows paths to WSL mount paths", () => {
      expect(windowsToWsl("C:\\Users\\foo")).toBe("/mnt/c/Users/foo");
      expect(windowsToWsl("D:/projects")).toBe("/mnt/d/projects");
      expect(windowsToWsl("Z:\\deep\\nested\\path")).toBe("/mnt/z/deep/nested/path");
    });

    it("should handle drive root paths", () => {
      expect(windowsToWsl("C:\\")).toBe("/mnt/c");
      expect(windowsToWsl("D:/")).toBe("/mnt/d");
    });

    it("should preserve non-Windows paths", () => {
      expect(windowsToWsl("/mnt/c/Users")).toBe("/mnt/c/Users");
      expect(windowsToWsl("/home/user")).toBe("/home/user");
      expect(windowsToWsl("relative/path")).toBe("relative/path");
    });

    it("should handle edge cases", () => {
      expect(windowsToWsl("")).toBe("");
      expect(windowsToWsl(null)).toBe("");
      expect(windowsToWsl(undefined)).toBe("");
    });

    it("should lowercase drive letters", () => {
      expect(windowsToWsl("C:\\Users")).toBe("/mnt/c/Users");
      expect(windowsToWsl("c:\\Users")).toBe("/mnt/c/Users");
    });

    it("should handle mixed slashes", () => {
      expect(windowsToWsl("C:\\Users/Documents\\file")).toBe("/mnt/c/Users/Documents/file");
    });
  });

  describe("normalizePath", () => {
    describe("for windows platform", () => {
      it("should convert forward slashes to backslashes", () => {
        expect(normalizePath("/mnt/c/Users/foo", "windows")).toBe("\\mnt\\c\\Users\\foo");
        expect(normalizePath("C:/Users/foo", "windows")).toBe("C:\\Users\\foo");
      });

      it("should preserve existing backslashes", () => {
        expect(normalizePath("C:\\Users\\foo", "windows")).toBe("C:\\Users\\foo");
      });

      it("should handle mixed slashes", () => {
        expect(normalizePath("C:/Users\\foo/bar", "windows")).toBe("C:\\Users\\foo\\bar");
      });
    });

    describe("for unix platform", () => {
      it("should convert backslashes to forward slashes", () => {
        expect(normalizePath("C:\\Users\\foo", "unix")).toBe("C:/Users/foo");
        expect(normalizePath("\\\\server\\share", "unix")).toBe("//server/share");
      });

      it("should preserve existing forward slashes", () => {
        expect(normalizePath("/mnt/c/Users/foo", "unix")).toBe("/mnt/c/Users/foo");
      });

      it("should handle mixed slashes", () => {
        expect(normalizePath("C:\\Users/foo\\bar", "unix")).toBe("C:/Users/foo/bar");
      });
    });

    it("should handle edge cases", () => {
      expect(normalizePath("", "windows")).toBe("");
      expect(normalizePath("", "unix")).toBe("");
      expect(normalizePath(null, "windows")).toBe("");
      expect(normalizePath(null, "unix")).toBe("");
      expect(normalizePath(undefined, "windows")).toBe("");
      expect(normalizePath(undefined, "unix")).toBe("");
    });
  });

  describe("expandWindowsEnvVars", () => {
    const mockEnv: Record<string, string | undefined> = {
      USERPROFILE: "C:\\Users\\testuser",
      TEMP: "C:\\Users\\testuser\\AppData\\Local\\Temp",
      HOME: "/home/testuser",
      EMPTY_VAR: "",
    };

    it("should expand known environment variables", () => {
      expect(expandWindowsEnvVars("%USERPROFILE%\\Documents", mockEnv)).toBe(
        "C:\\Users\\testuser\\Documents",
      );
      expect(expandWindowsEnvVars("%TEMP%\\file.txt", mockEnv)).toBe(
        "C:\\Users\\testuser\\AppData\\Local\\Temp\\file.txt",
      );
    });

    it("should expand multiple variables in one path", () => {
      expect(expandWindowsEnvVars("%USERPROFILE%\\%TEMP%", mockEnv)).toBe(
        "C:\\Users\\testuser\\C:\\Users\\testuser\\AppData\\Local\\Temp",
      );
    });

    it("should be case-insensitive for variable names", () => {
      expect(expandWindowsEnvVars("%userprofile%\\Documents", mockEnv)).toBe(
        "C:\\Users\\testuser\\Documents",
      );
      expect(expandWindowsEnvVars("%UserProfile%\\Documents", mockEnv)).toBe(
        "C:\\Users\\testuser\\Documents",
      );
    });

    it("should preserve unknown variables", () => {
      expect(expandWindowsEnvVars("%UNKNOWN_VAR%\\path", mockEnv)).toBe("%UNKNOWN_VAR%\\path");
    });

    it("should handle paths without variables", () => {
      expect(expandWindowsEnvVars("C:\\Users\\foo", mockEnv)).toBe("C:\\Users\\foo");
      expect(expandWindowsEnvVars("no-vars-here", mockEnv)).toBe("no-vars-here");
    });

    it("should handle empty variable values", () => {
      expect(expandWindowsEnvVars("%EMPTY_VAR%\\path", mockEnv)).toBe("\\path");
    });

    it("should handle edge cases", () => {
      expect(expandWindowsEnvVars("", mockEnv)).toBe("");
      expect(expandWindowsEnvVars(null, mockEnv)).toBe("");
      expect(expandWindowsEnvVars(undefined, mockEnv)).toBe("");
    });

    it("should use process.env by default when no env provided", () => {
      // This test verifies the default behavior
      const result = expandWindowsEnvVars("no-vars");
      expect(result).toBe("no-vars");
    });
  });

  describe("resolvePathForExec", () => {
    const mockEnv: Record<string, string | undefined> = {
      USERPROFILE: "C:\\Users\\testuser",
      TEMP: "C:\\Temp",
    };

    describe("targeting windows", () => {
      it("should convert WSL paths to Windows paths", () => {
        expect(resolvePathForExec("/mnt/c/Users/foo", { targetPlatform: "windows" })).toBe(
          "C:\\Users\\foo",
        );
        expect(resolvePathForExec("/mnt/d/projects", { targetPlatform: "windows" })).toBe(
          "D:\\projects",
        );
      });

      it("should normalize existing Windows paths", () => {
        expect(resolvePathForExec("C:/Users/foo", { targetPlatform: "windows" })).toBe(
          "C:\\Users\\foo",
        );
      });

      it("should normalize Unix-style paths", () => {
        expect(resolvePathForExec("/home/user/file", { targetPlatform: "windows" })).toBe(
          "\\home\\user\\file",
        );
      });

      it("should expand environment variables when requested", () => {
        expect(
          resolvePathForExec("%USERPROFILE%\\Documents", {
            targetPlatform: "windows",
            expandEnvVars: true,
            env: mockEnv,
          }),
        ).toBe("C:\\Users\\testuser\\Documents");
      });

      it("should not expand environment variables by default", () => {
        expect(
          resolvePathForExec("%USERPROFILE%\\Documents", {
            targetPlatform: "windows",
            env: mockEnv,
          }),
        ).toBe("%USERPROFILE%\\Documents");
      });
    });

    describe("targeting unix", () => {
      it("should convert Windows paths to WSL paths", () => {
        expect(resolvePathForExec("C:\\Users\\foo", { targetPlatform: "unix" })).toBe(
          "/mnt/c/Users/foo",
        );
        expect(resolvePathForExec("D:/projects", { targetPlatform: "unix" })).toBe(
          "/mnt/d/projects",
        );
      });

      it("should normalize existing Unix paths", () => {
        expect(resolvePathForExec("/home/user/file", { targetPlatform: "unix" })).toBe(
          "/home/user/file",
        );
      });

      it("should normalize mixed-slash paths", () => {
        expect(resolvePathForExec("/home\\user/file", { targetPlatform: "unix" })).toBe(
          "/home/user/file",
        );
      });

      it("should expand environment variables before conversion", () => {
        expect(
          resolvePathForExec("%USERPROFILE%\\Documents", {
            targetPlatform: "unix",
            expandEnvVars: true,
            env: mockEnv,
          }),
        ).toBe("/mnt/c/Users/testuser/Documents");
      });
    });

    it("should handle edge cases", () => {
      expect(resolvePathForExec("", { targetPlatform: "windows" })).toBe("");
      expect(resolvePathForExec("", { targetPlatform: "unix" })).toBe("");
      expect(resolvePathForExec(null, { targetPlatform: "windows" })).toBe("");
      expect(resolvePathForExec(null, { targetPlatform: "unix" })).toBe("");
      expect(resolvePathForExec(undefined, { targetPlatform: "windows" })).toBe("");
      expect(resolvePathForExec(undefined, { targetPlatform: "unix" })).toBe("");
    });

    it("should preserve relative paths", () => {
      expect(resolvePathForExec("relative/path", { targetPlatform: "windows" })).toBe(
        "relative\\path",
      );
      expect(resolvePathForExec("relative\\path", { targetPlatform: "unix" })).toBe(
        "relative/path",
      );
    });
  });

  describe("round-trip conversions", () => {
    it("should round-trip WSL → Windows → WSL", () => {
      const original = "/mnt/c/Users/foo/bar";
      const windows = wslToWindows(original);
      const backToWsl = windowsToWsl(windows);
      expect(backToWsl).toBe(original);
    });

    it("should round-trip Windows → WSL → Windows", () => {
      const original = "C:\\Users\\foo\\bar";
      const wsl = windowsToWsl(original);
      const backToWindows = wslToWindows(wsl);
      expect(backToWindows).toBe(original);
    });

    it("should round-trip with resolvePathForExec", () => {
      const wslPath = "/mnt/c/Users/foo";
      const windows = resolvePathForExec(wslPath, { targetPlatform: "windows" });
      const backToUnix = resolvePathForExec(windows, { targetPlatform: "unix" });
      expect(backToUnix).toBe(wslPath);
    });
  });
});
