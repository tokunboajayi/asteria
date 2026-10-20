import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Cesium's prebuilt runtime, copied in by scripts/copy-cesium.mjs; not our code.
    "public/cesium/**",
    // Generated from the API's OpenAPI schema by `npm run gen:types`.
    "src/lib/api-types.ts",
  ]),
]);

export default eslintConfig;
