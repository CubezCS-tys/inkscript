// print pdf.js (Firefox) text per page as JSON: [{page, text}]
import * as pdfjs from "pdfjs-dist/legacy/build/pdf.mjs";
import fs from "fs";
const data = new Uint8Array(fs.readFileSync(process.argv[2]));
const doc = await pdfjs.getDocument({ data, useSystemFonts: false, disableFontFace: true }).promise;
const out = [];
for (let p = 1; p <= doc.numPages; p++) {
  const tc = await (await doc.getPage(p)).getTextContent();
  let s = "";
  for (const it of tc.items) { s += it.str; if (it.hasEOL) s += "\n"; }
  out.push({ page: p, text: s });
}
console.log(JSON.stringify(out));
