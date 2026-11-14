"""Small deterministic front door; interpretation models never supply answer values."""
from __future__ import annotations

import re

from contracts import models as m


def language(question: str, requested: str | None = None) -> str:
    if requested:
        return requested
    text = question.casefold()
    patterns = {
        'fi': r'\b(montako|kuinka|mikä|mitkä|paljonko|näytä)\b',
        'sv': r'\b(hur|vilka|vilken|fönster|dörrar|många)\b',
        'de': r'\b(wie|welche|wieviel|gibt|geschoss|räume)\b',
        'fr': r'\b(combien|quelle|quelles|quel|étage|pièces)\b',
        'it': r'\b(quanti|quante|qual|quale|superficie|piano)\b',
        'da': r'\b(hvor|hvad|hvilke|bygning|rummet)\b',
        'nl': r'\b(hoeveel|welke|wat|oppervlakte|verdieping)\b',
        'es': r'\b(cuántos|cuántas|cuál|número|superficie)\b',
        'et': r'\b(mitu|milline|kui|ruumi|kogu)\b',
        'pl': r'\b(ile|jaka|jakie|powierzchnia|pomieszczenia)\b',
        'ro': r'\b(care|câte|numărul|clădire|suprafața)\b',
    }
    return next((key for key, pattern in patterns.items() if re.search(pattern, text)), 'en')


def requested_parts(request: m.AnswerRequest) -> list[m.AnswerRequestedPart]:
    if request.parts is not None:
        return request.parts
    # Explicit separate sentences can be handled independently. Keep complex
    # conjunctive interpretation in the structured planner, not string guesses.
    sentences = [item.strip() for item in re.split(r'(?<=[?;])\s+(?=[A-ZÄÖÅÉ¿])', request.question) if item.strip()]
    if len(sentences) == 1:
        clauses = re.split(r'\s+(?:and|plus|und|ja|et|e)\s+(?=(?:give|calculate|what|how|list|show|measure|find|provide|welche|laske|näytä)\b)',
                           request.question, flags=re.I)
        if len(clauses) > 1:
            sentences = clauses
    if len(sentences) > 1 and len(sentences) <= 16:
        return [m.AnswerRequestedPart(key=f'part-{i+1}', question=item, literal_identifiers=identifiers(item)) for i, item in enumerate(sentences)]
    return [m.AnswerRequestedPart(key='answer', question=request.question, literal_identifiers=identifiers(request.question))]


def identifiers(question):
    quoted = re.findall(r'''["“«']([^"”»']+)["”»']''', question)
    labeled = re.findall(r'\b(?:room|space|door|window|raam|tila|huone|raum)\s+([\w]+(?:[.\-][\w]+)+)', question, re.I)
    return list(dict.fromkeys([*quoted, *labeled]))


def is_count_question(question):
    return bool(re.search(r'\b(?:how many|number of|count|montako|kuinka monta|lukumäärä|määrä|wie viele|anzahl|combien|nombre de|quanti|quante|hoeveel|hvor mange|hur många|antal|cuántos|cuántas|número de|mitu|ile|numărul|câte)\b', question, re.I))


def needs_entire_ifc(question: str) -> bool:
    return bool(re.search(r'\b(?:entire|whole)\s+(?:ifc\s+)?(?:model|building)\b|\bkoko\s+(?:ifc[- ]?)?malli|\bgesamten?\s+(?:ifc[- ]?)?modell', question, re.I))
