"""Common orchestration around the existing source executors.

No reference QA, model answer numbers, browser-supplied facts, or free-form answer
writer are accepted here. Each successful part keeps its plan and evidence.
"""
from __future__ import annotations

import asyncio
from copy import copy
import hashlib
import re
from time import perf_counter
from uuid import uuid4

from contracts import models as m
from image_api.errors import ApiError
from ifc_api.service import InvalidProposal, PlanProposal, _model_title_conflict, _native_work
from ifc_api.providers import PlannerReply, PlannerUsage
from ifc_engine.engine import QueryError
from .budget import AnswerBudget, BudgetPlanner
from .intent import language, needs_entire_ifc, requested_parts, is_count_question


def visual_identification(question):
    """Recognize bounded visual matching, without promising measured rankings.

    Values, physical properties and relations still need their native executor.
    This hint selects an evidence type; it never chooses or ranks image boxes.
    """
    if is_count_question(question) or re.search(
        r"\b(area|volume|length|height|width|depth|perimeter|distance|dimensions?|net|gross|"
        r"material|rating|cost|price|route|connected|adjacent|external|internal|compliance|"
        r"pinta-ala|tilavuus|pituus|korkeus|leveys)\b|m[²³]|\b(?:m2|m3|mm)\b", question, re.I):
        return None
    subject = r"\b(room|rooms|roo|space|spaces|door|doors|window|windows|huone|huoneista|tila|ovi|ikkuna|raum|zimmer|pièce|stanza|locale)\b"
    rank = r"(?:largest|smallest|biggest|bigger|smaller|suurin|pienin|größte|grösste|kleinste|plus\s+(?:grand|petit)|più\s+(?:grande|piccol))"
    ranking_lead = rf"^\s*(?:{rank}\b|(?:which|what)\s+(?:is\s+)?(?:the\s+)?(?:room|space|{rank})\b|(?:find|locate|identify|show(?:\s+me)?)\s+(?:the\s+)?{rank}\b)"
    if re.search(subject, question, re.I) and re.search(rf"\b{rank}\b", question, re.I) and re.match(ranking_lead, question, re.I):
        return "rank"
    location = re.match(r"^\s*(?:where\s+(?:is|are)|find|locate|identify|show(?:\s+me)?|missä|näytä|etsi)\s+(.+?)[?.!]*$", question, re.I)
    if location:
        # Keep positive location routing narrow: a class, literal source label
        # or source-like identifier. Extra prose can contain a property/relation
        # request which this adapter cannot execute.
        target = re.sub(r"^(?:the|a|an)\s+", "", location.group(1), flags=re.I)
        literal = r'''["“«][^"”»]+["”»]'''
        identifier = r"(?=[\w.\-]*\d)[\w]+(?:[.\-][\w]+)*"
        kind = r"(?:room|rooms|space|spaces|door|doors|window|windows|kitchen|bathroom|huone|tila|ovi|ikkuna|keittiö)"
        if re.fullmatch(rf"(?:{kind}(?:\s+(?:{literal}|{identifier}))?|{literal}|{identifier})", target, re.I):
            return "match"
    return None


def unavailable(key, status, message, dependencies=()):
    return m.AnswerPart(key=key, status=status, message=m.LocalizedText(text=message), depends_on=list(dependencies))


def planning_reason(status):
    # Planner explanations are proposals, not facts about source absence.
    return {
        'missing_information': 'The bounded planner could not resolve required source inputs. This does not establish that those inputs are absent from the model.',
        'missing_source': 'A required registered source was not identified for this part. No substitute source was used.',
        'unsupported_operation': 'This part has no validated executable route in the local toolset; it remains an implementation gap.',
        'needs_clarification': 'The source identifiers, scope or required inputs could not be resolved into a validated plan. Clarify this part.',
    }.get(status, 'A validated executable answer could not be produced for this part.')


async def cpu_work(function, *args):
    """Native execution finishes before callers may release source leases."""
    return await _native_work(function, *args)


class AnswerService:
    def __init__(self, documents, ifc_service, *, deadline_seconds=180):
        self.documents, self.ifc = documents, ifc_service
        self.deadline_seconds = deadline_seconds

    async def answer(self, request, request_id, *, visual=None, on_handoff=None):
        budget = AnswerBudget(self.deadline_seconds)
        if request.model_id:
            return await self._ifc(request, request_id, budget)
        with self.documents.lease(request.source_id) as session:
            if request.source_sha256 != session.source_sha256:
                raise ApiError(409, 'source_mismatch', 'The question refers to a different original source revision.')
            captured = m.AnswerSnapshot.model_validate(session.public()['snapshot'])
            if request.snapshot is not None and request.snapshot != captured:
                raise ApiError(409, 'snapshot_mismatch', 'The page/layout or displayed snapshot changed. Register the selected snapshot again.')
            label = (f'{session.filename} · {captured.layout_name}' if captured.layout_name
                     else f'{session.filename} · page {(captured.page_index or 0) + 1}')
            source = m.AnswerSourceBinding(**captured.model_dump(), source_id=session.source_id,
                kind=session.format if session.format in {'pdf', 'svg', 'dxf'} else 'image', scope_label=label)
            intent = m.AnswerIntent(language=language(request.question, request.language), scope_label=label,
                                    requested_parts=requested_parts(request))
            parts, contexts, candidate = [], [], None
            for part in intent.requested_parts:
                failed = [key for key in part.depends_on if next(p for p in parts if p.key == key).status != 'answered']
                if failed:
                    parts.append(unavailable(part.key, 'blocked', 'A required input part did not produce a complete answer.', part.depends_on))
                    continue
                if needs_entire_ifc(part.question):
                    parts.append(unavailable(part.key, 'missing_source',
                        'This question requires the entire IFC model. No provenance-backed link to a registered IFC model is available for this drawing.', part.depends_on))
                    continue
                # Native document operations use original registered bytes. A
                # lookup or table query must resolve literal source cells before
                # it can produce a fact. Pixel detections remain proposals.
                from .native import answer_native
                native = await answer_native(session, part, source, request_id, budget,
                                             self.ifc.planner, intent.language)
                if native is not None:
                    native_part, context = native
                    native_part.depends_on = part.depends_on
                    parts.append(native_part)
                    if context is not None:
                        contexts.append(context)
                    continue
                if request.plans:
                    parts.append(unavailable(part.key, 'unsupported_operation',
                        'Direct drawing query plans require native facts supported by the registered document adapter.', part.depends_on))
                    continue
                if visual is None:
                    parts.append(unavailable(part.key, 'unsupported_operation', 'No visual analyzer is configured for this drawing.', part.depends_on))
                    continue
                try:
                    budget.check(2)  # one selected detector and optional Decisions call
                    observed = await asyncio.wait_for(visual(session, part.question, request_id, budget,
                        detail=request.detail, on_handoff=on_handoff),
                        timeout=max(.001, budget.remaining - .1))
                    from .adapters import candidate_part
                    identification = visual_identification(part.question) if part.operation == 'auto' else None
                    answer_part, context = candidate_part(observed, source, request_id, part_key=part.key,
                                                         identification=identification)
                    if identification is None and part.operation not in {'count', 'inventory_count'} and not is_count_question(part.question):
                        # Detection boxes are not source values, dimensions or
                        # answers to an unrelated requested operation.
                        answer_part = m.AnswerPart(key=part.key, status='unsupported_operation',
                            evidence_context_id=context.id, result=m.QueryResult(id='result:' + uuid4().hex,
                                request_id=request_id, status='unsupported_operation', executor_version='drawing-observations-1',
                                issues=[m.Issue(code='unsupported_operation', anchor_ids=[anchor.id for anchor in context.bundle.anchors],
                                    message=m.LocalizedText(text='The visual tool located candidate source regions, but it did not extract or execute the requested property, quantity or relation. That answer tool remains an implementation gap.'))]))
                    answer_part.depends_on = part.depends_on
                    parts.append(answer_part)
                    contexts.append(context)
                    # The legacy response is a single-question overlay. Compound
                    # observations keep their own evidence contexts instead.
                    if part.question == request.question:
                        candidate = observed
                except ApiError as exc:
                    parts.append(unavailable(part.key, 'execution_error', exc.message, part.depends_on))
                except asyncio.TimeoutError:
                    parts.append(unavailable(part.key, 'execution_error', 'The shared question deadline expired before this part completed.', part.depends_on))
            return self._finish(request, request_id, source, intent, parts, contexts, budget, candidate=candidate)

    @staticmethod
    def _finish(request, request_id, source, intent, parts, contexts, budget, *, candidate=None, ifc=None):
        from .realize import realize_answer
        from contracts.validation import validate_answer
        response = m.AnswerResponse(request_id=request_id, question=request.question,
            question_sha256=hashlib.sha256(request.question.encode('utf-8')).hexdigest(), source=source,
            interpretation=intent, parts=parts, evidence_contexts=contexts,
            metrics=budget.metrics(), candidate_response=candidate, ifc_response=ifc)
        response.narrative = realize_answer(response)
        validate_answer(response)
        return response

    async def _ifc(self, request, request_id, budget):
        service = self.ifc
        if service._gate.locked():
            raise ApiError(429, 'busy', 'IFC service is busy; try again later.', True)
        async with service._gate:
            with service._lock:
                model = service._model(request.model_id, request.source_sha256)
                model.active += 1
            try:
                source = m.AnswerSourceBinding(source_id=model.model_id, kind='ifc',
                    source_sha256=model.sha256, source_revision=model.sha256, scope_label='Entire model')
                intent = m.AnswerIntent(language=language(request.question, request.language), scope_label=source.scope_label,
                                        requested_parts=requested_parts(request))
                ifc_request = m.IfcQuestionRequest(model_id=model.model_id, source_sha256=model.sha256,
                                                  question=request.question, scope='model')
                plans, missing = {}, {}
                reply = PlannerReply(text='', model='no-model-call', usage=PlannerUsage(prompt_tokens=0, completion_tokens=0))
                source_error = None
                try:
                    # One hydration/work budget spans planning and every output.
                    # Earlier part evidence survives until the union is exported.
                    await cpu_work(model.engine.clear_hydration)
                    conflict = await cpu_work(_model_title_conflict, model.engine, request.question, True)
                except QueryError as exc:
                    source_error = exc
                    conflict = None
                if source_error:
                    status = source_error.code if source_error.code in {'missing_source', 'unsupported_operation', 'needs_clarification', 'incomplete_coverage', 'missing_information'} else 'execution_error'
                    proposal = PlanProposal(status='missing_information', interpretation=planning_reason(status),
                        explicitly_requests_entire_model=True, steps=[])
                    missing = {part.key: unavailable(part.key, status, planning_reason(status)) for part in intent.requested_parts}
                    reply = service._native_reply()
                elif conflict:
                    proposal = PlanProposal(status='needs_clarification', interpretation=conflict,
                        explicitly_requests_entire_model=True, steps=[])
                    missing = {part.key: unavailable(part.key, 'needs_clarification', conflict)
                               for part in intent.requested_parts}
                    reply = service._native_reply()
                elif request.plans:
                    plans = {key: plan.model_copy(update={'id': 'plan:' + uuid4().hex, 'request_id': request_id})
                             for key, plan in request.plans.items()}
                    proposal = PlanProposal(status='missing_information', interpretation='Validated direct query plans.',
                                            explicitly_requests_entire_model=True, steps=[])
                else:
                    proxy = copy(service)
                    if service.planner is not None:
                        proxy.planner = BudgetPlanner(service.planner, budget)
                    context = {'answer_parts': True, 'requested_parts': [part.model_dump() for part in intent.requested_parts]}
                    repair = None
                    proposal = None
                    for attempt in range(2):
                        try:
                            compiled = None
                            if (attempt == 0 and len(intent.requested_parts) == 1 and service.settings.fast_plans
                                    and not getattr(service, 'configuration_error', None)):
                                from ifc_api.fast_plans import try_plan
                                compiled = await cpu_work(try_plan, model.engine, request.question,
                                    service._scope_members(model, ifc_request))
                                if compiled is not None and len(compiled.get('outputs', {})) > 1 and request.parts is not None:
                                    # A host-supplied part key cannot be silently
                                    # replaced by several native output keys.
                                    compiled = None
                            if compiled is not None:
                                proposal = PlanProposal.model_validate(compiled)
                                reply = service._native_reply()
                                if proposal.status == 'ready':
                                    if len(proposal.outputs) > 1:
                                        proposal = proposal.model_copy(update={'requested_parts': [
                                            m.AnswerRequestedPart(key=key, question=request.question) for key in proposal.outputs]})
                                    else:
                                        output = proposal.output_step_id or next(iter(proposal.outputs.values()))
                                        proposal = proposal.model_copy(update={'output_step_id': None,
                                            'outputs': {intent.requested_parts[0].key: output}})
                            else:
                                proposal, reply = await asyncio.wait_for(proxy._propose(model, ifc_request, repair, context),
                                                                         timeout=max(.001, budget.remaining - .1))
                            if proposal.status == 'ready':
                                outputs = proposal.outputs or {'answer': proposal.output_step_id}
                                # Compile every requested output before executing
                                # any part, then isolate its dependency closure.
                                if request.parts is None and len(intent.requested_parts) == 1:
                                    if proposal.requested_parts:
                                        intent.requested_parts = proposal.requested_parts
                                    elif set(outputs) | {part.key for part in proposal.unavailable_parts} != {'answer'}:
                                        # Compatibility for older planners: keep
                                        # the unresolved original request visible
                                        # beside additional executed outputs.
                                        keys = [key for key in [*outputs, *(part.key for part in proposal.unavailable_parts)]
                                                if key != 'answer']
                                        intent.requested_parts.extend(m.AnswerRequestedPart(key=key, question=key) for key in keys)
                                invalid = []
                                for key, step_id in outputs.items():
                                    try:
                                        steps = self._dependency_steps(proposal.steps, step_id)
                                        candidate = m.QueryPlan(id='plan:' + uuid4().hex, request_id=request_id,
                                            scope=model.engine.scope(), steps=steps, outputs={key: step_id})
                                        part = next((part for part in intent.requested_parts if part.key == key), None)
                                        question = (request.question if len(intent.requested_parts) == 1
                                                    else part.question if part is not None else request.question)
                                        scoped_request = ifc_request.model_copy(update={'question': question})
                                        scoped_proposal = proposal.model_copy(update={'steps': steps, 'outputs': {key: step_id},
                                            'output_step_id': None, 'unanswered_parts': [], 'unavailable_parts': []})
                                        await cpu_work(service._preflight_plan, model, scoped_request, scoped_proposal, candidate)
                                        plans[key] = candidate
                                        missing.pop(key, None)
                                    except (ValueError, InvalidProposal) as exc:
                                        invalid.append(str(exc))
                                        missing[key] = unavailable(key, 'needs_clarification',
                                            'This output did not compile into a valid ordered dependency plan. Clarify its source inputs.')
                                    except QueryError as exc:
                                        status = exc.code if exc.code in {'missing_source', 'unsupported_operation', 'needs_clarification', 'incomplete_coverage', 'missing_information'} else 'execution_error'
                                        missing[key] = unavailable(key, status, planning_reason(status))
                                missing.update({part.key: part for part in proposal.unavailable_parts})
                                # An ignored literal room or invalid reference is
                                # repairable. Valid independent outputs survive.
                                if invalid and not plans:
                                    raise InvalidProposal(invalid[0])
                            else:
                                missing = {part.key: unavailable(part.key, proposal.status, planning_reason(proposal.status))
                                           for part in intent.requested_parts}
                            break
                        except InvalidProposal as exc:
                            repair = str(exc)
                            if attempt == 1 or len(context.get('replies', [])) >= service.settings.max_model_requests:
                                missing = {part.key: unavailable(part.key, 'needs_clarification',
                                    'A source-valid plan could not be formed within the shared planning budget.') for part in intent.requested_parts}
                        except QueryError as exc:
                            status = exc.code if exc.code in {'missing_source', 'unsupported_operation', 'needs_clarification', 'incomplete_coverage', 'missing_information'} else 'execution_error'
                            missing.update({part.key: unavailable(part.key, status, planning_reason(status))
                                            for part in intent.requested_parts if part.key not in plans})
                            break
                        except (ApiError, asyncio.TimeoutError) as exc:
                            message = exc.message if isinstance(exc, ApiError) else 'The shared question deadline expired during planning.'
                            missing = {part.key: unavailable(part.key, 'execution_error', message) for part in intent.requested_parts}
                            break
                parts, contexts, responses, coverage_records = [], [], [], {}
                for part in intent.requested_parts:
                    if any(next(p for p in parts if p.key == key).status != 'answered' for key in part.depends_on):
                        parts.append(unavailable(part.key, 'blocked', 'A required input part failed or is partial.', part.depends_on))
                        continue
                    if part.key in missing:
                        item = missing[part.key]
                        message = item.message.text if isinstance(item, m.AnswerPart) else planning_reason(item.status)
                        parts.append(unavailable(part.key, item.status, message, part.depends_on))
                        continue
                    plan = plans.get(part.key)
                    if plan is None:
                        parts.append(unavailable(part.key, 'needs_clarification',
                            'The planner did not resolve this requested part; clarify its source inputs or scope.', part.depends_on))
                        continue
                    executable_plan = None
                    try:
                        budget.check()
                        expected = model.engine.scope()
                        if (plan.scope.project_id != expected.project_id or plan.scope.document_ids != expected.document_ids
                                or plan.scope.view_ids or plan.scope.universe not in {'modeled_objects', 'source_records'}):
                            raise QueryError('missing_source', 'The executable plan belongs to a different source or drawing view.')
                        scoped_request = ifc_request.model_copy(update={'question': request.question
                            if len(intent.requested_parts) == 1 else part.question})
                        scoped_proposal = proposal.model_copy(update={'steps': plan.steps, 'outputs': plan.outputs,
                            'output_step_id': None, 'unanswered_parts': [], 'unavailable_parts': []})
                        await cpu_work(service._preflight_plan, model, scoped_request, scoped_proposal, plan)
                        executable_plan = plan
                        result = await cpu_work(model.engine.execute, plan)
                    except (QueryError, ValueError, ApiError) as exc:
                        result = model.engine._failure(QueryError(getattr(exc, 'code', 'execution_error')
                            if getattr(exc, 'code', '') in {'missing_source', 'unsupported_operation', 'needs_clarification', 'incomplete_coverage', 'missing_information'} else 'execution_error',
                            str(exc)), request_id, executable_plan.id if executable_plan else None)
                    ctx_id = 'evidence:ifc:' + model.model_id
                    coverage_ids = {identifier for claim in result.claims for identifier in claim.coverage_ids}
                    coverage_records.update({item.id: item for item in model.engine.bundle.coverage if item.id in coverage_ids})
                    parts.append(m.AnswerPart(key=part.key, status=result.status, result=result, plan=executable_plan,
                        evidence_context_id=ctx_id, depends_on=part.depends_on))
                    responses.append(service._response(model, ifc_request,
                        proposal or PlanProposal(status='missing_information', interpretation='Direct query.',
                            explicitly_requests_entire_model=True, steps=[]), executable_plan, result.model_copy(deep=True),
                        request_id, (perf_counter() - budget.started) * 1000, reply))
                if any(part.evidence_context_id is not None for part in parts):
                    from .evidence import prune_ifc_context
                    context_bundle = model.engine.bundle.model_copy(update={'coverage': list(coverage_records.values())})
                    context_bundle = prune_ifc_context(context_bundle,
                        [part.result for part in parts if part.result is not None],
                        [part.plan for part in parts if part.plan is not None])
                    contexts.append(m.AnswerEvidenceContext(id='evidence:ifc:' + model.model_id, bundle=context_bundle))
                legacy = next((item for item in responses if item.result.claims), responses[0] if responses else None)
                if legacy is not None:
                    for field in ('included_elements', 'excluded_elements', 'unresolved_elements', 'facts', 'anchors', 'coverage', 'properties'):
                        values = {}
                        for response in responses:
                            for item in getattr(response, field):
                                identifier = getattr(item, 'entity_id', None) or getattr(item, 'id', None) or item.key
                                values[identifier] = item
                        setattr(legacy, field, list(values.values()))
                    included = {item.entity_id for item in legacy.included_elements}
                    unresolved = {item.entity_id for item in legacy.unresolved_elements} - included
                    legacy.unresolved_elements = [item for item in legacy.unresolved_elements if item.entity_id in unresolved]
                    legacy.excluded_elements = [item for item in legacy.excluded_elements
                                                if item.entity_id not in included | unresolved]
                return self._finish(request, request_id, source, intent, parts, contexts, budget, ifc=legacy)
            finally:
                service._release(model)

    @staticmethod
    def _dependency_steps(steps, output_id):
        if len({step.id for step in steps}) != len(steps):
            raise InvalidProposal('The proposed dependency graph contains duplicate step IDs.')
        by_id = {step.id: step for step in steps}
        needed, pending = set(), [output_id]
        while pending:
            current = pending.pop()
            if current in needed:
                continue
            if current not in by_id:
                raise InvalidProposal('A requested output refers to an unknown plan step.')
            needed.add(current)
            operation = by_id[current].operation
            pending.extend(getattr(operation, 'input_step_ids', []))
            for operand in ('input_step_id', 'component_step_id', 'target_step_id'):
                if getattr(operation, operand, None) is not None:
                    pending.append(getattr(operation, operand))
        return [step for step in steps if step.id in needed]
