import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import type { NextConfig } from "next";

// Settings are shared with the engine and read from the Asteria root, highest priority
// first. A blank line (as left by the .env.example template) never hides a value saved
// in a later file. Values already in the environment win. NEXT_PUBLIC_ values are fixed
// into the build, so rebuild after changing them. Values are never printed.
const ROOT = path.resolve(process.cwd(), "..");
const SETTINGS_FILES = [".env.local", ".env", "web/.env.local", "web/.env"].map((f) => path.join(ROOT, f));

function readDotenv(file: string): Record<string, string> {
  if (!existsSync(file)) return {};
  const out: Record<string, string> = {};
  for (const raw of readFileSync(file, "utf8").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const i = line.indexOf("=");
    const key = line.slice(0, i).replace(/^export\s+/, "").trim();
    let value = line.slice(i + 1).trim();
    if (value.length >= 2 && (value[0] === '"' || value[0] === "'") && value.at(-1) === value[0]) {
      value = value.slice(1, -1);
    }
    out[key] = value;
  }
  return out;
}

for (const file of SETTINGS_FILES) {
  for (const [key, value] of Object.entries(readDotenv(file))) {
    if (value && !process.env[key]) process.env[key] = value;
  }
}

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // Baseline security headers. A Content-Security-Policy is not set: Cesium needs
  // web workers, WebAssembly and tile/terrain hosts, and a policy that breaks the
  // globe is worse than none; see README "Security".
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
