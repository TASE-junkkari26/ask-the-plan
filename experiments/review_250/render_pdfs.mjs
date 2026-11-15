import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const { createCanvas } = require('@napi-rs/canvas');
const pdfjs = await import(pathToFileURL(require.resolve('pdfjs-dist/legacy/build/pdf.mjs')));
const [runDirectory, datasetRoot] = process.argv.slice(2);
if (!runDirectory || !datasetRoot) throw new Error('Supply the run directory and dataset root.');
const manifest = JSON.parse(await fs.readFile(path.join(runDirectory, 'cases.json'), 'utf8'));
for (const source of manifest.assets.filter(source => source.path.endsWith('.pdf'))) {
  const target = path.join(runDirectory, 'inputs', source.id);
  await fs.mkdir(target, { recursive: true });
  const task = pdfjs.getDocument({ data: new Uint8Array(await fs.readFile(path.join(datasetRoot, source.path))) });
  const document = await task.promise;
  try {
    const page = await document.getPage(1);
    const original = page.getViewport({ scale: 1 });
    const scale = Math.min(2, 4096 / Math.max(original.width, original.height),
      Math.sqrt(8_000_000 / (original.width * original.height)));
    const viewport = page.getViewport({ scale });
    const canvas = createCanvas(Math.ceil(viewport.width), Math.ceil(viewport.height));
    await page.render({ canvasContext: canvas.getContext('2d'), canvas, viewport }).promise;
    await fs.writeFile(path.join(target, 'display.png'), canvas.toBuffer('image/png'));
    await fs.writeFile(path.join(target, 'render.json'), JSON.stringify({
      renderer: 'pdfjs-dist with @napi-rs/canvas', pdfjs: pdfjs.version, page_index: 0,
      pages: document.numPages, scale, rotation: viewport.rotation, width: canvas.width, height: canvas.height,
      viewport_transform: viewport.transform, source_bounds: page.view,
    }, null, 2));
    console.log(`${source.id} rendered ${canvas.width} x ${canvas.height}`);
  } finally {
    await task.destroy();
  }
}
