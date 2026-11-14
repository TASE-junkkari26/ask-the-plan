import type { DxfPreviewResponse } from '../contracts/DxfPreviewResponse';
import type { ImportedDrawing } from '../types';

const MAX_SVG_BYTES = 8 * 1024 * 1024;
const connectionMessage = 'DXF preview requires the local backend. Start the Python API and try again.';

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function validatePreview(value: unknown, sha256: string, page: number): DxfPreviewResponse {
  const invalid = () => new Error('The backend returned invalid DXF preview data.');
  if (!object(value) || value.schema_version !== '0.1.0'
      || !['rendered', 'partial'].includes(String(value.status))
      || typeof value.svg !== 'string' || !value.svg.startsWith('<svg ')
      || new Blob([value.svg]).size > MAX_SVG_BYTES
      || !Array.isArray(value.layouts) || value.layouts.length < 1 || value.layouts.length > 128
      || !value.layouts.every((name) => typeof name === 'string' && name.length > 0 && name.length <= 255)
      || new Set(value.layouts).size !== value.layouts.length
      || value.page !== page || page > value.layouts.length
      || !Array.isArray(value.warnings) || value.warnings.length > 40
      || !value.warnings.every((warning) => typeof warning === 'string' && warning.length > 0 && warning.length <= 1000)
      || (value.status === 'partial' && value.warnings.length === 0)
      || !Number.isSafeInteger(value.width) || !Number.isSafeInteger(value.height)
      || (value.width as number) <= 0 || (value.height as number) <= 0
      || (value.width as number) > 4096 || (value.height as number) > 4096
      || (value.width as number) * (value.height as number) > 8_000_000
      || (value.insunits != null && (!Number.isSafeInteger(value.insunits) || (value.insunits as number) < 0)))
    throw invalid();
  if (value.source_sha256 !== sha256)
    throw new Error('The DXF preview belongs to a different source file. Import the drawing again.');
  return value as unknown as DxfPreviewResponse;
}

/** Only the local backend receives the DXF. No inference happens during import. */
export async function previewDxf(file: File, page: number, signal?: AbortSignal): Promise<ImportedDrawing> {
  signal?.throwIfAborted();
  if (!globalThis.crypto?.subtle)
    throw new Error('DXF source verification requires localhost or an HTTPS connection.');
  const bytes = await file.arrayBuffer();
  signal?.throwIfAborted();
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  signal?.throwIfAborted();
  const sha256 = Array.from(new Uint8Array(digest), (n) => n.toString(16).padStart(2, '0')).join('');
  const body = new FormData();
  body.append('file', file);
  body.append('page', String(page));
  let response: Response;
  try {
    response = await fetch('/api/dxf/preview', { method: 'POST', body, signal });
  } catch {
    signal?.throwIfAborted();
    throw new Error(connectionMessage);
  }
  signal?.throwIfAborted();
  let value: unknown;
  try {
    value = await response.json();
  } catch {
    signal?.throwIfAborted();
    throw new Error(connectionMessage);
  }
  signal?.throwIfAborted();
  if (!response.ok) {
    if (object(value) && typeof value.message === 'string' && value.message.length <= 2000)
      throw new Error(value.message);
    throw new Error(connectionMessage);
  }
  const preview = validatePreview(value, sha256, page);
  const { svg, ...metadata } = preview;
  // Render as an isolated image, using the same viewport/PNG path as other 2D sources.
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
  return { file, url, width: preview.width, height: preview.height, kind: 'dxf',
    page, pages: preview.layouts.length, dxf: metadata };
}
