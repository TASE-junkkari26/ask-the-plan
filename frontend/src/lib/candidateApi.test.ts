import { test } from 'node:test';
import type { TestContext } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { prepareCandidateImage, requestCandidates } from './candidateApi.ts';
import type { PreparedCandidateImage } from './candidateApi.ts';
import type { ImageCandidateResponse } from '../contracts/ImageCandidateResponse';
import type { ImportedDrawing } from '../types';

const prepared: PreparedCandidateImage = {
  blob: new Blob(['submitted snapshot'], { type: 'image/png' }),
  sha256: 'a'.repeat(64),
  width: 800,
  height: 400,
};

function result(): ImageCandidateResponse {
  return {
    schema_version: '0.1.0', request_id: 'request-test', scope: 'submitted_image',
    inventory_completeness: 'unverified', status: 'ok', limitations: [],
    image: {
      sha256: prepared.sha256, inference_sha256: 'b'.repeat(64),
      width: prepared.width, height: prepared.height,
      coordinate_system: 'display_pixels_top_left',
    },
    candidates: [{
      id: 'candidate-001', category: 'window', source_label: '121.A',
      geometry: { kind: 'box', minimum: [80, 40], maximum: [160, 80] },
      uncertain: false, uncertainty_reason: null, visual_cue: 'Parallel window lines.',
    }],
    provenance: { requested_model: 'test-model', returned_model: 'test-model', prompt_version: 'v1' },
    metrics: { elapsed_ms: 25, prompt_tokens: null, completion_tokens: 20 },
  };
}

test('candidate request submits the exact PNG snapshot and question without manual headers', async (t) => {
  const controller = new AbortController();
  let called = 0;
  t.mock.method(globalThis, 'fetch', async (url: string, options: RequestInit) => {
    called++;
    assert.equal(url, '/api/v1/candidates');
    assert.equal(options.method, 'POST');
    assert.equal(options.headers, undefined);
    assert.equal(options.signal, controller.signal);
    const body = options.body as FormData;
    assert.equal(body.get('question'), 'Missä ikkunat 121.A ovat?');
    const image = body.get('image') as File;
    assert.equal(image.type, 'image/png');
    assert.equal(await image.text(), 'submitted snapshot');
    return Response.json(result());
  });
  const response = await requestCandidates(prepared, ' Missä ikkunat 121.A ovat? ', controller.signal);
  assert.equal(response.candidates?.[0].source_label, '121.A');
  assert.equal(response.image.sha256, prepared.sha256);
  assert.equal(called, 1);
});

test('source hash and display-frame mismatches cannot attach candidates to another view', async (t) => {
  for (const changes of [
    { sha256: 'c'.repeat(64) }, { width: 400 }, { height: 800 },
  ]) {
    const response = result();
    Object.assign(response.image, changes);
    t.mock.method(globalThis, 'fetch', async () => Response.json(response));
    await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal), /different image or coordinate frame/);
    t.mock.restoreAll();
  }
});

test('invalid versions, geometry, duplicate IDs, and unsupported response shapes are rejected', async (t) => {
  const bad: unknown[] = [null, {}, { ...result(), schema_version: '2' }];
  for (const box of [
    { minimum: [-1, 0], maximum: [100, 100] },
    { minimum: [0, 0], maximum: [801, 100] },
    { minimum: [0, 0], maximum: [100, 401] },
    { minimum: [10, 10], maximum: [10, 20] },
    { minimum: [0, 0, 0], maximum: [100, 100, 100] },
    { minimum: ['0', 0], maximum: [100, 100] },
  ]) {
    const response = result();
    Object.assign(response.candidates![0].geometry, box);
    bad.push(response);
  }
  const duplicate = result();
  duplicate.candidates!.push(structuredClone(duplicate.candidates![0]));
  bad.push(duplicate);
  const invalidUncertainty = result();
  invalidUncertainty.candidates![0].uncertain = true;
  bad.push(invalidUncertainty);
  bad.push({ ...result(), status: 'unsupported', limitations: ['Needs unseen floors.'] });
  for (const response of bad) {
    t.mock.method(globalThis, 'fetch', async () => Response.json(response));
    await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal), /invalid candidate data/);
    t.mock.restoreAll();
  }
});

test('empty detections, uncertainty and partial limitations retain their meanings', async (t) => {
  const partial = result();
  partial.status = 'partial';
  partial.limitations = ['One corner is unreadable.'];
  partial.candidates![0].uncertain = true;
  partial.candidates![0].uncertainty_reason = 'Could be a glazed door.';
  for (const value of [partial, { ...result(), candidates: [] }]) {
    t.mock.method(globalThis, 'fetch', async () => Response.json(value));
    const response = await requestCandidates(prepared, 'Windows?', new AbortController().signal);
    assert.deepEqual(response, value);
    assert.equal('answer' in response, false);
    assert.equal('count' in response, false);
    t.mock.restoreAll();
  }
});

test('safe API errors retain the backend diagnosis, including missing configuration', async (t) => {
  for (const [status, code, message] of [
    [429, 'busy', 'Candidate service is busy; try again later.'],
    [503, 'not_configured', 'Configure VERDA_INFERENCE_KEY on the backend.'],
  ] as const) {
    t.mock.method(globalThis, 'fetch', async () => Response.json({
      schema_version: '0.1.0', request_id: 'test', code, message, retryable: true,
    }, { status }));
    await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal), { message });
    t.mock.restoreAll();
  }
});

test('network failures explain that the backend must be started', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => { throw new TypeError('Network failure'); });
  await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal), /Start the backend/);
});

test('empty Vite errors and non-JSON proxy failures report HTTP status and backend routing', async (t) => {
  for (const [status, body] of [
    [500, ''], [502, '<html>proxy error</html>'], [503, 'Service Unavailable'], [504, 'Gateway Timeout'],
  ] as const) {
    t.mock.method(globalThis, 'fetch', async () => new Response(body, { status }));
    await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal),
      new RegExp(`HTTP ${status}.*image API backend.*frontend /api proxy`));
    t.mock.restoreAll();
  }
});

test('a frontend HTML fallback explains the missing API proxy without exposing its body', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('<!doctype html><html>app</html>', {
    headers: { 'Content-Type': 'text/html; charset=utf-8' },
  }));
  await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal), {
    message: 'The analysis endpoint returned a web page instead of JSON. Configure the frontend /api proxy to reach the image API backend.',
  });
});

test('malformed JSON from a successful endpoint points to backend logs', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('{"candidates":', {
    headers: { 'Content-Type': 'application/json' },
  }));
  await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal), /unreadable JSON.*backend logs/);
});

test('cancelled and blank questions do not send requests and pending cancellation stays an AbortError', async (t) => {
  let calls = 0;
  const controller = new AbortController();
  t.mock.method(globalThis, 'fetch', async () => {
    calls++;
    controller.abort();
    throw new DOMException('Cancelled', 'AbortError');
  });
  await assert.rejects(requestCandidates(prepared, ' ', controller.signal), /Enter a question/);
  assert.equal(calls, 0);
  await assert.rejects(requestCandidates(prepared, 'Windows?', controller.signal), { name: 'AbortError' });
  assert.equal(calls, 1);
  await assert.rejects(requestCandidates(prepared, 'Windows?', controller.signal), { name: 'AbortError' });
  assert.equal(calls, 1);
});

function rasterHarness(t: TestContext, mode: 'load' | 'pending' | 'encoding' = 'load') {
  const imageDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'Image');
  const documentDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'document');
  const blob = new Blob(['rasterized PNG bytes'], { type: 'image/png' });
  const operations: string[] = [];
  let image: MockImage;
  class MockImage {
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    constructor() { image = this; }
    set src(value: string) {
      if (value && mode !== 'pending') queueMicrotask(() => this.onload?.());
    }
  }
  const context = {
    fillStyle: '',
    fillRect: (..._args: unknown[]) => operations.push('white'),
    drawImage: (..._args: unknown[]) => operations.push('image'),
  };
  const canvas = {
    width: 0, height: 0,
    getContext: () => context,
    toBlob: (callback: (value: Blob) => void) => {
      operations.push('encode');
      if (mode !== 'encoding') queueMicrotask(() => callback(blob));
    },
  };
  Object.defineProperty(globalThis, 'Image', { configurable: true, value: MockImage });
  Object.defineProperty(globalThis, 'document', {
    configurable: true, value: { createElement: () => canvas },
  });
  t.after(() => {
    if (imageDescriptor) Object.defineProperty(globalThis, 'Image', imageDescriptor);
    else Reflect.deleteProperty(globalThis, 'Image');
    if (documentDescriptor) Object.defineProperty(globalThis, 'document', documentDescriptor);
    else Reflect.deleteProperty(globalThis, 'document');
  });
  return { blob, canvas, context, operations, get image() { return image; } };
}

function drawing(): ImportedDrawing {
  return {
    file: new File(['PDF source'], 'plans.pdf', { type: 'application/pdf' }),
    url: 'blob:rendered-page-two', width: 800, height: 400,
    kind: 'pdf', page: 2, pages: 4,
  };
}

test('preparation rasterizes the current rendered page on white and hashes the exact uploaded bytes', async (t) => {
  const harness = rasterHarness(t);
  const source = drawing();
  const image = await prepareCandidateImage(source);
  assert.equal(image.blob, harness.blob);
  assert.equal(image.sha256, createHash('sha256').update(await harness.blob.text()).digest('hex'));
  assert.deepEqual([image.width, image.height], [800, 400]);
  assert.deepEqual(harness.operations, ['white', 'image', 'encode']);
  assert.equal(harness.context.fillStyle, '#ffffff');
  assert.deepEqual([harness.canvas.width, harness.canvas.height], [0, 0]);
  assert.equal(harness.image.onload, null);
  assert.equal(harness.image.onerror, null);
  assert.equal(source.url, 'blob:rendered-page-two');
});

test('preparation bounds dimensions and rendered upload size before inference', async (t) => {
  const harness = rasterHarness(t);
  await assert.rejects(prepareCandidateImage({ ...drawing(), width: 10000, height: 10000 }), /40 megapixel/);
  await assert.rejects(prepareCandidateImage({ ...drawing(), width: 0 }), /invalid display dimensions/);
  Object.defineProperty(harness.blob, 'size', { value: 20 * 1024 * 1024 + 1 });
  await assert.rejects(prepareCandidateImage(drawing()), /20 MiB/);
  assert.equal(harness.canvas.width, 0);
});

test('cancelling image loading releases handlers without changing the imported source', async (t) => {
  const harness = rasterHarness(t, 'pending');
  const controller = new AbortController();
  const pending = prepareCandidateImage(drawing(), controller.signal);
  controller.abort();
  await assert.rejects(pending, { name: 'AbortError' });
  assert.equal(harness.image.onload, null);
  assert.equal(harness.image.onerror, null);
});

test('cancelling PNG encoding clears the worker canvas and never produces a late snapshot', async (t) => {
  const harness = rasterHarness(t, 'encoding');
  const controller = new AbortController();
  const pending = prepareCandidateImage(drawing(), controller.signal);
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(harness.operations, ['white', 'image', 'encode']);
  controller.abort();
  await assert.rejects(pending, { name: 'AbortError' });
  assert.equal(harness.canvas.width, 0);
});
