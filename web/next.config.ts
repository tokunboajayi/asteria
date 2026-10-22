import path from "node:path";

import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// The one settings file lives at the Asteria root (../.env.local), shared with the engine.
// Loaded before Next reads web/.env*, so a value there wins; NEXT_PUBLIC_ values are
// fixed into the build, so rebuild after changing them.
loadEnvConfig(path.resolve(process.cwd(), ".."));

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
