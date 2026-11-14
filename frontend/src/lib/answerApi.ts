import type { AnswerRequest, AnswerSnapshot } from '../contracts/AnswerRequest';
import type { AnswerResponse } from '../contracts/AnswerResponse';
import type { ImageCandidateProgress } from '../contracts/ImageCandidateStreamEvent';
import type { ImportedDrawing } from '../types';
import type { PreparedCandidateImage } from './candidateApi.ts';
import { candidateError, validateCandidateProgress, validateCandidateResponse } from './candidateApi.ts';
import { answerValue, validateIfcAnswer } from './ifcApi.ts';

export interface RegisteredAnswerSource {
  source_id: string;
  source_sha256: string;
  display_sha256: string;
  source_revision: string;
  display_width: number;
  display_height: number;
  filename: string;
  media_type: string;
  snapshot: AnswerSnapshot;
}

export class AnswerApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'AnswerApiError';
    this.status = status;
  }
}

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function text(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}
function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

/** A matching PNG alone cannot identify a page, layout or native mapping. */
export function sameAnswerSnapshot(first: AnswerSnapshot, second: AnswerSnapshot): boolean {
  return (['source_sha256', 'source_revision', 'display_sha256', 'display_width', 'display_height',
    'page_index', 'layout_name', 'rotation', 'viewport_transform', 'source_bounds'] as const)
    .every((key) => JSON.stringify(first[key] ?? (key === 'rotation' ? 0 : null))
      === JSON.stringify(second[key] ?? (key === 'rotation' ? 0 : null)));
}

export async function sha256(bytes: ArrayBuffer): Promise<string> {
  if (!globalThis.crypto?.subtle) throw new Error('Source verification requires localhost or an HTTPS connection.');
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), (n) => n.toString(16).padStart(2, '0')).join('');
}

const sourceHashes = new WeakMap<File, Promise<string>>();
export async function drawingSnapshot(drawing: ImportedDrawing, image: PreparedCandidateImage, signal: AbortSignal): Promise<AnswerSnapshot> {
  signal.throwIfAborted();
  let digest = sourceHashes.get(drawing.file);
  if (!digest) {
    digest = drawing.file.arrayBuffer().then(sha256);
    sourceHashes.set(drawing.file, digest);
    void digest.catch(() => sourceHashes.delete(drawing.file));
  }
  const originalHash = await digest;
  signal.throwIfAborted();
  return {
    source_sha256: originalHash, source_revision: originalHash,
    display_sha256: image.sha256, display_width: image.width, display_height: image.height,
    page_index: drawing.page - 1, layout_name: drawing.dxf?.layouts[drawing.page - 1] ?? null,
    rotation: (drawing.pdf?.rotation ?? 0) as 0 | 90 | 180 | 270,
    viewport_transform: drawing.pdf?.viewportTransform ?? null,
    source_bounds: drawing.pdf?.sourceBounds ?? null,
  };
}

async function fetchResponse(url: string, init: RequestInit, signal: AbortSignal): Promise<Response> {
  signal.throwIfAborted();
  try {
    const response = await fetch(url, { ...init, signal });
    signal.throwIfAborted();
    return response;
  } catch (error) {
    signal.throwIfAborted();
    if (error instanceof AnswerApiError) throw error;
    throw new Error('The answer service is unavailable. Start the Python backend and try again.');
  }
}

async function readJson(response: Response, signal: AbortSignal): Promise<unknown> {
  let value: unknown;
  try { value = await response.json(); }
  catch {
    signal.throwIfAborted();
    throw new AnswerApiError(`The answer service returned unreadable data (HTTP ${response.status}). Check the backend and /api proxy.`, response.status);
  }
  signal.throwIfAborted();
  if (!response.ok) {
    const message = object(value) && text(value.message) ? value.message : 'The source-bound answer request failed.';
    throw new AnswerApiError(message.slice(0, 2000), response.status);
  }
  return value;
}

export async function registerAnswerSource(file: File, image: PreparedCandidateImage, snapshot: AnswerSnapshot, signal: AbortSignal): Promise<RegisteredAnswerSource> {
  const body = new FormData();
  body.append('file', file, file.name);
  body.append('image', image.blob, 'display.png');
  body.append('snapshot', JSON.stringify(snapshot));
  const value = await readJson(await fetchResponse('/api/v1/sources', { method: 'POST', body }, signal), signal);
  if (!object(value) || !text(value.source_id) || value.source_sha256 !== snapshot.source_sha256
      || value.display_sha256 !== image.sha256 || value.source_revision !== snapshot.source_revision
      || value.display_width !== image.width || value.display_height !== image.height
      || typeof value.filename !== 'string' || !text(value.media_type))
    throw new Error('The registered source does not match the original file and displayed page.');
  if (value.snapshot != null && (!object(value.snapshot) || !sameAnswerSnapshot(value.snapshot as unknown as AnswerSnapshot, snapshot)))
    throw new Error('The registered source does not match the selected page, layout or display mapping.');
  return { ...value, snapshot: structuredClone(snapshot) } as unknown as RegisteredAnswerSource;
}

/** Session deletion is best effort; active backend leases finish before eviction. */
export async function releaseAnswerSource(sourceId: string): Promise<void> {
  try { await fetch(`/api/v1/sources/${encodeURIComponent(sourceId)}`, { method: 'DELETE', keepalive: true }); }
  catch { /* The bounded backend TTL also releases abandoned sessions. */ }
}

const statuses = new Set(['answered', 'partial', 'needs_clarification', 'missing_source', 'missing_information',
  'incomplete_coverage', 'unsupported_operation', 'conflicting_evidence', 'insufficient_calibration', 'execution_error', 'blocked']);

/** Reject stale results before their evidence is attached to the displayed source. */
export function validateAnswerResponse(value: unknown, request: AnswerRequest, questionHash: string, image?: PreparedCandidateImage): AnswerResponse {
  const invalid = () => new Error('The answer service returned invalid or unbound answer evidence. Please ask again.');
  if (!object(value) || value.schema_version !== '0.1.0' || !text(value.request_id)
      || value.question !== request.question || value.question_sha256 !== questionHash || !object(value.source)
      || value.source.source_sha256 !== request.source_sha256
      || value.source.source_id !== (request.source_id ?? request.model_id))
    throw new Error('The answer belongs to a different source revision or question. Please ask again.');
  if (request.snapshot) {
    if (!sameAnswerSnapshot(value.source as unknown as AnswerSnapshot, request.snapshot))
      throw new Error('The answer belongs to a different page, layout, or display mapping. Please ask again.');
  }
  if (!text(value.source.scope_label) || !object(value.interpretation) || !Array.isArray(value.interpretation.requested_parts)
      || !value.interpretation.requested_parts.length || !Array.isArray(value.parts) || !value.parts.length
      || !Array.isArray(value.narrative) || !Array.isArray(value.evidence_contexts) || !object(value.metrics)) throw invalid();
  const keys = new Set<string>();
  const claims = new Map<string, Set<string>>();
  const contexts = new Set<string>();
  for (const context of value.evidence_contexts) {
    if (!object(context) || !text(context.id) || contexts.has(context.id) || !object(context.bundle)) throw invalid();
    if (!Array.isArray(context.bundle.assets) || !context.bundle.assets.some((asset) => object(asset) && asset.sha256 === request.source_sha256)
        || !Array.isArray(context.bundle.anchors)) throw invalid();
    if (value.source.display_sha256 != null) {
      const displayDigest = value.source.display_sha256;
      if (!object(context.source_snapshot)
          || !sameAnswerSnapshot(context.source_snapshot as unknown as AnswerSnapshot, value.source as unknown as AnswerSnapshot)
          || !context.bundle.assets.some((asset) => object(asset) && asset.sha256 === displayDigest)) throw invalid();
    }
    contexts.add(context.id);
  }
  for (const part of value.parts) {
    if (!object(part) || !text(part.key) || keys.has(part.key) || !statuses.has(String(part.status))
        || (part.evidence_context_id != null && (!text(part.evidence_context_id) || !contexts.has(part.evidence_context_id)))) throw invalid();
    keys.add(part.key);
    const claimIds = new Set<string>();
    if (part.result != null) {
      if (!object(part.result) || part.result.status !== part.status || !Array.isArray(part.result.claims)
          || !Array.isArray(part.result.calculations) || !Array.isArray(part.result.entity_sets) || !Array.isArray(part.result.issues)) throw invalid();
      for (const claim of part.result.claims) {
        if (!object(claim) || !text(claim.id) || claimIds.has(claim.id) || !answerValue(claim.value)
            || !['exact', 'estimated', 'lower_bound', 'upper_bound'].includes(String(claim.quality))) throw invalid();
        claimIds.add(claim.id);
      }
    }
    claims.set(part.key, claimIds);
  }
  const requestedKeys = value.interpretation.requested_parts.map((part: unknown) => object(part) ? part.key : null);
  if (requestedKeys.length !== keys.size || new Set(requestedKeys).size !== keys.size
      || requestedKeys.some((key: unknown) => typeof key !== 'string' || !keys.has(key))) throw invalid();
  if (request.parts && (request.parts.length !== keys.size || request.parts.some((part) => !keys.has(part.key)))) throw invalid();
  const sentences = new Set<string>();
  for (const sentence of value.narrative) {
    if (!object(sentence) || !text(sentence.id) || sentences.has(sentence.id) || !text(sentence.part_key)
        || !keys.has(sentence.part_key) || !text(sentence.text) || !strings(sentence.claim_ids)
        || !sentence.claim_ids.every((id) => claims.get(sentence.part_key as string)?.has(id))
        || !strings(sentence.anchor_ids) || !['claim', 'issue'].includes(String(sentence.kind))
        || !['exact', 'estimated', 'lower_bound', 'upper_bound', 'unavailable'].includes(String(sentence.qualification))) throw invalid();
    if (sentence.kind === 'claim' && sentence.claim_ids.length === 0) throw invalid();
    const part = value.parts.find((item: unknown) => object(item) && item.key === sentence.part_key) as Record<string, unknown>;
    const context = value.evidence_contexts.find((item: unknown) => object(item) && item.id === part.evidence_context_id) as { bundle?: { anchors?: { id: string }[] } } | undefined;
    if (sentence.anchor_ids.some((id) => !context?.bundle?.anchors?.some((anchor) => anchor.id === id))) throw invalid();
    sentences.add(sentence.id);
  }
  if (value.candidate_response != null) {
    if (!image) throw invalid();
    validateCandidateResponse(value.candidate_response, image, questionHash);
  }
  if (value.ifc_response != null) {
    if (!request.model_id) throw invalid();
    validateIfcAnswer(value.ifc_response, { model_id: request.model_id, source_sha256: request.source_sha256,
      question: request.question, scope: 'model', visible_step_ids: null });
  }
  return value as unknown as AnswerResponse;
}

async function readAnswerStream(response: Response, request: AnswerRequest, questionHash: string,
  signal: AbortSignal, image?: PreparedCandidateImage, onProgress?: (value: ImageCandidateProgress) => void): Promise<AnswerResponse> {
  const invalid = () => new Error('The answer service returned an invalid or incomplete progress stream. Please ask again.');
  const requestId = response.headers.get('X-Request-ID');
  if (!response.body || !text(requestId)) throw invalid();
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8', { fatal: true });
  let buffered = '';
  let bytes = 0;
  let handedOff: ImageCandidateProgress | null = null;
  const state: { terminal: AnswerResponse | Error | null } = { terminal: null };
  const abort = () => { void reader.cancel(signal.reason).catch(() => {}); };
  signal.addEventListener('abort', abort, { once: true });
  const consume = (line: string) => {
    if (!line.trim()) return;
    if (state.terminal || line.length > 32 * 1024 * 1024) throw invalid();
    let frame: unknown;
    try { frame = JSON.parse(line); } catch { throw invalid(); }
    if (!object(frame) || frame.schema_version !== '0.1.0') throw invalid();
    if (frame.type === 'handoff') {
      if (!image || handedOff || frame.result != null || frame.error != null) throw invalid();
      handedOff = validateCandidateProgress(frame.progress, requestId, image, questionHash);
      signal.throwIfAborted();
      onProgress?.(handedOff);
    } else if (frame.type === 'result') {
      if (!response.ok || frame.progress != null || frame.error != null) throw invalid();
      const result = validateAnswerResponse(frame.result, request, questionHash, image);
      if (result.request_id !== requestId) throw invalid();
      if (handedOff && result.candidate_response
          && (result.candidate_response.image.inference_sha256 !== handedOff.image.inference_sha256
          || result.candidate_response.provenance.requested_model !== handedOff.requested_model)) throw invalid();
      state.terminal = result;
    } else if (frame.type === 'error') {
      if (!object(frame.error) || frame.error.request_id !== requestId || frame.result != null || frame.progress != null) throw invalid();
      if (image) state.terminal = candidateError(frame.error, image, questionHash);
      else if (text(frame.error.message)) state.terminal = new AnswerApiError(frame.error.message.slice(0, 2000), response.status);
      else throw invalid();
    } else throw invalid();
  };
  try {
    while (true) {
      signal.throwIfAborted();
      const part = await reader.read();
      signal.throwIfAborted();
      if (part.done) break;
      bytes += part.value.byteLength;
      if (bytes > 32 * 1024 * 1024) throw invalid();
      buffered += decoder.decode(part.value, { stream: true });
      let end: number;
      while ((end = buffered.indexOf('\n')) !== -1) {
        consume(buffered.slice(0, end));
        buffered = buffered.slice(end + 1);
      }
    }
    buffered += decoder.decode();
    if (buffered.trim()) consume(buffered);
    if (!state.terminal) throw invalid();
    if (state.terminal instanceof Error) throw state.terminal;
    return state.terminal;
  } finally {
    signal.removeEventListener('abort', abort);
    void reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export async function requestAnswer(request: AnswerRequest, signal: AbortSignal,
  image?: PreparedCandidateImage, onProgress?: (value: ImageCandidateProgress) => void): Promise<AnswerResponse> {
  signal.throwIfAborted();
  if (!request.question.trim() || request.question.length > 4000) throw new Error('Enter a question with 1 to 4000 characters.');
  const questionHash = await sha256(new TextEncoder().encode(request.question).buffer);
  signal.throwIfAborted();
  const response = await fetchResponse('/api/v1/answers', { method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/x-ndjson' }, body: JSON.stringify(request) }, signal);
  if (response.headers.get('content-type')?.split(';')[0].trim().toLowerCase() === 'application/x-ndjson')
    return readAnswerStream(response, request, questionHash, signal, image, onProgress);
  return validateAnswerResponse(await readJson(response, signal), request, questionHash, image);
}
