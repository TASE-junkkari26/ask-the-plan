import type { IfcModelResponse } from '../contracts/IfcModelResponse';
import type { IfcQuestionRequest } from '../contracts/IfcQuestionRequest';
import type { IfcQuestionResponse } from '../contracts/IfcQuestionResponse';

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function text(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}
function sha256(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
}
function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}
function localized(value: unknown) {
  return object(value) && typeof value.text === 'string';
}
function answerValue(value: unknown, depth = 0): boolean {
  if (!object(value) || depth > 12) return false;
  switch (value.kind) {
    case 'count': return Number.isSafeInteger(value.value) && (value.value as number) >= 0;
    case 'quantity': return typeof value.magnitude === 'string' && /^-?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(value.magnitude)
      && typeof value.basis === 'string' && (value.unit_id == null || text(value.unit_id));
    case 'text': return localized(value.value);
    case 'boolean': return typeof value.value === 'boolean';
    case 'references': return strings(value.entity_ids);
    case 'unavailable': return text(value.reason) && typeof value.explanation === 'string';
    case 'list': return Array.isArray(value.items) && value.items.every((item) => answerValue(item, depth + 1));
    case 'record': return object(value.fields) && Object.values(value.fields).every((item) => answerValue(item, depth + 1));
    case 'table': return Array.isArray(value.columns) && value.columns.every((column) => object(column) && text(column.key) && localized(column.label))
      && Array.isArray(value.rows) && value.rows.every((row) => object(row) && (value.columns as Record<string, unknown>[]).every((column) => answerValue(row[String(column.key)], depth + 1)));
    default: return false;
  }
}

export class IfcApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function jsonRequest(url: string, init: RequestInit, signal: AbortSignal): Promise<unknown> {
  signal.throwIfAborted();
  let response: Response;
  try {
    response = await fetch(url, { ...init, signal });
  } catch {
    signal.throwIfAborted();
    throw new Error('The IFC analysis service is unavailable. Start the Python backend and try again.');
  }
  signal.throwIfAborted();
  let value: unknown;
  try {
    value = await response.json();
  } catch {
    signal.throwIfAborted();
    throw new IfcApiError(`The IFC service returned unreadable data (HTTP ${response.status}). Check that the backend is running and the /api proxy can reach it.`, response.status);
  }
  signal.throwIfAborted();
  if (!response.ok) {
    const message = object(value) && text(value.message) ? value.message
      : object(value) && text(value.detail) ? value.detail
        : 'The IFC analysis request failed. Please try again.';
    throw new IfcApiError(message.slice(0, 2000), response.status);
  }
  return value;
}

export async function uploadIfcModel(file: File, sourceHash: string, signal: AbortSignal): Promise<IfcModelResponse> {
  if (!sha256(sourceHash)) throw new Error('Wait until the IFC source identity has been verified.');
  const body = new FormData();
  body.append('file', file, file.name);
  body.append('source_sha256', sourceHash);
  const value = await jsonRequest('/api/ifc/models', { method: 'POST', body }, signal);
  if (!object(value) || value.schema_version !== '0.1.0' || !text(value.model_id)
      || !sha256(value.source_sha256) || value.source_sha256 !== sourceHash
      || !text(value.ifc_schema) || !Number.isSafeInteger(value.entity_count) || (value.entity_count as number) < 0
      || !Array.isArray(value.warnings) || !value.warnings.every(text))
    throw new Error('The IFC analysis service returned a different or invalid source revision.');
  return value as unknown as IfcModelResponse;
}

/** Validate identities before server evidence can be attached to local geometry. */
export function validateIfcAnswer(value: unknown, request: IfcQuestionRequest): IfcQuestionResponse {
  const invalid = () => new Error('The IFC analysis service returned invalid evidence. Please ask again.');
  if (!object(value) || value.schema_version !== '0.1.0' || !text(value.request_id)
      || value.model_id !== request.model_id || value.source_sha256 !== request.source_sha256
      || value.question !== request.question || value.scope !== (request.scope ?? 'view'))
    throw new Error('The IFC answer belongs to a different source, question, or scope. Please ask again.');
  if (!text(value.scope_label) || typeof value.interpretation !== 'string'
      || !object(value.result) || !['answered', 'partial', 'needs_clarification', 'missing_source', 'missing_information', 'incomplete_coverage', 'unsupported_operation', 'conflicting_evidence', 'insufficient_calibration', 'execution_error'].includes(String(value.result.status))
      || !Array.isArray(value.result.claims) || !Array.isArray(value.result.calculations)
      || !Array.isArray(value.result.entity_sets) || !Array.isArray(value.result.issues)
      || !Array.isArray(value.included_elements) || !Array.isArray(value.excluded_elements)
      || !Array.isArray(value.facts) || !Array.isArray(value.anchors) || !Array.isArray(value.units)
      || !Array.isArray(value.warnings) || !value.warnings.every(text)) throw invalid();
  for (const claim of value.result.claims) {
    if (!object(claim) || !text(claim.id) || !answerValue(claim.value)) throw invalid();
    if (claim.count_policy != null && (!object(claim.count_policy) || !text(claim.count_policy.grain)
      || !text(claim.count_policy.hierarchy) || !text(claim.count_policy.distinct_by))) throw invalid();
  }
  for (const calculation of value.result.calculations) {
    if (!object(calculation) || !text(calculation.id) || !text(calculation.operation) || !answerValue(calculation.output)
      || (calculation.fact_ids !== undefined && !strings(calculation.fact_ids))
      || (calculation.input_node_ids !== undefined && !strings(calculation.input_node_ids))) throw invalid();
  }
  for (const issue of value.result.issues) {
    if (!object(issue) || !localized(issue.message) || (issue.options !== undefined && (!Array.isArray(issue.options) || !issue.options.every(localized)))) throw invalid();
  }
  if (value.result.explanation != null && !localized(value.result.explanation)) throw invalid();
  for (const fact of value.facts) {
    if (!object(fact) || !text(fact.id) || !text(fact.property_key) || !text(fact.status)
      || !object(fact.provenance) || (fact.provenance.anchor_ids !== undefined && !strings(fact.provenance.anchor_ids))
      || (fact.original_property_path !== undefined && !strings(fact.original_property_path))
      || (fact.value != null && !answerValue(fact.value))) throw invalid();
  }
  for (const anchor of value.anchors) {
    if (!object(anchor) || !text(anchor.id) || !object(anchor.selector) || !text(anchor.selector.kind)
      || !text(anchor.selector.value) || (anchor.selector.property_path !== undefined && !strings(anchor.selector.property_path))) throw invalid();
  }
  for (const unit of value.units) {
    if (!object(unit) || !text(unit.id) || typeof unit.symbol !== 'string') throw invalid();
  }
  const visible = (request.scope ?? 'view') === 'view' ? new Set(request.visible_step_ids ?? []) : null;
  for (const key of ['included_elements', 'excluded_elements'] as const) {
    const ids = new Set<string>();
    for (const element of value[key] as unknown[]) {
      if (!object(element) || !text(element.entity_id) || ids.has(element.entity_id)
          || !(element.step_id === null || (Number.isSafeInteger(element.step_id) && (element.step_id as number) > 0))
          || !(element.guid === null || text(element.guid)) || !text(element.ifc_class)
          || typeof element.name !== 'string') throw invalid();
      if (key === 'included_elements' && visible && !visible.has(element.step_id as number))
        throw new Error('The IFC answer contains elements outside the submitted view. Please ask again.');
      ids.add(element.entity_id);
    }
  }
  return value as unknown as IfcQuestionResponse;
}

export async function askIfcQuestion(request: IfcQuestionRequest, signal: AbortSignal): Promise<IfcQuestionResponse> {
  if (!request.question.trim() || request.question.length > 4000) throw new Error('Enter a question with 1 to 4000 characters.');
  if ((request.scope ?? 'view') === 'view' && !Array.isArray(request.visible_step_ids))
    throw new Error('The current view has not been captured. Please try again.');
  const value = await jsonRequest('/api/ifc/questions', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request),
  }, signal);
  return validateIfcAnswer(value, request);
}
