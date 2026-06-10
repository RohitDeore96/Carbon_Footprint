/// <reference types="vitest/config" />
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Vite plugin that replaces `Function('return this')()` and Zod's CSP probe
 * with CSP-safe alternatives in the production bundle.
 *
 * Two patterns are handled:
 * 1. `Function('return this')()` → `globalThis`
 *    Used by decimal.js-light (recharts), Firebase SDK, and others as a
 *    fallback to access the global object. In modern browsers `globalThis` is
 *    always available, so this is dead code — but its presence triggers CSP
 *    violations under `script-src 'self'` (without `'unsafe-eval'`).
 *
 * 2. `Function(\`\`)` (Zod's CSP probe) → `undefined`
 *    Zod v4 calls `new Function("")` inside a try/catch to detect whether
 *    eval is allowed. Even though the error is caught, the browser still
 *    fires a `securitypolicyviolation` event. We replace the probe so it
 *    never reaches the Function constructor, and set `jitless: true` at
 *    runtime via the `__zod_globalConfig` global.
 */
function replaceFunctionReturnThis(): Plugin {
  return {
    name: 'replace-function-return-this',
    enforce: 'post',
    generateBundle(_, bundle) {
      // Pattern 1: Function(`return this`)() and variants → globalThis
      const globalThisPattern = /Function\s*\(\s*[`"']return this[`"']\s*\)\s*\(\s*\)/g;

      // Pattern 2: Zod's allowsEval probe — new F("") where F = Function
      // The bundled form is: Function(``),!0}catch{return!1}
      // We replace the entire try block result with `false` so Zod thinks eval is unavailable
      const zodProbePattern = /Function\s*\(\s*`\s*`\s*\)\s*,\s*!0\s*\}\s*catch\s*\{\s*return\s*!1\s*\}/g;

      for (const chunk of Object.values(bundle)) {
        if (chunk.type === 'chunk' && chunk.fileName.endsWith('.js')) {
          const original = chunk.code;
          let replaced = original.replace(globalThisPattern, 'globalThis');
          replaced = replaced.replace(zodProbePattern, 'false}catch{return!1}');

          if (original !== replaced) {
            const gCount = (original.match(globalThisPattern) || []).length;
            const zCount = (original.match(zodProbePattern) || []).length;
            if (gCount) console.log(
              `[csp-fix] Replaced ${gCount} Function("return this")() → globalThis in ${chunk.fileName}`
            );
            if (zCount) console.log(
              `[csp-fix] Replaced ${zCount} Zod CSP probe → false in ${chunk.fileName}`
            );
            chunk.code = replaced;
          }
        }
      }
    },
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), replaceFunctionReturnThis()],
  build: {
    // Target modern browsers that support globalThis (eliminates need for Function fallback)
    target: 'es2020',
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
    },
  },
})
