import * as pdfjs from "pdfjs-dist/legacy/build/pdf.mjs";
import fs from "fs";
const doc = await pdfjs.getDocument({ data: new Uint8Array(fs.readFileSync(process.argv[2])), disableFontFace: true }).promise;
const tc = await (await doc.getPage(+process.argv[3] || 1)).getTextContent();
for (const it of tc.items.slice(0, +process.argv[4] || 20)) console.log(JSON.stringify({str: it.str, dir: it.dir, x: Math.round(it.transform[4]), y: Math.round(it.transform[5]), w: Math.round(it.width), eol: it.hasEOL}));
