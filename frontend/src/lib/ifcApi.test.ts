import test from 'node:test';
import assert from 'node:assert/strict';
import { askIfcQuestion, uploadIfcModel, validateIfcAnswer } from './ifcApi.ts';
import type { IfcQuestionRequest } from '../contracts/IfcQuestionRequest';

const hash = 'a'.repeat(64);
const request: IfcQuestionRequest = {
  model_id: 'model:test', source_sha256: hash, question: 'How many windows?',
  scope: 'view', visible_step_ids: [10, 20], view_label: 'Ground floor',
};
function answer() {
  return {
    schema_version: '0.1.0', model_id: request.model_id, source_sha256: hash,
    request_id: 'request:test', question: request.question, scope: 'view', scope_label: 'Ground floor',
    interpretation: 'Count window occurrences', included_elements: [{ entity_id: 'window:one', step_id: 10, guid: 'guid-A', name: 'W-1', ifc_class: 'IfcWindow' }], excluded_elements: [],
    facts: [], anchors: [], units: [], warnings: [], result: {
      status: 'answered', claims: [{ id: 'claim:test', value: { kind: 'count', value: 1 } }], calculations: [], entity_sets: [], issues: [],
    },
  };
}

test('IFC evidence must match submitted source, model, question and scope', () => {
  for (const change of [{ source_sha256: 'b'.repeat(64) }, { model_id: 'model:other' }, { question: 'Other?' }, { scope: 'model' }]) {
    assert.throws(() => validateIfcAnswer({ ...answer(), ...change }, request), /different source, question, or scope/);
  }
  assert.equal(validateIfcAnswer(answer(), request).included_elements?.[0].step_id, 10);
});

test('view evidence cannot attach an outside STEP ID, including an explicitly empty view', () => {
  const value = answer();
  value.included_elements[0].step_id = 30;
  assert.throws(() => validateIfcAnswer(value, request), /outside the submitted view/);
  assert.throws(() => validateIfcAnswer(answer(), { ...request, visible_step_ids: [] }), /outside the submitted view/);
  assert.equal(validateIfcAnswer({ ...answer(), scope: 'model' }, { ...request, scope: 'model', visible_step_ids: null }).scope, 'model');
});

test('a verified empty count stays distinct from a missing-information outcome', () => {
  const value = answer();
  value.included_elements = [];
  value.result.claims[0].value.value = 0;
  assert.equal(validateIfcAnswer(value, { ...request, visible_step_ids: [] }).result.claims?.[0].value.kind, 'count');
  value.result.status = 'missing_information';
  value.result.claims = [];
  assert.equal(validateIfcAnswer(value, request).result.status, 'missing_information');
});

test('all generated engine non-answer statuses survive the wire boundary', () => {
  for (const status of ['partial', 'needs_clarification', 'missing_source', 'missing_information', 'incomplete_coverage', 'unsupported_operation', 'conflicting_evidence', 'insufficient_calibration', 'execution_error']) {
    const value = answer();
    value.result.status = status;
    value.result.claims = [];
    assert.equal(validateIfcAnswer(value, request).result.status, status);
  }
});

test('malformed answer values and duplicate element identities are rejected before rendering', () => {
  const value = answer();
  value.included_elements.push(value.included_elements[0]);
  assert.throws(() => validateIfcAnswer(value, request), /invalid evidence/);
  const malformed = answer();
  malformed.result.claims[0].value.value = Number.NaN;
  assert.throws(() => validateIfcAnswer(malformed, request), /invalid evidence/);
});

test('upload binds model handle to original source hash and sends no inference credential', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    assert.equal(url, '/api/ifc/models');
    assert.equal(init?.method, 'POST');
    assert.equal(init?.headers, undefined);
    const body = init?.body as FormData;
    assert.equal(body.get('source_sha256'), hash);
    assert.equal((body.get('file') as File).name, 'source.ifc');
    return Response.json({ schema_version: '0.1.0', model_id: 'model:test', source_sha256: hash, ifc_schema: 'IFC4', entity_count: 2, warnings: [] });
  };
  try {
    const result = await uploadIfcModel(new File(['IFC'], 'source.ifc'), hash, new AbortController().signal);
    assert.equal(result.source_sha256, hash);
    globalThis.fetch = async () => Response.json({ schema_version: '0.1.0', model_id: 'model:test', source_sha256: 'b'.repeat(64), ifc_schema: 'IFC4', entity_count: 2, warnings: [] });
    await assert.rejects(uploadIfcModel(new File(['IFC'], 'source.ifc'), hash, new AbortController().signal), /invalid source revision/);
  } finally { globalThis.fetch = original; }
});

test('question requests retain empty scope and discard an aborted late response', async () => {
  const original = globalThis.fetch;
  const controller = new AbortController();
  globalThis.fetch = async (_url, init) => {
    const payload = JSON.parse(init?.body as string);
    assert.deepEqual(payload.visible_step_ids, []);
    controller.abort();
    return Response.json(answer());
  };
  try {
    await assert.rejects(askIfcQuestion({ ...request, visible_step_ids: [] }, controller.signal), { name: 'AbortError' });
  } finally { globalThis.fetch = original; }
});

test('backend errors and non-JSON proxy failures remain readable', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => Response.json({ message: 'Source expired; upload again.' }, { status: 410 });
    await assert.rejects(askIfcQuestion(request, new AbortController().signal), /Source expired/);
    globalThis.fetch = async () => new Response('<html>Vite fallback</html>', { status: 200 });
    await assert.rejects(askIfcQuestion(request, new AbortController().signal), /backend is running/);
  } finally { globalThis.fetch = original; }
});
