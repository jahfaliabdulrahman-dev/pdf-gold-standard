// pdf.js as a READER, not a fixer: whatever `getTextContent()` gives, with `hasEOL` to rebuild the lines.
// No BiDi normalisation, no reordering, no trimming of Arabic — a reader that repairs cannot be measured
// against the others, and this one is here to be measured.
//
// Usage: node pdfjs_text.mjs <path> [<path> ...]
// Output: {"version": "6.5.438", "pages": {path: [[line, ...], ...]}, "texts": {path: "..."}}
//
// One process for the whole batch (the same shape as `pdfkit_text.swift`): pdf.js keeps font caches between
// documents, so a per-file process would pay for the same parse twice.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const pkg = JSON.parse(readFileSync(join(here, "node_modules/pdfjs-dist/package.json"), "utf8"));

// The legacy build runs on Node without a DOM; the modern one expects browser globals.
const pdfjs = await import("./node_modules/pdfjs-dist/legacy/build/pdf.mjs");

const pages = {};
const texts = {};

for (const path of process.argv.slice(2)) {
  const data = new Uint8Array(readFileSync(path));
  const doc = await pdfjs.getDocument({
    data,
    useSystemFonts: true,
    isEvalSupported: false,       // a reader of untrusted files must not eval
    disableFontFace: true,
    verbosity: 0,
  }).promise;
  const perPage = [];
  for (let n = 1; n <= doc.numPages; n++) {
    const page = await doc.getPage(n);
    const content = await page.getTextContent();
    let line = "";
    const lines = [];
    for (const item of content.items) {
      if (typeof item.str !== "string") continue;      // marked-content markers carry no text
      line += item.str;
      if (item.hasEOL) {
        lines.push(line);
        line = "";
      }
    }
    if (line !== "") lines.push(line);
    perPage.push(lines);
    page.cleanup();
  }
  await doc.cleanup();              // pdf.js v6: `destroy` moved off the document proxy; cleanup frees the pages
  pages[path] = perPage;
  texts[path] = perPage.map((l) => l.join("\n")).join("\n");
}

process.stdout.write(JSON.stringify({ version: pkg.version, pages, texts }));
