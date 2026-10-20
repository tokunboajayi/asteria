// Cesium loads its web workers, widgets and assets at runtime from a URL.
// Copy them out of node_modules into public/cesium (git-ignored) so Next.js
// serves them, and the app sets window.CESIUM_BASE_URL = "/cesium".
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const source = join(web, "node_modules", "cesium", "Build", "Cesium");
const target = join(web, "public", "cesium");

if (!existsSync(source)) {
  console.error(`copy-cesium: ${source} not found; is the cesium package installed?`);
  process.exit(1);
}
rmSync(target, { recursive: true, force: true });
mkdirSync(target, { recursive: true });
for (const dir of ["Workers", "ThirdParty", "Assets", "Widgets"]) {
  cpSync(join(source, dir), join(target, dir), { recursive: true });
}
console.log(`copy-cesium: copied Cesium runtime assets to ${target}`);
