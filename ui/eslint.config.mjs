import { defineConfig } from "eslint";

export default defineConfig([
  {
    ignores: ["out/**", ".next/**", "node_modules/**", "next-env.d.ts"],
  },
  {
    files: ["**/*.ts", "**/*.tsx"],
    rules: {
      "no-unused-vars": "off",
      "@typescript-eslint/no-unused-vars": "warn",
    },
  },
]);
