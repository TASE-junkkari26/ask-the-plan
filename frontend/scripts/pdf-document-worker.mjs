// Server-owned PDF.js text extraction. One JSON request on stdin; one JSON response.
// Filesystem paths are supplied only by document_engine's registered-source bridge.
import fs from 'node:fs/promises';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const MAX_SOURCE_BYTES = 64 * 1024 * 1024;
const MAX_OUTPUT_BYTES = 8 * 1024 * 1024;
const MAX_ITEMS = 100000;
const require = createRequire(new URL('../package.json', import.meta.url));
// PDF.js diagnostics must never corrupt the typed stdout protocol.
console.log = () => {};
console.warn = () => {};
console.error = () => {};

function fail(code, message) {
  const error = new Error(message);
  error.code = code;
  throw error;
}
const finiteArray = (value, size) => Array.isArray(value) && value.length === size && value.every(Number.isFinite);
const closeArray = (a, b) => finiteArray(a, b.length) && a.every((value, index) => Math.abs(value - b[index]) <= 1e-6 * Math.max(1, Math.abs(b[index])));
function point(matrix, x, y) {
  return [matrix[0] * x + matrix[2] * y + matrix[4], matrix[1] * x + matrix[3] * y + matrix[5]];
}

let task;
try {
  let requestText = '';
  for await (const chunk of process.stdin) {
    requestText += chunk;
    if (requestText.length > 16384) fail('invalid_worker_request', 'The PDF worker request exceeds its limit.');
  }
  const request = JSON.parse(requestText);
  const { source_path: sourcePath, snapshot } = request;
  if (typeof sourcePath !== 'string' || !snapshot || !Number.isInteger(snapshot.page_index) || snapshot.page_index < 0) {
    fail('invalid_worker_request', 'The PDF worker needs a registered source and page index.');
  }
  const stat = await fs.stat(sourcePath);
  if (!stat.isFile() || !stat.size || stat.size > MAX_SOURCE_BYTES) fail('source_size_limit', 'The PDF source exceeds the byte limit.');
  const pdfjs = await import(pathToFileURL(require.resolve('pdfjs-dist/legacy/build/pdf.mjs')));
  task = pdfjs.getDocument({ data: new Uint8Array(await fs.readFile(sourcePath)),
    isEvalSupported: false, disableFontFace: true, useSystemFonts: false, useWorkerFetch: false,
    disableAutoFetch: true, disableStream: true, verbosity: 0 });
  const pdf = await task.promise;
  if (snapshot.page_index >= pdf.numPages) fail('invalid_page', 'The selected PDF page is absent from this original.');
  const page = await pdf.getPage(snapshot.page_index + 1);
  const rotation = snapshot.rotation ?? page.rotate;
  if (!Number.isInteger(rotation) || rotation % 90) fail('invalid_snapshot', 'PDF rotation must be a multiple of 90 degrees.');
  const original = page.getViewport({ scale: 1, rotation });
  const supplied = snapshot.viewport_transform;
  let scale = null;
  let viewport = null;
  if (supplied != null) {
    if (!finiteArray(supplied, 6)) fail('invalid_snapshot', 'The PDF viewport transform is invalid.');
    scale = Math.hypot(supplied[0], supplied[1]) / Math.hypot(original.transform[0], original.transform[1]);
    if (!(scale > 0) || !Number.isFinite(scale) || scale > 1000) fail('invalid_snapshot', 'The PDF viewport scale is invalid.');
    viewport = page.getViewport({ scale, rotation });
    if (!closeArray(supplied, viewport.transform)) fail('mapping_mismatch', 'The display transform does not match the original PDF page.');
    if (Math.ceil(viewport.width) !== snapshot.display_width || Math.ceil(viewport.height) !== snapshot.display_height) {
      fail('mapping_mismatch', 'The displayed raster dimensions do not match the PDF viewport.');
    }
    if (!closeArray(snapshot.source_bounds, page.view)) fail('mapping_mismatch', 'The source bounds do not match the original PDF CropBox.');
  }
  const content = await page.getTextContent({ disableNormalization: true, includeMarkedContent: false });
  if (content.items.length > MAX_ITEMS) fail('native_extraction_limit', 'The PDF page exceeds the native text-item limit; extraction is incomplete.');
  const spans = [];
  let unresolved = 0;
  for (let index = 0; index < content.items.length; index++) {
    const item = content.items[index];
    if (typeof item.str !== 'string' || !item.str.trim()) continue;
    if (!finiteArray(item.transform, 6) || !Number.isFinite(item.width) || !Number.isFinite(item.height)) {
      unresolved++;
      continue;
    }
    const native = item.transform;
    const font = content.styles[item.fontName] ?? {};
    const ascent = Number.isFinite(font.ascent) ? font.ascent : Number.isFinite(font.descent) ? 1 + font.descent : 0.8;
    const fontHeight = Math.hypot(native[2], native[3]);
    const baselineWidth = Math.hypot(native[0], native[1]);
    const ux = baselineWidth ? native[0] / baselineWidth : 1;
    const uy = baselineWidth ? native[1] / baselineWidth : 0;
    const vx = fontHeight ? native[2] / fontHeight : 0;
    const vy = fontHeight ? native[3] / fontHeight : 1;
    const height = item.height || fontHeight;
    const quad = [
      [native[4] + vx * height * (ascent - 1), native[5] + vy * height * (ascent - 1)],
      [native[4] + ux * item.width + vx * height * (ascent - 1), native[5] + uy * item.width + vy * height * (ascent - 1)],
      [native[4] + ux * item.width + vx * height * ascent, native[5] + uy * item.width + vy * height * ascent],
      [native[4] + vx * height * ascent, native[5] + vy * height * ascent],
    ];
    const displayQuad = viewport ? quad.map(p => point(viewport.transform, ...p)) : null;
    const bbox = displayQuad ? [Math.min(...displayQuad.map(p => p[0])), Math.min(...displayQuad.map(p => p[1])),
      Math.max(...displayQuad.map(p => p[0])), Math.max(...displayQuad.map(p => p[1]))] : null;
    const displayMatrix = viewport ? pdfjs.Util.transform(viewport.transform, native) : null;
    spans.push({ id: `pdf:p${snapshot.page_index}:text${index}`, text: item.str,
      native_transform: native, native_quad: quad, display_transform: displayMatrix,
      display_bbox: bbox, width: item.width, height: item.height, has_eol: !!item.hasEOL,
      direction: item.dir, font_name: item.fontName, vertical: !!font.vertical,
      bbox_quality: 'font_metrics_estimate' });
  }
  const response = { version: 'pdfjs-native-v1', pdfjs_version: pdfjs.version,
    page_index: snapshot.page_index, page_count: pdf.numPages, page_rotation: page.rotate,
    rotation, source_bounds: page.view, native_user_unit: page.userUnit,
    viewport_transform: viewport?.transform ?? null, display_width: snapshot.display_width,
    display_height: snapshot.display_height, mapping_verified: !!viewport,
    text_enumeration_complete: unresolved === 0, unresolved_items: unresolved, spans,
    warnings: [
      ...(!viewport ? ['No verified PDF-to-display mapping was supplied; anchors remain in native PDF coordinates.'] : []),
      ...(unresolved ? ['Some native text items could not be represented; text enumeration is incomplete.'] : []),
      'Native text enumeration does not establish table reconstruction, depicted-object completeness or text correctness.',
      'Text bounding boxes use source font metrics and may differ from exact glyph outlines.',
    ] };
  const output = JSON.stringify(response);
  if (Buffer.byteLength(output, 'utf8') > MAX_OUTPUT_BYTES) fail('native_output_limit', 'The PDF native extraction exceeds the output limit.');
  process.stdout.write(output);
} catch (error) {
  const known = new Set(['invalid_worker_request', 'source_size_limit', 'invalid_page', 'invalid_snapshot',
    'mapping_mismatch', 'native_extraction_limit', 'native_output_limit']);
  process.stdout.write(JSON.stringify({ error: { code: known.has(error.code) ? error.code : 'native_extraction_failed',
    message: known.has(error.code) ? error.message : 'The registered PDF could not be extracted by the local PDF.js worker.' } }));
  process.exitCode = 1;
} finally {
  if (task) await task.destroy();
}
