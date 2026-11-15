import { test } from 'node:test';
import assert from 'node:assert/strict';
import { answerCost } from './answerMetrics.ts';
import { estimateTokenCost } from './responseMetrics.ts';
import type { AnswerResponse } from '../contracts/AnswerResponse';

const timestamp = '2026-11-15T00:00:00Z';
const call = (input: number, output: number): NonNullable<AnswerResponse['metrics']['calls']>[number] => ({
  id: `call-${input}`, purpose: 'analysis', requested_model: 'gemini-4-hydrogen',
  returned_model: 'gemini-4-hydrogen', outcome: 'completed', completed_at: timestamp,
  prompt_tokens: input, completion_tokens: output,
});

test('answer and candidate views estimate the same two recorded calls', () => {
  const calls: [ReturnType<typeof call>, ReturnType<typeof call>] = [call(2337, 693), call(2681, 750)];
  const expected = calls.reduce((total, item) => total + estimateTokenCost(
    item.returned_model!, item.prompt_tokens, item.completion_tokens, timestamp)!.totalUsd, 0);
  assert.equal(answerCost({ elapsed_ms: 10850, external_attempts: 2, calls }).amount, expected);
  assert.equal(answerCost({ elapsed_ms: 10850, external_attempts: 2, calls }).unknownCalls, 0);
});

test('unknown usage, dates, tariffs and unrecorded attempts cannot become a complete total', () => {
  for (const unknown of [
    { ...call(17, 2), completion_tokens: null },
    { ...call(17, 2), completed_at: null },
    { ...call(17, 2), returned_model: 'unpriced-model' },
  ]) {
    const result = answerCost({ elapsed_ms: 1, external_attempts: 2, calls: [call(1000, 200), unknown] });
    assert.equal(result.amount, null);
    assert.equal(result.unknownCalls, 1);
    assert.equal(result.knownUsd, 0.003);
  }
  assert.equal(answerCost({ elapsed_ms: 1, external_attempts: 2, calls: [call(1000, 200)] }).amount, null);
});

test('reported currency totals and genuinely local zero-cost work retain their meaning', () => {
  assert.equal(answerCost({ elapsed_ms: 1, external_attempts: 0 }).amount, 0);
  assert.deepEqual(answerCost({ elapsed_ms: 1, cost_amount: '0.50', cost_currency: 'EUR', cost_basis: 'estimated' }),
    { amount: 0.5, currency: 'EUR', estimated: true, unknownCalls: 0, knownUsd: 0 });
});
