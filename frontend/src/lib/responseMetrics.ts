import type { Language } from '../types';

export const PRICING_SOURCE_URL = 'https://ai.google.dev/gemini-api/docs/pricing';
export const PRICING_VERIFIED_ON = '2026-11-14';

interface TokenRates {
  effectiveFrom: string;
  inputUsdPerMillion: number;
  outputUsdPerMillion: number;
}

interface ModelPricing {
  name: string;
  rates: readonly TokenRates[];
}

// Standard paid Gemini API rates, per 1M tokens. Keep model selection on the
// backend; use the actual returned model to select an estimate here.
export const MODEL_PRICING: Readonly<Record<string, ModelPricing>> = {
  'gemini-4-hydrogen': {
    name: 'Gemini 4 Hydrogen',
    rates: [{ effectiveFrom: '2026-11-14T00:00:00Z', inputUsdPerMillion: 1.5, outputUsdPerMillion: 7.5 }],
  },
  'gemini-4-carbon': {
    name: 'Gemini 4 Carbon',
    rates: [
      { effectiveFrom: '2026-11-14T00:00:00Z', inputUsdPerMillion: 2, outputUsdPerMillion: 10 },
      { effectiveFrom: '2026-12-01T00:00:00Z', inputUsdPerMillion: 4, outputUsdPerMillion: 20 },
    ],
  },
};

export function modelName(model: string): string {
  return Object.hasOwn(MODEL_PRICING, model) ? MODEL_PRICING[model].name : model;
}

/** A response keeps its completion timestamp so later rate changes do not reprice it. */
export function modelRates(model: string, completedAt: string): TokenRates | null {
  if (!Object.hasOwn(MODEL_PRICING, model)) return null;
  const completed = Date.parse(completedAt);
  if (!Number.isFinite(completed)) return null;
  return [...MODEL_PRICING[model].rates].reverse()
    .find((rate) => completed >= Date.parse(rate.effectiveFrom)) ?? null;
}

function reportedTokens(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
}

export function estimateTokenCost(
  model: string,
  inputTokens: number | null | undefined,
  outputTokens: number | null | undefined,
  completedAt: string,
): { inputUsd: number; outputUsd: number; totalUsd: number } | null {
  const rates = modelRates(model, completedAt);
  if (!rates || !reportedTokens(inputTokens) || !reportedTokens(outputTokens)) return null;
  const inputUsd = inputTokens * rates.inputUsdPerMillion / 1_000_000;
  const outputUsd = outputTokens * rates.outputUsdPerMillion / 1_000_000;
  return { inputUsd, outputUsd, totalUsd: inputUsd + outputUsd };
}

export function formatResponseTime(milliseconds: number, language: Language): string {
  if (!Number.isFinite(milliseconds) || milliseconds < 0)
    return language === 'fi' ? 'Ei tallennettu' : 'Not recorded';
  const seconds = milliseconds >= 1000;
  const value = new Intl.NumberFormat(language, {
    minimumFractionDigits: seconds ? 1 : 0,
    maximumFractionDigits: seconds ? 1 : 0,
  }).format(seconds ? milliseconds / 1000 : milliseconds);
  return `${value} ${seconds ? 's' : 'ms'}`;
}

export function formatEstimatedUsd(amount: number, language: Language): string {
  const tiny = amount > 0 && amount < 0.0001;
  const value = new Intl.NumberFormat(language, {
    style: 'currency', currency: 'USD',
    minimumFractionDigits: amount === 0 ? 2 : 4,
    maximumFractionDigits: 4,
  }).format(tiny ? 0.0001 : amount);
  return `${tiny ? '<' : ''}${value}`;
}
