import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  estimateTokenCost, formatEstimatedUsd, formatResponseTime, modelName, modelRates,
} from './responseMetrics.ts';

const completed = '2026-11-14T18:00:00Z';

test('estimate charges actual input and output tokens at the returned model rates', () => {
  assert.deepEqual(estimateTokenCost('gemini-4-hydrogen', 1000, 200, completed), {
    inputUsd: 0.0015, outputUsd: 0.0015, totalUsd: 0.003,
  });
  assert.deepEqual(estimateTokenCost('gemini-4-carbon', 1000, 200, completed), {
    inputUsd: 0.002, outputUsd: 0.002, totalUsd: 0.004,
  });
});

test('Carbon promotional pricing ends at December 1 UTC; earlier responses retain their rates', () => {
  const before = '2026-11-30T23:59:59.999Z';
  const after = '2026-12-01T00:00:00Z';
  assert.equal(estimateTokenCost('gemini-4-carbon', 1000, 200, before)?.totalUsd, 0.004);
  assert.equal(estimateTokenCost('gemini-4-carbon', 1000, 200, after)?.totalUsd, 0.008);
  assert.equal(estimateTokenCost('gemini-4-carbon', 1000, 200, before)?.totalUsd, 0.004);
  assert.equal(estimateTokenCost('gemini-4-hydrogen', 1000, 200, after)?.totalUsd, 0.003);
});

test('missing and invalid usage never become a zero cost; reported zero remains zero', () => {
  for (const value of [null, undefined, -1, NaN, Infinity, 1.5, Number.MAX_SAFE_INTEGER + 1]) {
    assert.equal(estimateTokenCost('gemini-4-hydrogen', value, 200, completed), null);
    assert.equal(estimateTokenCost('gemini-4-hydrogen', 1000, value, completed), null);
  }
  assert.deepEqual(estimateTokenCost('gemini-4-hydrogen', 0, 0, completed), {
    inputUsd: 0, outputUsd: 0, totalUsd: 0,
  });
});

test('unknown model IDs and unverified dates never inherit a Gemini price', () => {
  for (const model of ['nemotron', 'other-model', 'gemini-4-hydrogen-unknown', 'constructor', '__proto__']) {
    assert.equal(modelRates(model, completed), null);
    assert.equal(estimateTokenCost(model, 1000, 200, completed), null);
    assert.equal(modelName(model), model);
  }
  assert.equal(modelRates('gemini-4-hydrogen', 'invalid date'), null);
  assert.equal(modelRates('gemini-4-hydrogen', '2026-11-13T23:59:59Z'), null);
  assert.equal(modelName('gemini-4-hydrogen'), 'Gemini 4 Hydrogen');
  assert.equal(modelName('gemini-4-carbon'), 'Gemini 4 Carbon');
});

test('sub-cent estimates stay visible without presenting tiny nonzero costs as free', () => {
  assert.equal(formatEstimatedUsd(0.003, 'en'), '$0.0030');
  assert.equal(formatEstimatedUsd(0.0000015, 'en'), '<$0.0001');
  assert.equal(formatEstimatedUsd(0, 'en'), '$0.00');
  assert.match(formatEstimatedUsd(0.003, 'fi'), /0,0030/);
});

test('response time shows milliseconds or seconds in the selected language', () => {
  assert.equal(formatResponseTime(0, 'en'), '0 ms');
  assert.equal(formatResponseTime(123, 'en'), '123 ms');
  assert.equal(formatResponseTime(3824, 'en'), '3.8 s');
  assert.equal(formatResponseTime(3824, 'fi'), '3,8 s');
  for (const value of [NaN, Infinity, -1])
    assert.equal(formatResponseTime(value, 'en'), 'Not recorded');
});

test('mixed-model accounting uses each call timestamp and keeps failed/missing usage unknown', async () => {
  const { estimateCallCosts } = await import('./responseMetrics.ts');
  const base = { id: 'routing', purpose: 'routing' as const, requested_model: 'gemini-decision-1',
    returned_model: 'gemini-decision-1', input_sha256: 'a'.repeat(64), input_width: 800, input_height: 400,
    elapsed_ms: 100, completed_at: completed, outcome: 'completed' as const, prompt_tokens: 1000, completion_tokens: 0 };
  const carbon = { ...base, id: 'analysis', purpose: 'analysis' as const, requested_model: 'gemini-4-carbon', returned_model: 'gemini-4-carbon',
    prompt_tokens: 1000, completion_tokens: 200 };
  assert.deepEqual(estimateCallCosts([base, carbon]), { knownUsd: 0.0041, unknownCalls: 0 });
  assert.deepEqual(estimateCallCosts([base, { ...carbon, outcome: 'failed', prompt_tokens: null }]), { knownUsd: 0.0001, unknownCalls: 1 });
  assert.deepEqual(estimateCallCosts([base, { ...carbon, completed_at: '2026-12-01T00:00:00Z' }]), { knownUsd: 0.0081, unknownCalls: 0 });
});

test('detail tool cost uses Hydrogen layout and Carbon detection rates separately', async () => {
  const { estimateCallCosts } = await import('./responseMetrics.ts');
  const base = { input_sha256: 'a'.repeat(64), input_width: 300, input_height: 200,
    source_box: [40, 20, 340, 220] as [number, number, number, number],
    elapsed_ms: 100, completed_at: completed, outcome: 'completed' as const,
    prompt_tokens: 1000, completion_tokens: 200 };
  const result = estimateCallCosts([
    { ...base, id: 'layout', purpose: 'region_proposal', requested_model: 'gemini-4-hydrogen', returned_model: 'gemini-4-hydrogen' },
    { ...base, id: 'detect', purpose: 'analysis', requested_model: 'gemini-4-carbon', returned_model: 'gemini-4-carbon' },
    { ...base, id: 'verify', purpose: 'candidate_verification', requested_model: 'gemini-4-carbon', returned_model: 'gemini-4-carbon' },
    { ...base, id: 'reinspect', purpose: 'reinspection', requested_model: 'gemini-4-carbon', returned_model: 'gemini-4-carbon' },
  ]);
  assert.equal(result.unknownCalls, 0);
  assert.ok(Math.abs(result.knownUsd - 0.015) < 1e-12);
});
