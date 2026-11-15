"""Small deterministic front door; interpretation models never supply answer values."""
from __future__ import annotations

import re

from contracts import models as m


_COUNTING_RULE = re.compile(
    r"^(?:count\s+(?:only\b|doorways\s+fitted\b)|only\s+count\b|do\s+not\s+count\b|"
    r"include\b|exclude\b|laske\s+(?:vain\b|oviaukot\b)|älä\s+laske\b|"
    r"jätä\s+pois\b|(?:open\s+doorways\b.*\bdo\s+not\s+count\b)|"
    r"(?:pelkkiä\s+oviaukkoja\b.*\bei\s+lasketa\b)|"
    r"(?:a|each)\b.*\bcounts?\s+as\s+(?:one|1)\b)", re.I)
_QUOTED = re.compile(r'''"[^"]*"|“[^”]*”|«[^»]*»|(?<!\w)'[^']*'(?!\w)''')


def _split_unquoted(pattern: str, text: str, *, flags=0) -> list[str]:
    """Separate explicit requests without splitting a literal source identifier."""
    protected = [match.span() for match in _QUOTED.finditer(text)]
    start, pieces = 0, []
    for boundary in re.finditer(pattern, text, flags):
        if any(left <= boundary.start() < right for left, right in protected):
            continue
        pieces.append(text[start:boundary.start()].strip())
        start = boundary.end()
    pieces.append(text[start:].strip())
    return [piece for piece in pieces if piece]


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
    fragments = _split_unquoted(r'(?<=[?;])\s+(?=[A-ZÄÖÅÉ¿])', request.question)
    sentences = []
    for fragment in fragments:
        # A counting rule qualifies the preceding inventory; it is not another
        # requested answer. Keep the rule with the detector's full question.
        if sentences and is_count_question(sentences[-1]) and _COUNTING_RULE.match(fragment):
            sentences[-1] += ' ' + fragment
        else:
            sentences.append(fragment)
    if len(sentences) == 1:
        clauses = _split_unquoted(r'\s+(?:and|plus|und|ja|et|e)\s+(?=(?:give|calculate|what|how|list|show|measure|find|provide|welche|laske|näytä)\b)',
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
