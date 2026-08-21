// Expo's static web export does not emit PWA tags, so this runs after
// `expo export` and injects them into the generated index.html. Files under
// frontend/public/ (manifest.json, icons/) are copied into the export by Expo
// itself; this script only wires them into the document head.
//
// Usage: node scripts/inject-pwa.mjs <export-dir>

import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const exportDir = process.argv[2];
if (!exportDir) {
  console.error("usage: node scripts/inject-pwa.mjs <export-dir>");
  process.exit(1);
}

const indexPath = join(exportDir, "index.html");
let html = readFileSync(indexPath, "utf8");

if (html.includes('rel="manifest"')) {
  console.log("inject-pwa: manifest link already present, nothing to do");
  process.exit(0);
}

const tags = [
  '<link rel="manifest" href="/manifest.json"/>',
  '<meta name="theme-color" content="#6750A4"/>',
  '<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png"/>',
  // iOS reads these instead of the manifest for Add-to-Home-Screen behaviour.
  '<meta name="apple-mobile-web-app-capable" content="yes"/>',
  '<meta name="mobile-web-app-capable" content="yes"/>',
  '<meta name="apple-mobile-web-app-status-bar-style" content="default"/>',
  '<meta name="apple-mobile-web-app-title" content="Christduell"/>',
].join("");

if (!html.includes("</head>")) {
  console.error("inject-pwa: no </head> in index.html — export format changed?");
  process.exit(1);
}
html = html.replace("</head>", `${tags}</head>`);
writeFileSync(indexPath, html);
console.log(`inject-pwa: PWA tags injected into ${indexPath}`);
