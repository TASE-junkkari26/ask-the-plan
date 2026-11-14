import type { ImageCandidateResponse } from '../contracts/ImageCandidateResponse';
import type { ImportedDrawing } from '../types';

const MAX_IMAGE_BYTES = 20 * 1024 * 1024;
const MAX_IMAGE_PIXELS = 40_000_000;

/** The exact white-background snapshot uploaded and displayed during analysis. */
export interface PreparedCandidateImage {
  blob: Blob;
  sha256: string;
  width: number;
  height: number;
}

function aborted(signal?: AbortSignal) {
  signal?.throwIfAborted();
}

function abortError() {
  return new DOMException('Candidate analysis cancelled.', 'AbortError');
}

async function loadImage(url: string, signal?: AbortSignal): Promise<HTMLImageElement> {
  aborted(signal);
  const image = new Image();
  await new Promise<void>((resolve, reject) => {
    let finished = false;
    const finish = (error?: unknown) => {
      if (finished) return;
      finished = true;
      image.onload = image.onerror = null;
      signal?.removeEventListener('abort', abort);
      if (error) reject(error);
      else resolve();
    };
    const abort = () => {
      finish(abortError());
      image.src = '';
    };
    image.onload = () => finish();
    image.onerror = () => finish(new Error('The displayed drawing could not be prepared for analysis.'));
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) abort();
    else image.src = url;
  });
  aborted(signal);
  return image;
}

async function pngBlob(canvas: HTMLCanvasElement, signal?: AbortSignal): Promise<Blob> {
  aborted(signal);
  return new Promise<Blob>((resolve, reject) => {
    let finished = false;
    const finish = (blob?: Blob | null, error?: unknown) => {
      if (finished) return;
      finished = true;
      signal?.removeEventListener('abort', abort);
      if (error) reject(error);
      else if (blob) resolve(blob);
      else reject(new Error('The displayed drawing could not be converted to PNG.'));
    };
    const abort = () => finish(undefined, abortError());
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) abort();
    else {
      try {
        canvas.toBlob((blob) => finish(blob), 'image/png');
      } catch {
        finish(undefined, new Error('This drawing cannot be rasterized. Try importing a local PNG or PDF.'));
      }
    }
  });
}

/** Rasterize the selected image or already-rendered PDF page, with no resizing. */
export async function prepareCandidateImage(
  drawing: ImportedDrawing,
  signal?: AbortSignal,
): Promise<PreparedCandidateImage> {
  aborted(signal);
  const { width, height } = drawing;
  if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height) || width <= 0 || height <= 0)
    throw new Error('The drawing has invalid display dimensions.');
  if (width * height > MAX_IMAGE_PIXELS)
    throw new Error('This view exceeds the 40 megapixel analysis limit. Import a smaller image.');
  const image = await loadImage(drawing.url, signal);
  const canvas = document.createElement('canvas');
  try {
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Canvas rendering is unavailable.');
    aborted(signal);
    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, width, height);
    context.drawImage(image, 0, 0, width, height);
    const blob = await pngBlob(canvas, signal);
    aborted(signal);
    if (blob.size > MAX_IMAGE_BYTES)
      throw new Error('The rendered PNG exceeds the 20 MiB analysis limit. Import a smaller image.');
    if (!globalThis.crypto?.subtle)
      throw new Error('Image verification requires localhost or an HTTPS connection.');
    const bytes = await blob.arrayBuffer();
    aborted(signal);
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    aborted(signal);
    const sha256 = Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, '0')).join('');
    return { blob, sha256, width, height };
  } finally {
    image.src = '';
    canvas.width = canvas.height = 0;
  }
}

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function text(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}
function finite(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}
function coordinatePair(value: unknown): value is [number, number] {
  return Array.isArray(value) && value.length === 2 && value.every(finite);
}
function hash(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
}
function optionalTokens(value: unknown) {
  return value === undefined || value === null || (Number.isSafeInteger(value) && (value as number) >= 0);
}

/** Check the wire boundary before attaching server regions to a local source. */
function validateResponse(value: unknown, submitted: PreparedCandidateImage): ImageCandidateResponse {
  const invalid = () => new Error('The analysis service returned invalid candidate data. Please try again.');
  if (!object(value) || value.schema_version !== '0.1.0' || value.scope !== 'submitted_image'
      || value.inventory_completeness !== 'unverified' || !text(value.request_id)
      || !object(value.image) || value.image.coordinate_system !== 'display_pixels_top_left'
      || !hash(value.image.sha256) || !hash(value.image.inference_sha256)) throw invalid();
  if (value.image.sha256 !== submitted.sha256 || value.image.width !== submitted.width
      || value.image.height !== submitted.height)
    throw new Error('The returned candidates belong to a different image or coordinate frame. Please ask again.');
  const candidates = value.candidates;
  const limitations = value.limitations;
  if (!['ok', 'partial', 'unreadable', 'unsupported'].includes(String(value.status))
      || !Array.isArray(candidates) || candidates.length > 100
      || !Array.isArray(limitations) || limitations.length > 100 || !limitations.every(text)
      || (value.status !== 'ok' && limitations.length === 0)
      || (['unreadable', 'unsupported'].includes(String(value.status)) && candidates.length !== 0)
      || (candidates.length === 100 && value.status !== 'partial')) throw invalid();
  const ids = new Set<string>();
  const boxes = new Set<string>();
  for (const candidate of candidates) {
    if (!object(candidate) || !text(candidate.id) || ids.has(candidate.id)
        || !text(candidate.category) || !text(candidate.visual_cue)
        || (candidate.source_label !== undefined && candidate.source_label !== null && typeof candidate.source_label !== 'string')
        || typeof candidate.uncertain !== 'boolean' || !object(candidate.geometry)
        || candidate.geometry.kind !== 'box' || !coordinatePair(candidate.geometry.minimum)
        || !coordinatePair(candidate.geometry.maximum)) throw invalid();
    const [x1, y1] = candidate.geometry.minimum;
    const [x2, y2] = candidate.geometry.maximum;
    if (x1 < 0 || y1 < 0 || x1 >= x2 || y1 >= y2 || x2 > submitted.width || y2 > submitted.height
        || (candidate.uncertain ? !text(candidate.uncertainty_reason) : candidate.uncertainty_reason != null)) throw invalid();
    const key = JSON.stringify([candidate.category, x1, y1, x2, y2]);
    if (boxes.has(key)) throw invalid();
    ids.add(candidate.id);
    boxes.add(key);
  }
  if (!object(value.metrics) || !finite(value.metrics.elapsed_ms) || value.metrics.elapsed_ms < 0
      || !optionalTokens(value.metrics.prompt_tokens) || !optionalTokens(value.metrics.completion_tokens)
      || !object(value.provenance) || !text(value.provenance.requested_model)
      || !text(value.provenance.returned_model) || !text(value.provenance.prompt_version)) throw invalid();
  return value as unknown as ImageCandidateResponse;
}

export async function requestCandidates(
  image: PreparedCandidateImage,
  question: string,
  signal: AbortSignal,
): Promise<ImageCandidateResponse> {
  aborted(signal);
  const trimmed = question.trim();
  if (!trimmed || trimmed.length > 4000) throw new Error('Enter a question with 1 to 4000 characters.');
  const body = new FormData();
  body.append('image', image.blob, 'drawing.png');
  body.append('question', trimmed);
  let response: Response;
  try {
    response = await fetch('/api/v1/candidates', { method: 'POST', body, signal });
  } catch {
    aborted(signal);
    throw new Error('The analysis service is unavailable. Start the backend and try again.');
  }
  aborted(signal);
  let value: unknown;
  try {
    value = await response.json();
  } catch {
    aborted(signal);
    if (!response.ok)
      throw new Error(`The analysis request failed (HTTP ${response.status}). Check that the image API backend is running and the frontend /api proxy can reach it.`);
    if (response.headers.get('content-type')?.split(';')[0].trim().toLowerCase() === 'text/html')
      throw new Error('The analysis endpoint returned a web page instead of JSON. Configure the frontend /api proxy to reach the image API backend.');
    throw new Error('The analysis service returned unreadable JSON. Check the image API backend logs and try again.');
  }
  aborted(signal);
  if (!response.ok) {
    if (object(value) && value.schema_version === '0.1.0' && text(value.code)
        && text(value.request_id) && text(value.message) && value.message.length <= 2000)
      throw new Error(value.message);
    throw new Error('The analysis request failed. Please try again.');
  }
  return validateResponse(value, image);
}
