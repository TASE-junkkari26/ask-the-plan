import { test } from 'node:test';
import type { TestContext } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { prepareCandidateImage, requestCandidates } from './candidateApi.ts';
import type { PreparedCandidateImage } from './candidateApi.ts';
import type { ImageCandidateResponse, AnalysisCall, AnalysisDecisionNode } from '../contracts/ImageCandidateResponse';
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

test('candidate request submits the exact snapshot and advertises streaming without overriding multipart headers', async (t) => {
  const controller = new AbortController();
  let called = 0;
  t.mock.method(globalThis, 'fetch', async (url: string, options: RequestInit) => {
    called++;
    assert.equal(url, '/api/v1/candidates');
    assert.equal(options.method, 'POST');
    assert.deepEqual(options.headers, { Accept: 'application/x-ndjson' });
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

function traceFor(value = result()) {
  return {
    request_id: value.request_id, question_sha256: createHash('sha256').update('Windows?').digest('hex'),
    image: value.image, mode: 'auto' as const, policy_version: 'capability-v1', capability_version: 'pilot-v1',
    selected_profile: 'strong' as const, recommended_profile: 'strong' as const,
    assessments: { normal_fit: 'uncertain', task_kind: 'instance_discovery' },
    assessment_probabilities: { normal_fit: 0.62, task_kind: 0.95 },
    calls: [{ id: 'routing', purpose: 'routing' as const, requested_model: 'gemini-decision-1', returned_model: 'gemini-decision-1',
      completed_at: '2026-11-14T20:00:00Z', outcome: 'completed' as const, elapsed_ms: 100,
      input_sha256: value.image.inference_sha256, input_width: 800, input_height: 400,
      prompt_tokens: 100, completion_tokens: 0 }] as [AnalysisCall],
    nodes: [{ id: 'fit', criterion: 'capability' as const, state: 'evaluated' as const,
      reason_code: 'fit_below_threshold', value: 'supported', probability: 0.62, threshold: 0.9, call_id: 'routing' }] as [AnalysisDecisionNode],
  };
}

test('source- and question-bound decision traces survive success and terminal failures', async (t) => {
  const value = result();
  value.decision_trace = traceFor(value);
  t.mock.method(globalThis, 'fetch', async () => Response.json(value));
  assert.deepEqual((await requestCandidates(prepared, ' Windows? ', new AbortController().signal)).decision_trace, value.decision_trace);
  t.mock.restoreAll();
  const { CandidateApiError } = await import('./candidateApi.ts');
  t.mock.method(globalThis, 'fetch', async () => Response.json({
    schema_version: '0.1.0', request_id: value.request_id, code: 'provider_configuration',
    message: 'Advanced analysis is unavailable.', retryable: false, decision_trace: value.decision_trace,
  }, { status: 503 }));
  await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal), (error: unknown) => {
    assert.ok(error instanceof CandidateApiError);
    assert.deepEqual(error.decisionTrace, value.decision_trace);
    return true;
  });
});

test('stale decision traces and invalid probabilities/references cannot reach the UI', async (t) => {
  const bad = [
    { mode: ['auto'] }, { selected_profile: ['strong'] },
    { nodes: [{ ...traceFor().nodes[0], criterion: ['capability'] }] },
    { calls: [{ ...traceFor().calls[0], purpose: ['routing'] }] },
    { request_id: 'other-request' }, { question_sha256: 'c'.repeat(64) },
    { image: { ...result().image, sha256: 'c'.repeat(64) } },
    { image: { ...result().image, inference_sha256: 'c'.repeat(64) } },
    { nodes: [{ ...traceFor().nodes[0], probability: 1.1 }] },
    { nodes: [{ ...traceFor().nodes[0], threshold: -0.1 }] },
    { nodes: [{ ...traceFor().nodes[0], parent_id: 'missing' }] },
    { nodes: [{ ...traceFor().nodes[0], call_id: 'missing' }] },
    { calls: [{ ...traceFor().calls[0], prompt_tokens: -1 }] },
    { calls: [{ ...traceFor().calls[0], input_sha256: 'c'.repeat(64) }] },
    { calls: [{ ...traceFor().calls[0], completed_at: 'unknown' }] },
    { calls: [traceFor().calls[0], traceFor().calls[0]] },
    { assessment_probabilities: { normal_fit: 2 } },
    { assessment_probabilities: { unknown_trait: 0.9 } },
  ];
  for (const change of bad) {
    t.mock.method(globalThis, 'fetch', async () => Response.json({ ...result(), decision_trace: { ...traceFor(), ...change } }));
    await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal), /invalid decision trace/);
    t.mock.restoreAll();
  }
});


test('a cancelled routing call can report a pending route without claiming an analyzer ran', async (t) => {
  const value = result();
  const trace = { ...traceFor(value), selected_profile: 'pending', recommended_profile: null,
    assessments: {}, assessment_probabilities: {},
    calls: [{ ...traceFor(value).calls[0], outcome: 'cancelled', returned_model: null }],
    nodes: [{ id: 'cancelled', criterion: 'capability', state: 'failed', reason_code: 'analysis_cancelled', call_id: 'routing' }],
  };
  t.mock.method(globalThis, 'fetch', async () => Response.json({
    schema_version: '0.1.0', request_id: value.request_id, code: 'deadline_exceeded',
    message: 'The request deadline expired.', retryable: true, decision_trace: trace,
  }, { status: 504 }));
  const { CandidateApiError } = await import('./candidateApi.ts');
  await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal), (error: unknown) => {
    assert.ok(error instanceof CandidateApiError);
    assert.equal(error.decisionTrace?.selected_profile, 'pending');
    return true;
  });
});

test('decision labels preserve pending routes and explain routing failures without claiming dispatch', async () => {
  const { decisionReason, decisionValue, routeLabel } = await import('./decisionTrace.ts');
  assert.equal(routeLabel('pending', 'en'), 'Route not selected');
  assert.equal(decisionValue('selected_view', 'fi'), 'Valittu näkymä');
  assert.equal(decisionValue('instance_discovery', 'fi'), 'Paikanna näkyvät kohteet');
  assert.equal(decisionValue('unrecognized_future_choice', 'en'), 'Unavailable');
  for (const reason of ['router_timeout', 'router_failed']) {
    const label = decisionReason({ id: 'routing', criterion: 'capability', state: 'failed', reason_code: reason }, 'en');
    assert.doesNotMatch(label, /selected|ran|completed/);
  }
  assert.match(decisionReason({ id: 'budget', criterion: 'analysis', state: 'failed', reason_code: 'budget_exhausted' }, 'en'), /request time budget was exhausted/);
});


function handoff(value = result()) {
  return { schema_version: '0.1.0', type: 'handoff', progress: {
    schema_version: '0.1.0', request_id: value.request_id, image: value.image,
    question_sha256: createHash('sha256').update('Windows?').digest('hex'),
    requested_model: value.provenance.requested_model,
  } };
}
const eventBytes = (frame: unknown) => new TextEncoder().encode(JSON.stringify(frame) + '\n');
function streamingResponse(frames: unknown[], chunkSize = 65536, requestId = 'request-test') {
  const bytes = new TextEncoder().encode(frames.map((frame) => JSON.stringify(frame) + '\n').join(''));
  return new Response(new ReadableStream<Uint8Array>({
    start(controller) {
      for (let i = 0; i < bytes.length; i += chunkSize) controller.enqueue(bytes.subarray(i, i + chunkSize));
      controller.close();
    },
  }), { headers: { 'Content-Type': 'application/x-ndjson; charset=utf-8', 'X-Request-ID': requestId } });
}

test('model handoff is delivered while the final response is still blocked', async (t) => {
  let stream!: ReadableStreamDefaultController<Uint8Array>;
  let sawProgress!: () => void;
  const progressed = new Promise<void>((resolve) => { sawProgress = resolve; });
  const response = new Response(new ReadableStream<Uint8Array>({ start(controller) {
    stream = controller;
    controller.enqueue(eventBytes(handoff()));
  } }), { headers: { 'Content-Type': 'application/x-ndjson', 'X-Request-ID': 'request-test' } });
  t.mock.method(globalThis, 'fetch', async () => response);
  let completed = false;
  const pending = requestCandidates(prepared, 'Windows?', new AbortController().signal, (progress) => {
    assert.equal(progress.requested_model, result().provenance.requested_model);
    assert.equal(progress.image.sha256, prepared.sha256);
    sawProgress();
  }).finally(() => { completed = true; });
  await progressed;
  assert.equal(completed, false);
  stream.enqueue(eventBytes({ schema_version: '0.1.0', type: 'result', result: result() }));
  stream.close();
  assert.deepEqual(await pending, result());
});

test('streaming handles arbitrary byte and unicode boundaries without resubmitting analysis', async (t) => {
  const value = result();
  value.candidates![0].visual_cue = 'Näkyvä ikkuna · fenêtre · 窓';
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async () => {
    calls++;
    return streamingResponse([handoff(value), { schema_version: '0.1.0', type: 'result', result: value }], 1);
  });
  assert.deepEqual(await requestCandidates(prepared, 'Windows?', new AbortController().signal), value);
  assert.equal(calls, 1);
});

test('legacy JSON fallback succeeds without fabricating a handoff or retrying', async (t) => {
  let calls = 0;
  let progress = 0;
  t.mock.method(globalThis, 'fetch', async () => { calls++; return Response.json(result()); });
  assert.deepEqual(await requestCandidates(prepared, 'Windows?', new AbortController().signal, () => { progress++; }), result());
  assert.equal(calls, 1);
  assert.equal(progress, 0);
});

test('streamed errors preserve the recorded trace without turning failure into a result', async (t) => {
  const value = result();
  const error = { schema_version: '0.1.0', request_id: value.request_id, code: 'provider_error',
    message: 'The analyzer could not finish.', retryable: false, decision_trace: traceFor(value) };
  t.mock.method(globalThis, 'fetch', async () => streamingResponse([
    handoff(value), { schema_version: '0.1.0', type: 'error', error },
  ]));
  const { CandidateApiError } = await import('./candidateApi.ts');
  await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal), (caught: unknown) => {
    assert.ok(caught instanceof CandidateApiError);
    assert.equal(caught.message, error.message);
    assert.deepEqual(caught.decisionTrace, error.decision_trace);
    return true;
  });
});

test('stale or malformed progress and duplicate/extra frames are rejected', async (t) => {
  const final = { schema_version: '0.1.0', type: 'result', result: result() };
  const bad = [
    [{ ...handoff(), progress: { ...handoff().progress, schema_version: undefined } }, final],
    [{ ...handoff(), progress: { ...handoff().progress, schema_version: '2.0.0' } }, final],
    [{ ...handoff(), progress: { ...handoff().progress, request_id: 'another-request' } }, final],
    [{ ...handoff(), progress: { ...handoff().progress, question_sha256: 'c'.repeat(64) } }, final],
    [{ ...handoff(), progress: { ...handoff().progress, image: { ...result().image, sha256: 'c'.repeat(64) } } }, final],
    [{ ...handoff(), progress: { ...handoff().progress, image: { ...result().image, width: 1 } } }, final],
    [{ ...handoff(), result: result() }, final],
    [handoff(), handoff(), final],
    [handoff(), final, handoff()],
    [handoff(), { ...final, result: { ...result(), provenance: { ...result().provenance, requested_model: 'contradictory-model' } } }],
    [handoff()],
    [{ schema_version: '0.1.0', type: 'unknown' }],
  ];
  for (const frames of bad) {
    t.mock.method(globalThis, 'fetch', async () => streamingResponse(frames));
    await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal), /different request or source|invalid or incomplete progress stream/);
    t.mock.restoreAll();
  }
  t.mock.method(globalThis, 'fetch', async () => streamingResponse([handoff(), final], 65536, 'wrong-header-id'));
  await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal), /different request or source/);
});

test('aborting the stream cancels its reader and cannot deliver later progress', async (t) => {
  let cancelled = false;
  let stream!: ReadableStreamDefaultController<Uint8Array>;
  const aborter = new AbortController();
  t.mock.method(globalThis, 'fetch', async () => new Response(new ReadableStream<Uint8Array>({
    start(controller) { stream = controller; },
    cancel() { cancelled = true; },
  }), { headers: { 'Content-Type': 'application/x-ndjson', 'X-Request-ID': 'request-test' } }));
  let progress = 0;
  const pending = requestCandidates(prepared, 'Windows?', aborter.signal, () => { progress++; });
  await new Promise((resolve) => setTimeout(resolve, 20));
  aborter.abort();
  await assert.rejects(pending, { name: 'AbortError' });
  assert.equal(cancelled, true);
  assert.equal(progress, 0);
  assert.throws(() => stream.enqueue(eventBytes(handoff())));
});

test('success requires a handoff but pre-dispatch errors can arrive without one', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => streamingResponse([{ schema_version: '0.1.0', type: 'result', result: result() }]));
  await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal), /incomplete progress stream/);
  t.mock.restoreAll();
  t.mock.method(globalThis, 'fetch', async () => streamingResponse([{ schema_version: '0.1.0', type: 'error', error: {
    schema_version: '0.1.0', request_id: 'request-test', code: 'invalid_image', message: 'Could not prepare the image.', retryable: false,
  } }]));
  await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal), /Could not prepare the image/);
  t.mock.restoreAll();
  t.mock.method(globalThis, 'fetch', async () => streamingResponse([]));
  await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal), /incomplete progress stream/);
});

test('stream parser rejects invalid bytes, unbound headers and excessive buffered data', async (t) => {
  const headers = { 'Content-Type': 'application/x-ndjson', 'X-Request-ID': 'request-test' };
  const values = [
    new Response('{invalid}\n', { headers }),
    new Response(new Uint8Array([0xff, 0xfe]), { headers }),
    new Response(' '.repeat(1024 * 1024 + 1), { headers }),
    new Response(eventBytes(handoff()), { headers: { 'Content-Type': 'application/x-ndjson' } }),
  ];
  for (const response of values) {
    t.mock.method(globalThis, 'fetch', async () => response);
    await assert.rejects(requestCandidates(prepared, 'Windows?', new AbortController().signal), /invalid or incomplete progress stream/);
    t.mock.restoreAll();
  }
});
