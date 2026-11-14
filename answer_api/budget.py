"""One host-owned wall-clock and external-attempt budget per answer."""
from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from contracts import models as m
from image_api.errors import ApiError


class AnswerBudget:
    def __init__(self, seconds=180, max_attempts=15):
        self.started = perf_counter()
        self.deadline = self.started + seconds
        self.max_attempts = min(15, max_attempts)
        self.calls: list[m.AnswerCall] = []

    @property
    def remaining(self):
        return max(0., self.deadline - perf_counter())

    @property
    def attempts_remaining(self):
        return self.max_attempts - len(self.calls)

    def check(self, attempts=0):
        if self.remaining <= .25:
            raise ApiError(504, "deadline_exceeded", "The answer's shared deadline was exhausted.", True)
        if self.attempts_remaining < attempts:
            raise ApiError(422, "answer_budget_exceeded", "The question's shared external-attempt budget was exhausted.")

    def begin(self, purpose, model):
        self.check(1)
        call = m.AnswerCall(id='answer-call:' + uuid4().hex, purpose=purpose,
                            requested_model=model, outcome='failed')
        self.calls.append(call)
        return call, perf_counter()

    @staticmethod
    def complete(call, started, reply=None, outcome='completed'):
        call.outcome = outcome
        call.elapsed_ms = (perf_counter() - started) * 1000
        call.completed_at = datetime.now(timezone.utc).isoformat()
        if reply is not None:
            call.returned_model = getattr(reply, 'model', None)
            usage = getattr(reply, 'usage', None)
            call.prompt_tokens = getattr(usage, 'prompt_tokens', None)
            call.completion_tokens = getattr(usage, 'completion_tokens', None)
            call.thought_tokens = getattr(usage, 'thought_tokens', None)

    def visual(self, response):
        """Import the actual image tool ledger, preserving unknown usage."""
        if response.decision_trace is not None:
            self.visual_trace(response.decision_trace)
        else:
            self.calls.append(m.AnswerCall(id='answer-call:' + uuid4().hex, purpose='analysis',
                requested_model=response.provenance.requested_model,
                returned_model=response.provenance.returned_model, outcome='completed',
                elapsed_ms=response.metrics.elapsed_ms, prompt_tokens=response.metrics.prompt_tokens,
                completion_tokens=response.metrics.completion_tokens,
                input_sha256=response.image.inference_sha256))
        if len(self.calls) > self.max_attempts:
            raise RuntimeError('A tool exceeded its allocated answer attempt budget')

    def visual_trace(self, trace):
        for call in trace.calls:
            fields = {name: getattr(call, name) for name in m.AnswerCall.model_fields if hasattr(call, name)}
            # Legacy call IDs are local to one tool invocation; independent
            # subplans must not collide in the question-wide ledger.
            fields['id'] = f'answer-call:{len(self.calls)}:{call.id}'
            self.calls.append(m.AnswerCall(**fields))
        if len(self.calls) > self.max_attempts:
            raise RuntimeError('A tool exceeded its allocated answer attempt budget')

    def failed_visual(self, model, started, exc):
        import asyncio
        usage = getattr(exc, 'usage', None)
        self.calls.append(m.AnswerCall(id='answer-call:' + uuid4().hex, purpose='analysis',
            requested_model=model, returned_model=getattr(exc, 'returned_model', None),
            outcome='cancelled' if isinstance(exc, (asyncio.CancelledError, asyncio.TimeoutError)) else 'failed',
            elapsed_ms=(perf_counter() - started) * 1000, completed_at=datetime.now(timezone.utc).isoformat(),
            prompt_tokens=getattr(usage, 'prompt_tokens', None), completion_tokens=getattr(usage, 'completion_tokens', None)))

    def metrics(self):
        def total(field):
            values = [getattr(call, field) for call in self.calls]
            return sum(values) if all(value is not None for value in values) else None
        return m.AnswerMetrics(elapsed_ms=(perf_counter() - self.started) * 1000,
            external_attempts=len(self.calls), calls=self.calls,
            model_input_tokens=total('prompt_tokens'), model_output_tokens=total('completion_tokens'))


class BudgetPlanner:
    """Per-request adapter; never mutate shared provider clients/settings."""
    def __init__(self, planner, budget):
        self.inner, self.budget = planner, budget
        self.name, self.settings = planner.name, planner.settings

    @property
    def provenance(self):
        return self.inner.provenance

    async def generate(self, *args, **kwargs):
        call, started = self.budget.begin('planning', self.provenance.get('requested_model', self.name))
        try:
            reply = await self.inner.generate(*args, **kwargs)
        except BaseException as exc:
            import asyncio
            self.budget.complete(call, started, outcome='cancelled' if isinstance(exc, asyncio.CancelledError) else 'failed')
            raise
        self.budget.complete(call, started, reply)
        return reply
