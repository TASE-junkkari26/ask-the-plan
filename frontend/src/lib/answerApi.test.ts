import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import type { AnswerRequest, AnswerSnapshot } from '../contracts/AnswerRequest';
import type { AnswerResponse } from '../contracts/AnswerResponse';
import type { ImportedDrawing } from '../types';
import type { PreparedCandidateImage } from './candidateApi.ts';
import { drawingSnapshot, registerAnswerSource, requestAnswer, sameAnswerSnapshot, validateAnswerResponse } from './answerApi.ts';
import { anchorEvidence, answerOutcomeLabel, answerStatusLabel, partAnswerPresentation, partMemberGroups, sentenceEvidence } from './answerEvidence.ts';

const question = 'What is the area of room 121.A?';
const questionHash = createHash('sha256').update(question).digest('hex');
const originalHash = 'a'.repeat(64);
const displayHash = 'b'.repeat(64);
const image: PreparedCandidateImage = { blob: new Blob(['upright snapshot'], { type: 'image/png' }), sha256: displayHash, width: 800, height: 400 };
const request: AnswerRequest = {
  source_id: 'source-test', source_sha256: originalHash, question,
  snapshot: { source_sha256: originalHash, source_revision: originalHash, display_sha256: displayHash,
    display_width: 800, display_height: 400, page_index: 1, rotation: 90,
    viewport_transform: [0, 2, 2, 0, -20, -40], source_bounds: [10, 20, 210, 420] },
};

function unavailableAnswer(): AnswerResponse {
  return {
    schema_version: '0.1.0', request_id: 'request-test', question, question_sha256: questionHash,
    source: { ...request.snapshot!, source_id: request.source_id!, kind: 'pdf', scope_label: 'Selected PDF page 2' },
    interpretation: { language: 'en', scope_label: 'Selected PDF page 2', requested_parts: [{ key: 'area', question, operation: 'area' }], ambiguities: [] },
    parts: [{ key: 'area', status: 'missing_information', message: { text: 'No source-backed area is available for room 121.A.' } }],
    narrative: [{ id: 'sentence-area', part_key: 'area', kind: 'issue', text: 'No source-backed area is available for room 121.A.', claim_ids: [], value_paths: [], anchor_ids: [], qualification: 'unavailable' }],
    evidence_contexts: [], metrics: { elapsed_ms: 12, external_attempts: 0, calls: [], model_input_tokens: 0, model_output_tokens: 0 },
  };
}

test('original registration retains exact file, PNG and PDF.js rotated crop mapping', async (t) => {
  const file = new File(['original PDF bytes'], '7.16.pdf', { type: 'application/pdf' });
  const drawing: ImportedDrawing = { file, url: 'blob:page', width: 800, height: 400, page: 2, pages: 3, kind: 'pdf',
    pdf: { rotation: 90, viewportTransform: [0, 2, 2, 0, -20, -40], sourceBounds: [10, 20, 210, 420] } };
  const controller = new AbortController();
  const snapshot = await drawingSnapshot(drawing, image, controller.signal);
  assert.equal(snapshot.source_sha256, createHash('sha256').update(await file.text()).digest('hex'));
  assert.notEqual(snapshot.source_sha256, snapshot.display_sha256);
  assert.equal(snapshot.page_index, 1);
  assert.deepEqual(snapshot.viewport_transform, drawing.pdf?.viewportTransform);
  t.mock.method(globalThis, 'fetch', async (url: string, init: RequestInit) => {
    assert.equal(url, '/api/v1/sources');
    assert.equal(init.method, 'POST');
    assert.equal(init.signal, controller.signal);
    const body = init.body as FormData;
    assert.equal(await (body.get('file') as File).text(), await file.text());
    assert.equal(await (body.get('image') as File).text(), await image.blob.text());
    assert.deepEqual(JSON.parse(String(body.get('snapshot'))), snapshot);
    return Response.json({ source_id: 'registered', filename: file.name, media_type: file.type,
      source_sha256: snapshot.source_sha256, source_revision: snapshot.source_revision,
      display_sha256: displayHash, display_width: 800, display_height: 400 });
  });
  assert.equal((await registerAnswerSource(file, image, snapshot, controller.signal)).source_id, 'registered');
});

test('JSON answers bind question, original hash, page and exact viewport mapping', async (t) => {
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async (url: string, init: RequestInit) => {
    calls++;
    assert.equal(url, '/api/v1/answers');
    assert.deepEqual(JSON.parse(String(init.body)), request);
    assert.equal((init.headers as Record<string, string>).Accept, 'application/x-ndjson');
    return Response.json(unavailableAnswer());
  });
  const answer = await requestAnswer(request, new AbortController().signal, image);
  assert.equal(answer.parts[0].status, 'missing_information');
  assert.match(answer.narrative![0].text, /121\.A/);
  assert.doesNotMatch(answer.narrative![0].text, /\bzero\b|\b0\b/);
  assert.equal(calls, 1);
});

test('stale source, question, page, layout, rotation and transform never attach to the current drawing', () => {
  for (const mutate of [
    (value: AnswerResponse) => { value.source.source_sha256 = 'c'.repeat(64); },
    (value: AnswerResponse) => { value.question_sha256 = 'c'.repeat(64); },
    (value: AnswerResponse) => { value.source.source_id = 'other'; },
    (value: AnswerResponse) => { value.source.page_index = 0; },
    (value: AnswerResponse) => { value.source.rotation = 0; },
    (value: AnswerResponse) => { value.source.layout_name = 'Roof'; },
    (value: AnswerResponse) => { value.source.viewport_transform = [1, 0, 0, 1, 0, 0]; },
    (value: AnswerResponse) => { value.source.source_bounds = [0, 0, 400, 800]; },
  ]) {
    const value = unavailableAnswer();
    mutate(value);
    assert.throws(() => validateAnswerResponse(value, request, questionHash, image), /different/);
  }
});

test('source-session reuse compares full page/layout mappings even when original and raster hashes match', () => {
  const snapshot = request.snapshot!;
  assert.equal(sameAnswerSnapshot(snapshot, structuredClone(snapshot)), true);
  const alternatives: AnswerSnapshot[] = [
    { ...snapshot, page_index: 2 }, { ...snapshot, layout_name: 'Upper floor' },
    { ...snapshot, rotation: 0 as const }, { ...snapshot, viewport_transform: [1, 0, 0, 1, 0, 0] },
    { ...snapshot, source_bounds: [20, 20, 220, 420] },
  ];
  for (const other of alternatives) assert.equal(sameAnswerSnapshot(snapshot, other), false);
});

test('every compound requested part must occur once and each sentence binds to its own claims', () => {
  const missingPart = unavailableAnswer();
  missingPart.interpretation.requested_parts.push({ key: 'width', question: 'What is its width?' });
  assert.throws(() => validateAnswerResponse(missingPart, request, questionHash, image), /invalid or unbound/);
  const inventedClaim = unavailableAnswer();
  inventedClaim.narrative![0].kind = 'claim';
  inventedClaim.narrative![0].claim_ids = ['invented'];
  assert.throws(() => validateAnswerResponse(inventedClaim, request, questionHash, image), /invalid or unbound/);
  const inventedAnchor = unavailableAnswer();
  inventedAnchor.narrative![0].anchor_ids = ['other-source'];
  assert.throws(() => validateAnswerResponse(inventedAnchor, request, questionHash, image), /invalid or unbound/);
});

test('native answers may finish without a model handoff and stream terminal binding stays strict', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ schema_version: '0.1.0', type: 'result', result: unavailableAnswer() }) + '\n',
    { headers: { 'Content-Type': 'application/x-ndjson', 'X-Request-ID': 'request-test' } }));
  const answer = await requestAnswer(request, new AbortController().signal, image);
  assert.equal(answer.metrics.external_attempts, 0);
  assert.equal(answer.parts[0].status, 'missing_information');
  t.mock.restoreAll();
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ schema_version: '0.1.0', type: 'result', result: unavailableAnswer() }) + '\n',
    { headers: { 'Content-Type': 'application/x-ndjson', 'X-Request-ID': 'other-request' } }));
  await assert.rejects(requestAnswer(request, new AbortController().signal, image), /invalid or incomplete/);
});

test('actual model handoff is delivered before terminal answer without a second request', async (t) => {
  const encoder = new TextEncoder();
  let finish: (() => void) | undefined;
  let calls = 0;
  const stream = new ReadableStream<Uint8Array>({ start(controller) {
    controller.enqueue(encoder.encode(JSON.stringify({ schema_version: '0.1.0', type: 'handoff', progress: {
      schema_version: '0.1.0', request_id: 'request-test', question_sha256: questionHash, requested_model: 'gemini-4-hydrogen',
      image: { sha256: image.sha256, inference_sha256: 'c'.repeat(64), width: image.width, height: image.height, coordinate_system: 'display_pixels_top_left' },
    } }) + '\n'));
    finish = () => { controller.enqueue(encoder.encode(JSON.stringify({ schema_version: '0.1.0', type: 'result', result: unavailableAnswer() }) + '\n')); controller.close(); };
  } });
  t.mock.method(globalThis, 'fetch', async () => { calls++; return new Response(stream, { headers: { 'Content-Type': 'application/x-ndjson', 'X-Request-ID': 'request-test' } }); });
  let handoff: string | undefined;
  const pending = requestAnswer(request, new AbortController().signal, image, (progress) => {
    handoff = progress.requested_model;
    finish?.();
  });
  await pending;
  assert.equal(handoff, 'gemini-4-hydrogen');
  assert.equal(calls, 1);
});

test('cancellation during JSON parsing or pending streaming cannot publish a stale answer', async (t) => {
  const controller = new AbortController();
  t.mock.method(globalThis, 'fetch', async () => ({ ok: true, status: 200, headers: new Headers({ 'Content-Type': 'application/json' }),
    json: async () => { controller.abort(); return unavailableAnswer(); } } as Response));
  await assert.rejects(requestAnswer(request, controller.signal, image), { name: 'AbortError' });
  t.mock.restoreAll();
  const streamController = new AbortController();
  let cancelled = false;
  const stream = new ReadableStream<Uint8Array>({ cancel() { cancelled = true; } });
  t.mock.method(globalThis, 'fetch', async () => {
    setTimeout(() => streamController.abort(), 10);
    return new Response(stream, { headers: { 'Content-Type': 'application/x-ndjson', 'X-Request-ID': 'request-test' } });
  });
  await assert.rejects(requestAnswer(request, streamController.signal, image), { name: 'AbortError' });
  assert.equal(cancelled, true);
});

test('missing values and implementation gaps retain distinct visible statuses', () => {
  assert.equal(answerStatusLabel('missing_information', 'en'), 'Missing information');
  assert.equal(answerStatusLabel('unsupported_operation', 'en'), 'Not supported yet');
  assert.equal(answerStatusLabel('partial', 'fi'), 'Osittainen vastaus');
  assert.deepEqual(sentenceEvidence(unavailableAnswer(), unavailableAnswer().narrative![0]), []);
});

test('long technical failures get a concise summary while full diagnostics remain intact', () => {
  const response = unavailableAnswer();
  const diagnostic = 'The visual tool located candidate source regions, but it did not extract or execute the requested property, quantity or relation. That answer tool remains an implementation gap. Additional source inspection could not establish the requested area.';
  response.parts[0].status = 'unsupported_operation';
  response.parts[0].message = { text: diagnostic };
  response.narrative![0].text = diagnostic;
  const presented = partAnswerPresentation(response, 'area', 'en');
  assert.equal(presented.message, 'I couldn’t verify the requested answer from this drawing.');
  assert.deepEqual(presented.notes, [diagnostic]);
  assert.deepEqual(presented.claims, []);
  assert.equal(response.narrative![0].text, diagnostic);
  assert.equal(answerOutcomeLabel(response, 'en'), 'Not supported yet');
});

test('estimated identification leads with the bound backend claim and retains its qualification', () => {
  const response = unavailableAnswer();
  response.parts[0].status = 'partial';
  response.parts[0].result = { claims: [{ quality: 'estimated' }] } as unknown as NonNullable<AnswerResponse['parts'][number]['result']>;
  const claim = { ...response.narrative![0], id: 'identification', kind: 'claim' as const,
    text: 'Likely Zimmer 4.02. Size comparison is unverified.', claim_ids: ['room'], anchor_ids: ['room-box'], qualification: 'estimated' as const };
  response.narrative!.unshift(claim);
  const presented = partAnswerPresentation(response, 'area', 'en');
  assert.deepEqual(presented.claims, [claim]);
  assert.equal(presented.message, null);
  assert.equal(presented.claims[0].text, claim.text);
  assert.deepEqual(presented.claims[0].anchor_ids, ['room-box']);
  assert.equal(answerOutcomeLabel(response, 'en'), 'Estimate');
  assert.equal(answerOutcomeLabel(response, 'fi'), 'Arvio');
  assert.ok(presented.notes.includes('No source-backed area is available for room 121.A.'));
});

test('all answer claims remain visible without truncating long source identifiers or extra parts', () => {
  const response = unavailableAnswer();
  const claim = { ...response.narrative![0], kind: 'claim' as const, text: '121.A — ' + 'Original source identifier '.repeat(15),
    claim_ids: ['source'], qualification: 'exact' as const };
  response.narrative = [claim, { ...claim, id: 'second', text: '7.16' }];
  const presented = partAnswerPresentation(response, 'area', 'en');
  assert.equal(presented.claims.length, 2);
  assert.equal(presented.claims[0].text, claim.text);
  assert.equal(presented.claims[1].text, '7.16');
});

test('an empty unresolved scan never becomes a zero or an estimate label', () => {
  const response = unavailableAnswer();
  response.parts[0].status = 'incomplete_coverage';
  response.narrative = [];
  response.parts[0].message = undefined;
  const presented = partAnswerPresentation(response, 'area', 'en');
  assert.equal(presented.message, 'The scan does not establish a reliable total yet.');
  assert.deepEqual(presented.claims, []);
  assert.equal(answerOutcomeLabel(response, 'en'), 'Not verified');
});

function membershipAnswer(): AnswerResponse {
  const response = unavailableAnswer();
  const policy = { grain: 'schedule_row', hierarchy: 'all_matches', distinct_by: 'canonical_entity_id', rule_key: 'source.rows' };
  const rule = 'schedule.decimal_aggregate.v1:{"filters":[{"column":"Type","literal":"121.A","exclude":false}]}';
  const result = {
    claims: [{ id: 'claim', evidence: [{ calculation_id: 'final' }], coverage_ids: ['coverage'] }],
    calculations: [{ id: 'select', included_set_id: 'all-rows' },
      { id: 'final', included_set_id: 'chosen', excluded_set_id: 'omitted', rule_key: rule }],
    entity_sets: [{ id: 'all-rows', count: 3, entity_ids: ['row-a', 'row-b', 'unknown'], count_policy: policy },
      { id: 'chosen', count: 1, entity_ids: ['row-a'], count_policy: policy },
      { id: 'omitted', count: 1, entity_ids: ['row-b'], count_policy: policy }],
    issues: [{ code: 'missing_information', entity_ids: ['unknown'] }],
  };
  const provenance = (anchorIds: string[], method = 'native') => ({ anchor_ids: anchorIds, method, run_id: 'source-run' });
  response.parts = [{ key: 'area', status: 'partial', result } as unknown as AnswerResponse['parts'][number]];
  response.evidence_contexts = [{ id: 'context', source_snapshot: { ...request.snapshot! }, bundle: {
    assets: [{ id: 'original', sha256: originalHash, uri: '/api/v1/sources/source-test', format: 'pdf' },
      { id: 'display', sha256: displayHash, uri: '/api/v1/sources/source-test/display', format: 'png' }],
    entities: [{ id: 'row-a', labels: [{ text: '121.A | 2 | 3' }], provenance: provenance(['native-a', 'display-a']) },
      { id: 'row-b', labels: [{ text: '7.16 | 4 | 2' }], provenance: provenance(['native-b', 'display-b']) },
      { id: 'unknown', labels: [{ text: '未確定' }], provenance: provenance(['display-b'], 'detected') }],
    facts: [{ id: 'fact-a', subject_id: 'row-a', property_key: 'Type', status: 'present', value: { kind: 'text', value: { text: '121.A' } }, provenance: provenance(['native-a']) },
      { id: 'fact-b', subject_id: 'row-b', property_key: 'Type', status: 'present', value: { kind: 'text', value: { text: '7.16' } }, provenance: provenance(['native-b']) },
      { id: 'fact-unknown', subject_id: 'unknown', property_key: 'QTY', status: 'not_extracted', value: null, provenance: provenance(['display-b'], 'detected') }],
    anchors: [{ id: 'native-a', asset_id: 'original', geometry_id: 'native-a-box', selector: { kind: 'pdf_span', value: 'span-a' } },
      { id: 'display-a', asset_id: 'display', geometry_id: 'display-a-box', selector: { kind: 'image_region', value: 'span-a' } },
      { id: 'native-b', asset_id: 'original', geometry_id: 'native-b-box', selector: { kind: 'pdf_span', value: 'span-b' } },
      { id: 'display-b', asset_id: 'display', geometry_id: 'display-b-box', selector: { kind: 'image_region', value: 'span-b' } }],
    frames: [{ id: 'native-frame', asset_id: 'original', dimension: 2, space: 'presentation' },
      { id: 'display-frame', asset_id: 'display', dimension: 2, space: 'presentation' }],
    geometries: [{ id: 'native-a-box', frame_id: 'native-frame', shape: { kind: 'box', minimum: [1, 2], maximum: [3, 4] } },
      { id: 'display-a-box', frame_id: 'display-frame', shape: { kind: 'box', minimum: [20, 40], maximum: [60, 80] } },
      { id: 'native-b-box', frame_id: 'native-frame', shape: { kind: 'box', minimum: [5, 6], maximum: [7, 8] } },
      { id: 'display-b-box', frame_id: 'display-frame', shape: { kind: 'box', minimum: [100, 120], maximum: [140, 160] } }],
    coverage: [{ id: 'coverage', unresolved_entity_ids: ['row-a'], explanation: 'Observation membership remains unverified.' }],
    representations: [],
  } } as unknown as NonNullable<AnswerResponse['evidence_contexts']>[number]];
  response.parts[0].evidence_context_id = 'context';
  return response;
}

test('member evidence preserves final included/excluded roles, intermediate sets and unresolved source statuses', () => {
  const response = membershipAnswer();
  const groups = partMemberGroups(response, 'area');
  assert.deepEqual(groups.map((group) => [group.role, group.count]), [['intermediate', 3], ['included', 1], ['excluded', 1], ['unresolved', 1], ['unresolved', 1]]);
  assert.equal(groups.find((group) => group.role === 'included')?.members[0].label, '121.A | 2 | 3');
  const excluded = groups.find((group) => group.role === 'excluded')!;
  assert.equal(excluded.members[0].label, '7.16 | 4 | 2');
  assert.equal(excluded.members[0].facts[0].value?.kind, 'text');
  assert.match(excluded.rules[0], /"column":"Type","literal":"121.A"/);
  const unresolved = groups.find((group) => group.members[0]?.label === '未確定')!;
  assert.equal(unresolved.members[0].facts[0].status, 'not_extracted');
  assert.equal(unresolved.members[0].facts[0].value, null);
  assert.equal(unresolved.members[0].method, 'detected');
});

test('compound member anchors resolve each context without an embedded candidate response and keep native PDF frames separate', () => {
  const response = membershipAnswer();
  assert.equal(response.candidate_response, undefined);
  const anchors = anchorEvidence(response, 'area', ['native-a', 'display-a']);
  assert.equal(anchors[0].box, undefined);
  assert.equal(anchors[0].sourceUrl, '/api/v1/sources/source-test#page=2');
  assert.deepEqual(anchors[1].box, [20, 40, 60, 80]);
  response.evidence_contexts![0]!.source_snapshot!.page_index = 2;
  const otherPage = anchorEvidence(response, 'area', ['native-a', 'display-a']);
  assert.ok(otherPage.every((location) => location.box === undefined));
  assert.equal(otherPage[0].sourceUrl, '/api/v1/sources/source-test#page=3');
});

test('large source member sets retain every materialized member before display pagination', () => {
  const response = membershipAnswer();
  const included = response.parts[0].result!.entity_sets!.find((set) => set.id === 'chosen')!;
  included.entity_ids = Array.from({ length: 137 }, (_, index) => `source-row-${index}`);
  included.count = 137;
  const group = partMemberGroups(response, 'area').find((item) => item.role === 'included')!;
  assert.equal(group.count, 137);
  assert.equal(group.members.length, 137);
  assert.equal(group.members[136].id, 'source-row-136');
});
