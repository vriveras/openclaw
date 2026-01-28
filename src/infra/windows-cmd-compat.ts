/**
 * Windows CMD → PowerShell Compatibility Layer
 *
 * Translates common CMD-style commands and switches to PowerShell equivalents.
 * PowerShell has built-in aliases (dir, cd, copy, etc.) but the switches differ.
 *
 * This allows agents and users to use familiar CMD syntax while executing via PowerShell.
 */

/**
 * CMD switch to PowerShell parameter mapping
 */
type SwitchMapping = {
  /** CMD switch (e.g., "/b", "/s") */
  cmdSwitch: string | RegExp;
  /** PowerShell equivalent (e.g., "-Name", "-Recurse") */
  psParam: string;
  /** Optional: remove the switch entirely (handled differently) */
  remove?: boolean;
};

/**
 * Command translation rule
 */
type CommandRule = {
  /** CMD command pattern (case-insensitive) */
  pattern: RegExp;
  /** PowerShell command to use (null = keep original, let alias handle it) */
  psCommand: string | null;
  /** Switch mappings */
  switches: SwitchMapping[];
  /** Custom transformer for complex cases */
  transform?: (args: string[]) => string[];
};

/**
 * Translation rules for common CMD commands
 */
const COMMAND_RULES: CommandRule[] = [
  // dir → Get-ChildItem
  {
    pattern: /^dir$/i,
    psCommand: "Get-ChildItem",
    switches: [
      { cmdSwitch: "/b", psParam: "-Name" },
      { cmdSwitch: "/s", psParam: "-Recurse" },
      { cmdSwitch: "/a", psParam: "-Force" }, // Show hidden
      { cmdSwitch: /^\/a[dhr]*/i, psParam: "-Force" }, // /ad, /ah, /ar variants
      { cmdSwitch: "/o", psParam: "" }, // Sort - complex, ignore for now
      { cmdSwitch: "/p", psParam: "", remove: true }, // Pause - not applicable
      { cmdSwitch: "/w", psParam: "-Name" }, // Wide format ≈ names only
      { cmdSwitch: "/q", psParam: "" }, // Owner - use Get-Acl separately
    ],
  },

  // copy → Copy-Item
  {
    pattern: /^copy$/i,
    psCommand: "Copy-Item",
    switches: [
      { cmdSwitch: "/y", psParam: "-Force" },
      { cmdSwitch: "/-y", psParam: "-Confirm" },
      { cmdSwitch: "/v", psParam: "" }, // Verify - not directly available
      { cmdSwitch: "/b", psParam: "" }, // Binary - default behavior
    ],
  },

  // move → Move-Item
  {
    pattern: /^move$/i,
    psCommand: "Move-Item",
    switches: [{ cmdSwitch: "/y", psParam: "-Force" }],
  },

  // del / erase → Remove-Item
  {
    pattern: /^(del|erase)$/i,
    psCommand: "Remove-Item",
    switches: [
      { cmdSwitch: "/q", psParam: "-Force" }, // Quiet
      { cmdSwitch: "/f", psParam: "-Force" }, // Force
      { cmdSwitch: "/s", psParam: "-Recurse" },
      { cmdSwitch: "/p", psParam: "-Confirm" },
    ],
  },

  // rd / rmdir → Remove-Item
  {
    pattern: /^(rd|rmdir)$/i,
    psCommand: "Remove-Item",
    switches: [
      { cmdSwitch: "/s", psParam: "-Recurse" },
      { cmdSwitch: "/q", psParam: "-Force" },
    ],
  },

  // type → Get-Content
  {
    pattern: /^type$/i,
    psCommand: "Get-Content",
    switches: [],
  },

  // cls → Clear-Host
  {
    pattern: /^cls$/i,
    psCommand: "Clear-Host",
    switches: [],
  },

  // ren / rename → Rename-Item
  {
    pattern: /^(ren|rename)$/i,
    psCommand: "Rename-Item",
    switches: [],
  },

  // md / mkdir → New-Item -ItemType Directory
  {
    pattern: /^(md|mkdir)$/i,
    psCommand: null, // Keep mkdir - it's a function in PS
    switches: [],
    transform: (args) => {
      // mkdir in PowerShell works, but ensure -Force for nested
      if (args.length > 0 && !args.includes("-Force")) {
        return [...args, "-Force"];
      }
      return args;
    },
  },

  // echo → Write-Output (alias works, but handle special cases)
  {
    pattern: /^echo$/i,
    psCommand: null, // echo alias works
    switches: [],
  },

  // set → environment variable handling
  {
    pattern: /^set$/i,
    psCommand: null,
    switches: [],
    transform: (args) => {
      // "set VAR=value" → "$env:VAR = 'value'"
      if (args.length === 1 && args[0].includes("=")) {
        const [name, ...valueParts] = args[0].split("=");
        const value = valueParts.join("=");
        return [`$env:${name} = '${value}'`];
      }
      // "set VAR" → "$env:VAR" or "Get-ChildItem Env:VAR"
      if (args.length === 1 && !args[0].includes("=")) {
        return [`$env:${args[0]}`];
      }
      // "set" alone → "Get-ChildItem Env:"
      if (args.length === 0) {
        return ["Get-ChildItem", "Env:"];
      }
      return args;
    },
  },

  // find → Select-String (different syntax entirely)
  {
    pattern: /^find$/i,
    psCommand: "Select-String",
    switches: [
      { cmdSwitch: "/i", psParam: "-CaseSensitive:$false" },
      { cmdSwitch: "/v", psParam: "-NotMatch" },
      { cmdSwitch: "/c", psParam: "-Quiet" }, // Count vs quiet
      { cmdSwitch: "/n", psParam: "" }, // Line numbers (default in PS)
    ],
    transform: (args) => {
      // find "string" file → Select-String -Pattern "string" -Path file
      const newArgs: string[] = [];
      let pattern: string | null = null;
      let paths: string[] = [];

      for (const arg of args) {
        if (arg.startsWith('"') || arg.startsWith("'")) {
          pattern = arg;
        } else if (!arg.startsWith("-")) {
          paths.push(arg);
        } else {
          newArgs.push(arg);
        }
      }

      if (pattern) {
        newArgs.unshift("-Pattern", pattern);
      }
      if (paths.length > 0) {
        newArgs.push("-Path", ...paths);
      }

      return newArgs;
    },
  },

  // findstr → Select-String
  {
    pattern: /^findstr$/i,
    psCommand: "Select-String",
    switches: [
      { cmdSwitch: "/i", psParam: "-CaseSensitive:$false" },
      { cmdSwitch: "/v", psParam: "-NotMatch" },
      { cmdSwitch: "/r", psParam: "" }, // Regex is default in PS
      { cmdSwitch: "/s", psParam: "-Path", remove: true }, // Handled via -Path *
      { cmdSwitch: "/m", psParam: "-List" }, // Print only filename
    ],
  },

  // tasklist → Get-Process
  {
    pattern: /^tasklist$/i,
    psCommand: "Get-Process",
    switches: [
      { cmdSwitch: "/v", psParam: "" }, // Verbose - default has more info
    ],
  },

  // taskkill → Stop-Process
  {
    pattern: /^taskkill$/i,
    psCommand: "Stop-Process",
    switches: [
      { cmdSwitch: "/f", psParam: "-Force" },
      { cmdSwitch: /^\/pid$/i, psParam: "-Id" },
      { cmdSwitch: /^\/im$/i, psParam: "-Name" },
    ],
  },

  // where → Get-Command or Where-Object context-dependent
  {
    pattern: /^where$/i,
    psCommand: "Get-Command",
    switches: [],
  },

  // ipconfig → Get-NetIPConfiguration (or keep ipconfig.exe)
  {
    pattern: /^ipconfig$/i,
    psCommand: null, // ipconfig.exe works
    switches: [],
  },

  // ping → Test-Connection (or keep ping.exe)
  {
    pattern: /^ping$/i,
    psCommand: null, // ping.exe works fine
    switches: [],
  },
];

/**
 * Parse a command string into command and arguments
 */
function parseCommand(cmdLine: string): { command: string; args: string[] } {
  const tokens: string[] = [];
  let current = "";
  let inQuote = false;
  let quoteChar = "";

  for (const char of cmdLine) {
    if ((char === '"' || char === "'") && !inQuote) {
      inQuote = true;
      quoteChar = char;
      current += char;
    } else if (char === quoteChar && inQuote) {
      inQuote = false;
      current += char;
      quoteChar = "";
    } else if (char === " " && !inQuote) {
      if (current) {
        tokens.push(current);
        current = "";
      }
    } else {
      current += char;
    }
  }
  if (current) {
    tokens.push(current);
  }

  const [command = "", ...args] = tokens;
  return { command, args };
}

/**
 * Translate a single CMD switch to PowerShell parameter
 */
function translateSwitch(
  switchArg: string,
  mappings: SwitchMapping[],
): { translated: string | null; remove: boolean } {
  for (const mapping of mappings) {
    const matches =
      typeof mapping.cmdSwitch === "string"
        ? switchArg.toLowerCase() === mapping.cmdSwitch.toLowerCase()
        : mapping.cmdSwitch.test(switchArg);

    if (matches) {
      if (mapping.remove) {
        return { translated: null, remove: true };
      }
      return { translated: mapping.psParam || null, remove: !mapping.psParam };
    }
  }
  return { translated: null, remove: false };
}

/**
 * Translate a CMD command line to PowerShell equivalent
 *
 * @param cmdLine - The CMD command line to translate
 * @returns Translated PowerShell command, or original if no translation needed
 */
export function translateCmdToPs(cmdLine: string): string {
  const trimmed = cmdLine.trim();
  if (!trimmed) return trimmed;

  const { command, args } = parseCommand(trimmed);

  // Find matching rule
  const rule = COMMAND_RULES.find((r) => r.pattern.test(command));
  if (!rule) {
    // No translation rule - return as-is
    return cmdLine;
  }

  // Translate switches
  const translatedArgs: string[] = [];
  const nonSwitchArgs: string[] = [];

  for (const arg of args) {
    // CMD switches start with /
    if (arg.startsWith("/")) {
      const { translated, remove } = translateSwitch(arg, rule.switches);
      if (!remove && translated) {
        translatedArgs.push(translated);
      } else if (!remove && !translated) {
        // Unknown switch - keep as comment or warn
        // For now, skip unknown CMD switches
      }
    } else {
      nonSwitchArgs.push(arg);
    }
  }

  // Apply custom transform if present
  let finalArgs = [...translatedArgs, ...nonSwitchArgs];
  if (rule.transform) {
    finalArgs = rule.transform(finalArgs);
  }

  // Build final command
  const psCmd = rule.psCommand ?? command;
  if (finalArgs.length > 0) {
    return `${psCmd} ${finalArgs.join(" ")}`;
  }
  return psCmd;
}

/**
 * Check if a command line appears to use CMD syntax
 */
export function isCmdSyntax(cmdLine: string): boolean {
  const { command, args } = parseCommand(cmdLine.trim());

  // Check if command matches any rule
  const hasMatchingRule = COMMAND_RULES.some((r) => r.pattern.test(command));
  if (!hasMatchingRule) return false;

  // Check if any args use CMD-style switches (/)
  const hasCmdSwitches = args.some((arg) => arg.startsWith("/"));

  return hasCmdSwitches;
}

/**
 * Conditionally translate if CMD syntax detected
 */
export function maybeTranslateCmdToPs(cmdLine: string): {
  translated: string;
  wasTranslated: boolean;
} {
  if (isCmdSyntax(cmdLine)) {
    return {
      translated: translateCmdToPs(cmdLine),
      wasTranslated: true,
    };
  }
  return {
    translated: cmdLine,
    wasTranslated: false,
  };
}

/**
 * Get a help message showing CMD → PowerShell equivalents
 */
export function getCmdToPsHelp(): string {
  const lines = [
    "CMD → PowerShell Quick Reference:",
    "",
    "  dir /b          → Get-ChildItem -Name",
    "  dir /s          → Get-ChildItem -Recurse",
    "  dir /a          → Get-ChildItem -Force",
    "  copy /y         → Copy-Item -Force",
    "  del /q /s       → Remove-Item -Force -Recurse",
    "  type file       → Get-Content file",
    '  find "str" file → Select-String -Pattern "str" -Path file',
    "  tasklist        → Get-Process",
    "  taskkill /f /pid N → Stop-Process -Force -Id N",
    "  set VAR=value   → $env:VAR = 'value'",
    "  where cmd       → Get-Command cmd",
    "",
    "Note: Many CMD commands work as PowerShell aliases (dir, cd, copy, etc.)",
    "      but switches differ (/ vs -).",
  ];
  return lines.join("\n");
}
