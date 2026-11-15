"""Provider-independent structured planning, without executing model actions."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Protocol

from gemini import AsyncGeminiClient, GeminiError, GeminiRequestTooLarge
from image_api.errors import ApiError
from nemotron import AsyncNemotronClient, NemotronError, completion_text

from .config import IfcSettings


@dataclass(frozen=True)
class PlannerUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    output_tokens: int | None = None
    thought_tokens: int | None = None


@dataclass(frozen=True)
class PlannerReply:
    text: str = field(repr=False)
    model: str
    usage: PlannerUsage | None = None
    planning: dict | None = None


class Planner(Protocol):
    name: str
    settings: IfcSettings

    @property
    def provenance(self) -> dict: ...

    async def generate(self, payload: str, *, system: str, schema: dict) -> PlannerReply: ...


def gemini_schema(schema: dict) -> dict:
    """Preserve structure/refs using the native subset; validate all rules locally.

    Pydantic's discriminator and oneOf are replaced by supported anyOf branches.
    Removing repeated array/numeric bounds limits decoder-state growth, including
    recursive predicate/value types. The complete original schema remains in the
    system instruction and is enforced by the local Pydantic query boundary.
    """
    keywords = {"$ref", "type", "description", "format", "required", "enum"}

    def convert(value):
        if isinstance(value, bool):
            return value
        if not isinstance(value, dict):
            raise ValueError("Invalid structured planner schema.")
        result = {key: value[key] for key in keywords if key in value}
        if "const" in value:
            result["enum"] = [value["const"]]
        for key in ("$defs", "properties"):
            if key in value:
                result[key] = {name: convert(child) for name, child in value[key].items()}
        for key in ("items", "additionalProperties"):
            if key in value:
                result[key] = convert(value[key])
        if "prefixItems" in value:
            result["prefixItems"] = [convert(child) for child in value["prefixItems"]]
        variants = value.get("anyOf", value.get("oneOf"))
        if variants is not None:
            result["anyOf"] = [convert(child) for child in variants]
        return result

    return convert(schema)


def gemini_plan_schema(schema: dict) -> dict:
    """Constrain operations while transporting recursive predicates as JSON text.

    The recursive Predicate/Value grammar is much more complex than the small
    plan needed for one question. Native decoding still enforces each supported
    operation's required arguments and flat CountPolicy/FieldRef types. Opaque
    predicate objects let the decoder emit empty objects; finite nested unions
    were rejected by the provider in actual checks. JSON strings preserve the
    complete predicate grammar without a recursive decoder. Parse only those
    declared slots back into data, then apply unchanged local validation.
    """
    properties = schema.get("properties", {})
    if not {"steps", "interpretation", "explicitly_requests_entire_model"} <= properties.keys():
        return gemini_schema(schema)
    definitions = schema.get("$defs", {})

    def resolve(node):
        ref = node.get("$ref")
        if ref is None:
            return node
        prefix = "#/$defs/"
        if not ref.startswith(prefix) or ref[len(prefix):] not in definitions:
            raise ValueError("The IFC planner schema contains an unknown reference.")
        return definitions[ref[len(prefix):]]

    step = resolve(properties["steps"]["items"])
    operation = step["properties"]["operation"]
    variants = operation.get("oneOf", operation.get("anyOf", []))
    supported = {"select", "traverse", "aggregate", "spatial_query", "related_entities", "project", "rank",
                 "measure", "arithmetic", "table_calculate", "network_query", "material_quantity", "route_query"}
    operations = []
    for variant in variants:
        original = resolve(variant)
        if original.get("properties", {}).get("kind", {}).get("const") not in supported:
            continue
        converted = gemini_schema(original)
        for name in ("where", "exclude"):
            if name in converted.get("properties", {}):
                converted["properties"][name] = {"type": ["string", "null"],
                    "description": "JSON-encoded typed predicate from the full schema, or null to select all category candidates. Include its kind and every requested filter."}
        operations.append(converted)
    if not operations:
        raise ValueError("The IFC planner schema has no registered operation kinds.")
    compact = {
        "type": "object",
        "properties": {key: gemini_schema(value) for key, value in properties.items()
                       if key not in {"steps", "requests"}},
        "required": schema.get("required", []),
        "additionalProperties": False,
        "$defs": {name: gemini_schema(definitions[name]) for name in ("CountPolicy", "FieldRef")},
    }
    compact["properties"]["steps"] = {
        "type": "array", "items": {
            "type": "object", "properties": {
                "id": {"type": "string"},
                "operation": {"anyOf": operations},
            }, "required": ["id", "operation"], "additionalProperties": False,
        },
    }
    if "requests" in properties:
        compact["properties"]["requests"] = {
            "type": "array", "items": gemini_schema(resolve(properties["requests"]["items"])),
        }
    return compact


def decode_gemini_predicates(text: str) -> str:
    """Decode data in select filter slots only; malformed data stays invalid.

    Keep the original reply on parse failure so the service can account for
    its real usage and apply the same bounded repair and safe diagnostics.
    Text values, interpretation, source labels and step IDs are never decoded.
    """
    try:
        value = json.loads(text)
        if not isinstance(value, dict) or not isinstance(value.get("steps"), list):
            return text
        for step in value["steps"]:
            operation = step.get("operation") if isinstance(step, dict) else None
            if not isinstance(operation, dict) or operation.get("kind") != "select":
                continue
            for key in ("where", "exclude"):
                if isinstance(operation.get(key), str):
                    operation[key] = json.loads(operation[key])
        return json.dumps(value, ensure_ascii=False)
    except (ValueError, RecursionError):
        return text


def _counter(value) -> int | None:
    if value is not None and (type(value) is not int or value < 0):
        raise ApiError(502, "invalid_model_output", "The IFC planner returned invalid usage metadata.")
    return value


class NemotronPlanner:
    name = "nemotron"

    def __init__(self, client: AsyncNemotronClient, settings: IfcSettings | None = None):
        self.client = client
        self.settings = settings or IfcSettings()

    @property
    def provenance(self) -> dict:
        configuration = self.client.settings
        return {"provider": self.name, "requested_model": configuration.model,
                "thinking_level": ("enabled" if configuration.enable_thinking else
                                   "disabled" if configuration.enable_thinking is False else "provider_default"),
                "max_output_tokens": self.settings.max_tokens}

    async def generate(self, payload: str, *, system: str, schema: dict) -> PlannerReply:
        try:
            reply = await self.client.ask(payload,
                system=system + "\nJSON Schema:\n" + json.dumps(schema, ensure_ascii=False),
                response_format={"type": "json_object"},
                max_tokens=self.settings.max_tokens, temperature=0)
        except NemotronError as exc:
            if exc.status_code in {401, 403, 404}:
                raise ApiError(503, "provider_configuration", "The IFC inference provider is not configured for this service.") from None
            if exc.retryable:
                raise ApiError(503, "provider_unavailable", "The IFC inference provider is temporarily unavailable.", True) from None
            raise ApiError(502, "provider_error", "The IFC inference provider could not complete the query plan.") from None
        try:
            text = completion_text(reply)
        except NemotronError:
            raise ApiError(502, "invalid_model_output", "The IFC planner returned an incomplete or invalid query plan.") from None
        usage = None
        if reply.usage is not None:
            thoughts = getattr(getattr(reply.usage, "completion_tokens_details", None), "reasoning_tokens", None)
            usage = PlannerUsage(_counter(reply.usage.prompt_tokens), _counter(reply.usage.completion_tokens),
                                 thought_tokens=_counter(thoughts))
        return PlannerReply(text, reply.model, usage)


class GeminiPlanner:
    name = "gemini"

    def __init__(self, client: AsyncGeminiClient, settings: IfcSettings | None = None):
        self.client = client
        self.settings = settings or IfcSettings(provider="gemini")

    @property
    def provenance(self) -> dict:
        return {"provider": self.name, "requested_model": self.client.settings.model,
                "thinking_level": self.settings.gemini_thinking_level,
                "max_output_tokens": self.settings.gemini_max_output_tokens}

    async def generate(self, payload: str, *, system: str, schema: dict) -> PlannerReply:
        try:
            reply = await self.client.generate_plan(payload,
                system=system + "\nFull schema, including locally enforced constraints:\n" + json.dumps(schema, ensure_ascii=False)
                + "\nNative wire override: select.where and select.exclude must be JSON-encoded strings containing the complete typed predicate, or null. "
                  "For example where=\"{\\\"kind\\\":\\\"compare\\\",\\\"field\\\":{\\\"kind\\\":\\\"property\\\",\\\"key\\\":\\\"ifc:attribute/Name\\\"},\\\"operator\\\":\\\"eq\\\",\\\"value\\\":{\\\"kind\\\":\\\"text\\\",\\\"value\\\":{\\\"text\\\":\\\"ORIGINAL_ROOM_ID\\\"}}}\". "
                  "The server decodes those two slots and validates against the full schema before execution. Never omit a required filter to avoid encoding it.",
                schema=gemini_plan_schema(schema), thinking_level=self.settings.gemini_thinking_level,
                max_output_tokens=self.settings.gemini_max_output_tokens)
        except GeminiRequestTooLarge:
            raise ApiError(413, "planner_request_too_large", "The IFC planning context exceeds the provider request limit.") from None
        except GeminiError as exc:
            diagnostics = {"provider_status_code": exc.status_code, "provider_code": exc.provider_code}
            if exc.code == "invalid_model_output":
                raise ApiError(502, "invalid_model_output", "The IFC planner returned an incomplete or invalid query plan.", **diagnostics) from None
            if exc.status_code in {400, 401, 402, 403, 404}:
                raise ApiError(503, "provider_configuration", "The Gemini IFC planner rejected the request. Check schema, model settings, access and billing on the backend.", **diagnostics) from None
            if exc.retryable:
                raise ApiError(503, "provider_unavailable", "The IFC inference provider is temporarily unavailable.", True, **diagnostics) from None
            raise ApiError(502, "provider_error", "The IFC inference provider could not complete the query plan.", **diagnostics) from None
        usage = reply.usage
        return PlannerReply(decode_gemini_predicates(reply.text), reply.model, None if usage is None else PlannerUsage(
            usage.prompt_tokens, usage.completion_tokens, usage.output_tokens, usage.thought_tokens))
