// Render the first PDF page with the frontend's PDF.js version and scale policy.
// Node canvas can rasterize fonts differently from a browser; this is not a UI test.
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const { createCanvas } = require('@napi-rs/canvas');
const pdfjs = await import(pathToFileURL(require.resolve('pdfjs-dist/legacy/build/pdf.mjs')));
const [runDir, datasetRoot] = process.argv.slice(2);
if (!runDir || !datasetRoot) throw new Error('Usage: render_pdfs.mjs RUN_DIR DATASET_ROOT');
const { cases } = JSON.parse(await fs.readFile(path.join(runDir, 'cases.json'), 'utf8'));
for (const item of cases.filter(item => item.path.endsWith('.pdf'))) {
  const target = path.join(runDir, item.id);
  await fs.mkdir(target, { recursive: true });
  const task = pdfjs.getDocument({ data: new Uint8Array(await fs.readFile(path.join(datasetRoot, item.path))) });
  const pdf = await task.promise;
  try {
    const page = await pdf.getPage(1);
    const original = page.getViewport({ scale: 1 });
    const scale = Math.min(2, 4096 / Math.max(original.width, original.height),
      Math.sqrt(8_000_000 / (original.width * original.height)));
    const viewport = page.getViewport({ scale });
    const canvas = createCanvas(Math.ceil(viewport.width), Math.ceil(viewport.height));
    await page.render({ canvasContext: canvas.getContext('2d'), canvas, viewport }).promise;
    await fs.writeFile(path.join(target, 'input.png'), canvas.toBuffer('image/png'));
    await fs.writeFile(path.join(target, 'pdf-render.json'), JSON.stringify({
      renderer: 'pdfjs-dist with @napi-rs/canvas', pdfjs: pdfjs.version,
      page: 1, pages: pdf.numPages, scale, width: canvas.width, height: canvas.height,
      originalWidth: original.width, originalHeight: original.height,
    }, null, 2));
    // Native source text is saved for later diagnosis; it is not an inference input.
    const text = await page.getTextContent();
    await fs.writeFile(path.join(target, 'source-text.json'), JSON.stringify(text.items, null, 2));
    console.log(`${item.id}: ${canvas.width} x ${canvas.height}, ${text.items.length} text items`);
  } finally { await task.destroy(); }
}
