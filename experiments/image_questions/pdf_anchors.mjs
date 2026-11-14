// Source-derived text anchors for the selected PDF cases. No inference or QA answers.
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const pdfjs = await import(pathToFileURL(require.resolve('pdfjs-dist/legacy/build/pdf.mjs')));
const [runDir, datasetRoot] = process.argv.slice(2);
const { cases } = JSON.parse(await fs.readFile(path.join(runDir, 'cases.json'), 'utf8'));
for (const item of cases.filter(item => item.path.endsWith('.pdf'))) {
  const task = pdfjs.getDocument({ data: new Uint8Array(await fs.readFile(path.join(datasetRoot, item.path))) });
  const pdf = await task.promise;
  try {
    const page = await pdf.getPage(1);
    const render = JSON.parse(await fs.readFile(path.join(runDir, item.id, 'pdf-render.json'), 'utf8'));
    const viewport = page.getViewport({ scale: render.scale });
    const content = await page.getTextContent();
    const anchors = content.items.filter(t => t.str.trim()).map(t => {
      const matrix = pdfjs.Util.transform(viewport.transform, t.transform);
      return { text: t.str, nativeTransform: t.transform, matrix,
        box: [matrix[4], matrix[5] - t.height * render.scale,
              matrix[4] + t.width * render.scale, matrix[5]] };
    });
    await fs.writeFile(path.join(runDir, item.id, 'native-anchors.json'), JSON.stringify(anchors, null, 2));
    console.log(`${item.id}: ${anchors.length} source text anchors`);
  } finally { await task.destroy(); }
}
