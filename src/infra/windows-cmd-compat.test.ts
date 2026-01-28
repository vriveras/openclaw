import { describe, expect, it } from "vitest";

import {
  translateCmdToPs,
  isCmdSyntax,
  maybeTranslateCmdToPs,
  getCmdToPsHelp,
} from "./windows-cmd-compat.js";

describe("windows-cmd-compat", () => {
  describe("translateCmdToPs", () => {
    describe("dir command", () => {
      it("translates dir /b to Get-ChildItem -Name", () => {
        expect(translateCmdToPs("dir /b")).toBe("Get-ChildItem -Name");
      });

      it("translates dir /s to Get-ChildItem -Recurse", () => {
        expect(translateCmdToPs("dir /s")).toBe("Get-ChildItem -Recurse");
      });

      it("translates dir /b /s to Get-ChildItem -Name -Recurse", () => {
        expect(translateCmdToPs("dir /b /s")).toBe("Get-ChildItem -Name -Recurse");
      });

      it("translates dir /a to Get-ChildItem -Force", () => {
        expect(translateCmdToPs("dir /a")).toBe("Get-ChildItem -Force");
      });

      it("preserves path argument", () => {
        expect(translateCmdToPs("dir /b C:\\Users")).toBe("Get-ChildItem -Name C:\\Users");
      });

      it("handles case insensitivity", () => {
        expect(translateCmdToPs("DIR /B")).toBe("Get-ChildItem -Name");
      });
    });

    describe("copy command", () => {
      it("translates copy /y to Copy-Item -Force", () => {
        expect(translateCmdToPs("copy /y src dst")).toBe("Copy-Item -Force src dst");
      });

      it("translates copy /-y to Copy-Item -Confirm", () => {
        expect(translateCmdToPs("copy /-y src dst")).toBe("Copy-Item -Confirm src dst");
      });
    });

    describe("del/erase command", () => {
      it("translates del /q to Remove-Item -Force", () => {
        expect(translateCmdToPs("del /q file.txt")).toBe("Remove-Item -Force file.txt");
      });

      it("translates del /s /q to Remove-Item -Recurse -Force", () => {
        expect(translateCmdToPs("del /s /q folder")).toBe("Remove-Item -Recurse -Force folder");
      });

      it("translates erase same as del", () => {
        expect(translateCmdToPs("erase /q file.txt")).toBe("Remove-Item -Force file.txt");
      });
    });

    describe("rd/rmdir command", () => {
      it("translates rd /s /q to Remove-Item -Recurse -Force", () => {
        expect(translateCmdToPs("rd /s /q folder")).toBe("Remove-Item -Recurse -Force folder");
      });

      it("translates rmdir same as rd", () => {
        expect(translateCmdToPs("rmdir /s /q folder")).toBe("Remove-Item -Recurse -Force folder");
      });
    });

    describe("type command", () => {
      it("translates type to Get-Content", () => {
        expect(translateCmdToPs("type file.txt")).toBe("Get-Content file.txt");
      });
    });

    describe("cls command", () => {
      it("translates cls to Clear-Host", () => {
        expect(translateCmdToPs("cls")).toBe("Clear-Host");
      });
    });

    describe("move command", () => {
      it("translates move /y to Move-Item -Force", () => {
        expect(translateCmdToPs("move /y src dst")).toBe("Move-Item -Force src dst");
      });
    });

    describe("ren/rename command", () => {
      it("translates ren to Rename-Item", () => {
        expect(translateCmdToPs("ren old.txt new.txt")).toBe("Rename-Item old.txt new.txt");
      });

      it("translates rename to Rename-Item", () => {
        expect(translateCmdToPs("rename old.txt new.txt")).toBe("Rename-Item old.txt new.txt");
      });
    });

    describe("tasklist command", () => {
      it("translates tasklist to Get-Process", () => {
        expect(translateCmdToPs("tasklist")).toBe("Get-Process");
      });
    });

    describe("taskkill command", () => {
      it("translates taskkill /f /pid to Stop-Process -Force -Id", () => {
        expect(translateCmdToPs("taskkill /f /pid 1234")).toBe("Stop-Process -Force -Id 1234");
      });

      it("translates taskkill /im to Stop-Process -Name", () => {
        expect(translateCmdToPs("taskkill /im notepad.exe")).toBe("Stop-Process -Name notepad.exe");
      });
    });

    describe("where command", () => {
      it("translates where to Get-Command", () => {
        expect(translateCmdToPs("where node")).toBe("Get-Command node");
      });
    });

    describe("set command (special handling)", () => {
      it("translates set VAR=value to $env:VAR assignment", () => {
        expect(translateCmdToPs("set PATH=C:\\bin")).toBe("set $env:PATH = 'C:\\bin'");
      });

      it("translates set VAR to $env:VAR", () => {
        expect(translateCmdToPs("set PATH")).toBe("set $env:PATH");
      });

      it("translates bare set to Get-ChildItem Env:", () => {
        expect(translateCmdToPs("set")).toBe("set Get-ChildItem Env:");
      });
    });

    describe("no translation needed", () => {
      it("returns PowerShell commands unchanged", () => {
        expect(translateCmdToPs("Get-ChildItem -Name")).toBe("Get-ChildItem -Name");
      });

      it("returns unknown commands unchanged", () => {
        expect(translateCmdToPs("mycustomtool --flag")).toBe("mycustomtool --flag");
      });

      it("returns empty string unchanged", () => {
        expect(translateCmdToPs("")).toBe("");
      });

      it("returns commands that work as aliases unchanged", () => {
        // These have no CMD switches, so no translation needed
        expect(translateCmdToPs("dir")).toBe("Get-ChildItem");
        expect(translateCmdToPs("cd ..")).toBe("cd ..");
      });
    });

    describe("quoted arguments", () => {
      it("preserves double-quoted paths", () => {
        expect(translateCmdToPs('dir /b "C:\\Program Files"')).toBe(
          'Get-ChildItem -Name "C:\\Program Files"',
        );
      });

      it("preserves single-quoted strings", () => {
        expect(translateCmdToPs("type 'my file.txt'")).toBe("Get-Content 'my file.txt'");
      });
    });
  });

  describe("isCmdSyntax", () => {
    it("returns true for dir with CMD switches", () => {
      expect(isCmdSyntax("dir /b")).toBe(true);
      expect(isCmdSyntax("dir /s /b")).toBe(true);
    });

    it("returns true for del with CMD switches", () => {
      expect(isCmdSyntax("del /q file.txt")).toBe(true);
    });

    it("returns false for PowerShell syntax", () => {
      expect(isCmdSyntax("Get-ChildItem -Name")).toBe(false);
    });

    it("returns false for commands without switches", () => {
      expect(isCmdSyntax("dir")).toBe(false);
      expect(isCmdSyntax("echo hello")).toBe(false);
    });

    it("returns false for unknown commands with slashes", () => {
      // Unknown command - not in our rules
      expect(isCmdSyntax("unknowncmd /x")).toBe(false);
    });
  });

  describe("maybeTranslateCmdToPs", () => {
    it("translates CMD syntax and reports wasTranslated=true", () => {
      const result = maybeTranslateCmdToPs("dir /b");
      expect(result.translated).toBe("Get-ChildItem -Name");
      expect(result.wasTranslated).toBe(true);
    });

    it("does not translate non-CMD syntax and reports wasTranslated=false", () => {
      const result = maybeTranslateCmdToPs("Get-ChildItem");
      expect(result.translated).toBe("Get-ChildItem");
      expect(result.wasTranslated).toBe(false);
    });

    it("does not translate commands without CMD switches", () => {
      const result = maybeTranslateCmdToPs("dir");
      expect(result.translated).toBe("dir");
      expect(result.wasTranslated).toBe(false);
    });
  });

  describe("getCmdToPsHelp", () => {
    it("returns a non-empty help string", () => {
      const help = getCmdToPsHelp();
      expect(help).toContain("CMD → PowerShell");
      expect(help).toContain("dir /b");
      expect(help).toContain("Get-ChildItem");
    });
  });
});
