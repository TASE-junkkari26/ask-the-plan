import type { AnswerResponse } from '../contracts/AnswerResponse';
import { estimateTokenCost } from './responseMetrics.ts';

/** Use the same recorded model/timestamp tariff as the candidate panel. */
export function answerCost(metrics: AnswerResponse['metrics']): {
  amount: number | null; currency: string | null; estimated: boolean;
  unknownCalls: number; knownUsd: number;
} {
  if (metrics.cost_amount != null && metrics.cost_currency) {
    const amount = Number(metrics.cost_amount);
    if (Number.isFinite(amount) && amount >= 0)
      return { amount, currency: metrics.cost_currency, estimated: metrics.cost_basis === 'estimated',
        unknownCalls: 0, knownUsd: metrics.cost_currency === 'USD' ? amount : 0 };
  }
  const calls = metrics.calls ?? [];
  let knownUsd = 0;
  let unknownCalls = Math.max(0, (metrics.external_attempts ?? 0) - calls.length);
  for (const call of calls) {
    const cost = estimateTokenCost(call.returned_model ?? call.requested_model,
      call.prompt_tokens, call.completion_tokens, call.completed_at ?? '');
    if (cost) knownUsd += cost.totalUsd;
    else unknownCalls++;
  }
  return { amount: unknownCalls ? null : knownUsd, currency: unknownCalls ? null : 'USD',
    estimated: true, unknownCalls, knownUsd };
}
