// Lets node:test import source modules the way the app does: TypeScript and TSX are transpiled
// with the repository's own TypeScript, and "@/..." resolves to src/ as in tsconfig.json.
// Usage: node --import ./tests/support/register-tsx.mjs --test tests/*.test.mjs
import { existsSync, readFileSync, statSync } from "node:fs";
import { registerHooks } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import ts from "typescript";

const srcRoot = fileURLToPath(new URL("../../src/", import.meta.url));
const candidates = ["", ".ts", ".tsx", "/index.ts", "/index.tsx"];

function sourceFile(base) {
  for (const suffix of candidates) {
    const file = base + suffix;
    if (existsSync(file) && statSync(file).isFile()) return file;
  }
  return null;
}

registerHooks({
  resolve(specifier, context, nextResolve) {
    let file = null;
    if (specifier.startsWith("@/")) {
      file = sourceFile(path.join(srcRoot, specifier.slice(2)));
    } else if (/^\.\.?\//.test(specifier) && context.parentURL?.startsWith("file:")) {
      const parent = fileURLToPath(context.parentURL);
      if (parent.startsWith(srcRoot)) file = sourceFile(path.resolve(path.dirname(parent), specifier));
    }
    return file ? { url: pathToFileURL(file).href, shortCircuit: true } : nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url.startsWith("file:") && /\.tsx?$/.test(url)) {
      const fileName = fileURLToPath(url);
      const { outputText } = ts.transpileModule(readFileSync(fileName, "utf8"), {
        fileName,
        compilerOptions: {
          jsx: ts.JsxEmit.ReactJSX,
          module: ts.ModuleKind.ESNext,
          target: ts.ScriptTarget.ES2022,
        },
      });
      return { format: "module", source: outputText, shortCircuit: true };
    }
    return nextLoad(url, context);
  },
});
