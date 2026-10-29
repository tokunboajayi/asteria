// Run the UI acceptance suite in ../gan-harness/acceptance with this package's
// node_modules on NODE_PATH, so the specs (which live outside web/) can import
// @playwright/test. Works the same on Windows, macOS and Linux.
import { spawnSync } from "node:child_process";
import { delimiter, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { existsSync } from "node:fs";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const modules = join(web, "node_modules");
const defaultChrome = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const chromeExec = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (existsSync(defaultChrome) ? defaultChrome : undefined);
const env = {
  ...process.env,
  NODE_PATH: [modules, process.env.NODE_PATH].filter(Boolean).join(delimiter),
  ...(chromeExec ? { PLAYWRIGHT_CHROMIUM_EXECUTABLE: chromeExec } : {}),
};
const cli = join(modules, "@playwright", "test", "cli.js");
const result = spawnSync(
  process.execPath,
  [cli, "test", "-c", join(web, "..", "gan-harness", "acceptance"), ...process.argv.slice(2)],
  { stdio: "inherit", env, cwd: web },
);
process.exit(result.status ?? 1);
