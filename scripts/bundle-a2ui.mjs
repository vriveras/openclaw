#!/usr/bin/env node
/**
 * A2UI bundler - Cross-platform (Windows + Unix)
 * Replaces bundle-a2ui.sh for Windows compatibility
 */

import { createHash } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, "..");

const HASH_FILE = path.join(ROOT_DIR, "src/canvas-host/a2ui/.bundle.hash");
const OUTPUT_FILE = path.join(ROOT_DIR, "src/canvas-host/a2ui/a2ui.bundle.js");
const A2UI_RENDERER_DIR = path.join(ROOT_DIR, "vendor/a2ui/renderers/lit");
const A2UI_APP_DIR = path.join(ROOT_DIR, "apps/shared/MoltbotKit/Tools/CanvasA2UI");

const INPUT_PATHS = [
  path.join(ROOT_DIR, "package.json"),
  path.join(ROOT_DIR, "pnpm-lock.yaml"),
  A2UI_RENDERER_DIR,
  A2UI_APP_DIR,
];

async function exists(p) {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

async function walk(entryPath) {
  const files = [];
  const st = await fs.stat(entryPath);
  if (st.isDirectory()) {
    const entries = await fs.readdir(entryPath);
    for (const entry of entries) {
      files.push(...(await walk(path.join(entryPath, entry))));
    }
  } else {
    files.push(entryPath);
  }
  return files;
}

function normalize(p) {
  return p.split(path.sep).join("/");
}

async function computeHash() {
  const files = [];
  for (const input of INPUT_PATHS) {
    if (await exists(input)) {
      files.push(...(await walk(input)));
    }
  }

  files.sort((a, b) => normalize(a).localeCompare(normalize(b)));

  const hash = createHash("sha256");
  for (const filePath of files) {
    const rel = normalize(path.relative(ROOT_DIR, filePath));
    hash.update(rel);
    hash.update("\0");
    hash.update(await fs.readFile(filePath));
    hash.update("\0");
  }

  return hash.digest("hex");
}

function runCommand(cmd, args) {
  return new Promise((resolve, reject) => {
    const isWindows = process.platform === "win32";
    const shell = isWindows ? true : false;
    
    // On Windows, use pnpm.cmd
    const actualCmd = isWindows && cmd === "pnpm" ? "pnpm.cmd" : cmd;
    
    const child = spawn(actualCmd, args, {
      stdio: "inherit",
      cwd: ROOT_DIR,
      shell,
    });

    child.on("close", (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`${cmd} ${args.join(" ")} failed with code ${code}`));
      }
    });

    child.on("error", reject);
  });
}

async function main() {
  // Docker builds exclude vendor/apps via .dockerignore.
  // In that environment we must keep the prebuilt bundle.
  if (!(await exists(A2UI_RENDERER_DIR)) || !(await exists(A2UI_APP_DIR))) {
    console.log("A2UI sources missing; keeping prebuilt bundle.");
    process.exit(0);
  }

  const currentHash = await computeHash();

  if (await exists(HASH_FILE)) {
    const previousHash = (await fs.readFile(HASH_FILE, "utf8")).trim();
    if (previousHash === currentHash && (await exists(OUTPUT_FILE))) {
      console.log("A2UI bundle up to date; skipping.");
      process.exit(0);
    }
  }

  console.log("Building A2UI bundle...");

  // Run tsc
  const tsconfigPath = path.join(A2UI_RENDERER_DIR, "tsconfig.json");
  await runCommand("pnpm", ["exec", "tsc", "-p", tsconfigPath]);

  // Run rolldown
  const rolldownConfig = path.join(A2UI_APP_DIR, "rolldown.config.mjs");
  await runCommand("pnpm", ["exec", "rolldown", "-c", rolldownConfig]);

  // Write hash
  await fs.writeFile(HASH_FILE, currentHash, "utf8");

  console.log("A2UI bundle created.");
}

main().catch((err) => {
  console.error("A2UI bundling failed. Re-run with: pnpm canvas:a2ui:bundle");
  console.error("If this persists, verify pnpm deps and try again.");
  console.error(err.message);
  process.exit(1);
});
