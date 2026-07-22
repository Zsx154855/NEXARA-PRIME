import tsParser from "@typescript-eslint/parser";

export default [
  {
    ignores: ["out/**", ".next/**", "node_modules/**", "next-env.d.ts"],
  },
  {
    files: ["**/*.ts", "**/*.tsx"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
        ecmaVersion: "latest",
        sourceType: "module",
      },
    },
    rules: {
      "no-unused-vars": "off",
    },
  },
];
