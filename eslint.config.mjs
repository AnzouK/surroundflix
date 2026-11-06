// ESLint config (flat config, ESLint 9).
//
// CI lints the built JavaScript in dist/ (run `surroundflix build` first):
// the templates are joined there (shared.js + popup.js, shared.js +
// Script.js) and the placeholders filled, so every file stands alone.
// Every rule fails CI.
import globals from "globals";

const bugRules = {
  "no-const-assign": "error",
  "no-dupe-args": "error",
  "no-dupe-else-if": "error",
  "no-dupe-keys": "error",
  "no-duplicate-case": "error",
  "no-func-assign": "error",
  "no-invalid-regexp": "error",
  "no-obj-calls": "error",
  "no-self-assign": "error",
  "no-setter-return": "error",
  "no-sparse-arrays": "error",
  "no-unreachable": "error",
  "no-unsafe-finally": "error",
  "no-unsafe-negation": "error",
  "getter-return": "error",
  "use-isnan": "error",
  "valid-typeof": "error",
};

const hygieneRules = {
  "no-undef": "error",
  // vars: "local": the top-level helpers of shared.js are a small library,
  // and each built file uses only some of them.
  "no-unused-vars": ["error", { vars: "local", args: "none", caughtErrors: "none" }],
  "no-empty": ["error", { allowEmptyCatch: true }],
  eqeqeq: ["error", "smart"],
};

// Code that runs next to Netflix's page and reads data from it: no way to
// turn a string into code or HTML.
const securityRules = {
  "no-eval": "error",
  "no-implied-eval": "error",
  "no-new-func": "error",
  "no-script-url": "error",
  "no-restricted-properties": [
    "error",
    { property: "innerHTML", message: "Use textContent or DOM nodes." },
    { property: "outerHTML", message: "Use textContent or DOM nodes." },
    { property: "insertAdjacentHTML", message: "Use DOM nodes." },
    { object: "document", property: "write", message: "Use DOM nodes." },
  ],
};

export default [
  {
    files: ["dist/**/*.js"],
    languageOptions: {
      ecmaVersion: 2020,
      sourceType: "script",
      globals: { ...globals.browser, ...globals.webextensions },
    },
    rules: { ...bugRules, ...hygieneRules, ...securityRules },
  },
];
