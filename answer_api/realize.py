"""Deterministic, evidence-bound answer wording. No model writes source facts.

The renderer deliberately has no free-form rewrite path: validation regenerates
every sentence from the typed results, including scope and quality qualifiers.
Large tables remain complete in the result/export; only prose is summarized.
"""
from __future__ import annotations

from contracts import models as m


_TEXT = {
    "en": {"scope": "Scope: {scope}.", "estimated": "approximately ", "lower_bound": "at least ", "upper_bound": "at most ",
           "detected": "The scan detected {value} likely {name}; the total is not confirmed.",
           "count": "{name}: {value} ({grain}; {universe}).", "rows": "The summary shows {shown} of {total} rows; all rows are in the structured evidence.",
           "none": "No matching source records were returned.", "missing": "unavailable", "yes": "yes", "no": "no", "partial": "Partial result.", "unspecified": "unit unresolved"},
    "fi": {"scope": "Rajaus: {scope}.", "estimated": "noin ", "lower_bound": "vähintään ", "upper_bound": "enintään ",
           "detected": "Analyysi havaitsi {value} todennäköistä kohdetta ({name}); kokonaismäärää ei ole vahvistettu.",
           "count": "{name}: {value} ({grain}; {universe}).", "rows": "Yhteenveto näyttää {shown}/{total} riviä; kaikki rivit ovat rakenteisessa lähdeaineistossa.",
           "none": "Vastaavia lähdetietueita ei löytynyt.", "missing": "ei saatavilla", "yes": "kyllä", "no": "ei", "partial": "Osittainen tulos.", "unspecified": "yksikkö selvittämättä"},
    "de": {"scope": "Umfang: {scope}.", "estimated": "ungefähr ", "lower_bound": "mindestens ", "upper_bound": "höchstens ",
           "detected": "Die Analyse erkannte {value} mögliche Objekte ({name}); die Gesamtzahl ist nicht bestätigt.",
           "count": "{name}: {value} ({grain}; {universe}).", "rows": "Die Zusammenfassung zeigt {shown} von {total} Zeilen; alle Zeilen stehen in den strukturierten Belegen.",
           "none": "Keine passenden Quelldatensätze gefunden.", "missing": "nicht verfügbar", "yes": "ja", "no": "nein", "partial": "Teilergebnis.", "unspecified": "Einheit ungeklärt"},
    "fr": {"scope": "Périmètre : {scope}.", "estimated": "environ ", "lower_bound": "au moins ", "upper_bound": "au plus ",
           "detected": "L’analyse a détecté {value} objets probables ({name}) ; le total n’est pas confirmé.",
           "count": "{name} : {value} ({grain} ; {universe}).", "rows": "Le résumé affiche {shown} lignes sur {total} ; toutes les lignes figurent dans les preuves structurées.",
           "none": "Aucun enregistrement source correspondant trouvé.", "missing": "indisponible", "yes": "oui", "no": "non", "partial": "Résultat partiel.", "unspecified": "unité non résolue"},
    "it": {"scope": "Ambito: {scope}.", "estimated": "circa ", "lower_bound": "almeno ", "upper_bound": "al massimo ",
           "detected": "L’analisi ha rilevato {value} probabili oggetti ({name}); il totale non è confermato.",
           "count": "{name}: {value} ({grain}; {universe}).", "rows": "Il riepilogo mostra {shown} di {total} righe; tutte le righe sono nelle prove strutturate.",
           "none": "Nessun record sorgente corrispondente trovato.", "missing": "non disponibile", "yes": "sì", "no": "no", "partial": "Risultato parziale.", "unspecified": "unità non risolta"},
    "sv": {"scope": "Omfattning: {scope}.", "estimated": "ungefär ", "lower_bound": "minst ", "upper_bound": "högst ",
           "detected": "Analysen upptäckte {value} sannolika objekt ({name}); totalen är inte bekräftad.",
           "count": "{name}: {value} ({grain}; {universe}).", "rows": "Sammanfattningen visar {shown} av {total} rader; alla rader finns i det strukturerade underlaget.",
           "none": "Inga matchande källposter hittades.", "missing": "saknas", "yes": "ja", "no": "nej", "partial": "Delresultat.", "unspecified": "enhet ej fastställd"},
    "es": {"scope": "Ámbito: {scope}.", "estimated": "aproximadamente ", "lower_bound": "al menos ", "upper_bound": "como máximo ",
           "detected": "El análisis detectó {value} objetos probables ({name}); el total no está confirmado.",
           "count": "{name}: {value} ({grain}; {universe}).", "rows": "El resumen muestra {shown} de {total} filas; todas las filas están en las pruebas estructuradas.",
           "none": "No se encontraron registros de origen coincidentes.", "missing": "no disponible", "yes": "sí", "no": "no", "partial": "Resultado parcial.", "unspecified": "unidad sin resolver"},
    "da": {"scope": "Omfang: {scope}.", "estimated": "cirka ", "lower_bound": "mindst ", "upper_bound": "højst ",
           "detected": "Analysen fandt {value} sandsynlige objekter ({name}); det samlede antal er ikke bekræftet.",
           "count": "{name}: {value} ({grain}; {universe}).", "rows": "Oversigten viser {shown} af {total} rækker; alle rækker findes i det strukturerede kildegrundlag.",
           "none": "Ingen matchende kildeposter blev fundet.", "missing": "ikke tilgængelig", "yes": "ja", "no": "nej", "partial": "Delvist resultat.", "unspecified": "enhed uafklaret"},
    "nl": {"scope": "Bereik: {scope}.", "estimated": "ongeveer ", "lower_bound": "minstens ", "upper_bound": "hoogstens ",
           "detected": "De analyse detecteerde {value} waarschijnlijke objecten ({name}); het totaal is niet bevestigd.",
           "count": "{name}: {value} ({grain}; {universe}).", "rows": "De samenvatting toont {shown} van {total} rijen; alle rijen staan in het gestructureerde bronmateriaal.",
           "none": "Geen overeenkomende bronrecords gevonden.", "missing": "niet beschikbaar", "yes": "ja", "no": "nee", "partial": "Gedeeltelijk resultaat.", "unspecified": "eenheid niet vastgesteld"},
    "et": {"scope": "Ulatus: {scope}.", "estimated": "ligikaudu ", "lower_bound": "vähemalt ", "upper_bound": "kuni ",
           "detected": "Analüüs tuvastas {value} tõenäolist objekti ({name}); koguarv ei ole kinnitatud.",
           "count": "{name}: {value} ({grain}; {universe}).", "rows": "Kokkuvõttes on {shown} rida {total} reast; kõik read on struktureeritud tõendites.",
           "none": "Vastavaid lähtekirjeid ei leitud.", "missing": "pole saadaval", "yes": "jah", "no": "ei", "partial": "Osaline tulemus.", "unspecified": "ühik määramata"},
    "pl": {"scope": "Zakres: {scope}.", "estimated": "około ", "lower_bound": "co najmniej ", "upper_bound": "co najwyżej ",
           "detected": "Analiza wykryła {value} prawdopodobnych obiektów ({name}); łączna liczba nie została potwierdzona.",
           "count": "{name}: {value} ({grain}; {universe}).", "rows": "Podsumowanie pokazuje {shown} z {total} wierszy; wszystkie wiersze znajdują się w danych źródłowych.",
           "none": "Nie znaleziono pasujących rekordów źródłowych.", "missing": "niedostępne", "yes": "tak", "no": "nie", "partial": "Wynik częściowy.", "unspecified": "jednostka nieustalona"},
    "ro": {"scope": "Domeniu: {scope}.", "estimated": "aproximativ ", "lower_bound": "cel puțin ", "upper_bound": "cel mult ",
           "detected": "Analiza a detectat {value} obiecte probabile ({name}); totalul nu este confirmat.",
           "count": "{name}: {value} ({grain}; {universe}).", "rows": "Rezumatul arată {shown} din {total} rânduri; toate rândurile sunt în dovezile structurate.",
           "none": "Nu s-au găsit înregistrări sursă corespunzătoare.", "missing": "indisponibil", "yes": "da", "no": "nu", "partial": "Rezultat parțial.", "unspecified": "unitate neclarificată"},
}


def supported_languages() -> tuple[str, ...]:
    return tuple(_TEXT)


_VISUAL_TEXT = {
    "en": ("Likely {value}.", "Possible matches: {value}.", "Size comparison is unverified.", "Visual match, not verified.", "I can highlight a possible match, but can’t verify that answer yet."),
    "fi": ("Todennäköisesti {value}.", "Mahdolliset kohteet: {value}.", "Kokovertausta ei ole vahvistettu.", "Vahvistamaton visuaalinen havainto.", "Voin näyttää mahdollisen kohteen, mutta en vielä vahvistaa vastausta."),
    "de": ("Vermutlich {value}.", "Mögliche Treffer: {value}.", "Größenvergleich nicht bestätigt.", "Visueller Treffer, nicht bestätigt.", "Ich kann einen möglichen Treffer zeigen, die Antwort aber noch nicht bestätigen."),
    "fr": ("Probablement {value}.", "Correspondances possibles : {value}.", "Comparaison de taille non vérifiée.", "Correspondance visuelle non vérifiée.", "Je peux montrer une correspondance possible, mais pas encore confirmer la réponse."),
    "it": ("Probabilmente {value}.", "Possibili corrispondenze: {value}.", "Confronto dimensionale non verificato.", "Corrispondenza visiva non verificata.", "Posso mostrare una possibile corrispondenza, ma non ancora confermare la risposta."),
    "sv": ("Troligen {value}.", "Möjliga träffar: {value}.", "Storleksjämförelsen är inte verifierad.", "Visuell träff, inte verifierad.", "Jag kan visa en möjlig träff, men ännu inte bekräfta svaret."),
    "es": ("Probablemente {value}.", "Posibles coincidencias: {value}.", "Comparación de tamaño no verificada.", "Coincidencia visual no verificada.", "Puedo mostrar una posible coincidencia, pero aún no confirmar la respuesta."),
    "da": ("Sandsynligvis {value}.", "Mulige fund: {value}.", "Størrelsessammenligningen er ikke bekræftet.", "Visuelt fund, ikke bekræftet.", "Jeg kan vise et muligt fund, men endnu ikke bekræfte svaret."),
    "nl": ("Waarschijnlijk {value}.", "Mogelijke overeenkomsten: {value}.", "Groottevergelijking niet geverifieerd.", "Visuele overeenkomst, niet geverifieerd.", "Ik kan een mogelijke overeenkomst tonen, maar het antwoord nog niet bevestigen."),
    "et": ("Tõenäoliselt {value}.", "Võimalikud vasted: {value}.", "Suuruste võrdlus on kinnitamata.", "Kinnitamata visuaalne vaste.", "Saan näidata võimalikku vastet, kuid vastust veel mitte kinnitada."),
    "pl": ("Prawdopodobnie {value}.", "Możliwe dopasowania: {value}.", "Porównanie wielkości niezweryfikowane.", "Dopasowanie wizualne niezweryfikowane.", "Mogę pokazać możliwe dopasowanie, ale jeszcze nie potwierdzić odpowiedzi."),
    "ro": ("Probabil {value}.", "Posibile potriviri: {value}.", "Comparația dimensiunilor nu este verificată.", "Potrivire vizuală neverificată.", "Pot arăta o posibilă potrivire, dar încă nu pot confirma răspunsul."),
}


def _entity_name(identifier: str, bundle: m.KnowledgeBundle) -> str:
    entity = next((item for item in bundle.entities if item.id == identifier), None)
    if entity is None:
        return identifier  # Semantic validation rejects unresolved references.
    label = " · ".join(item.text for item in entity.labels) or identifier
    anchors = {anchor.id: anchor for anchor in bundle.anchors}
    steps = [anchors[key].selector.value for key in entity.provenance.anchor_ids
             if key in anchors and anchors[key].selector.kind == "step_id"
             and not anchors[key].selector.property_path]
    return label + (f" [#{steps[0]}]" if steps else "")


def _value(value: m.Value, bundle: m.KnowledgeBundle, words: dict[str, str]) -> str:
    if isinstance(value, m.CountValue):
        return str(value.value)
    if isinstance(value, m.QuantityValue):
        unit = next((unit for unit in bundle.units if unit.id == value.unit_id), None)
        qualifier = words.get(value.quality, "") if value.quality != "exact" else ""
        symbol = ('' if unit.symbol == '1' else unit.symbol) if unit else words['unspecified']
        return f"{qualifier}{value.magnitude}{' ' + symbol if symbol else ''} ({value.basis})"
    if isinstance(value, m.TextValue):
        return value.value.text  # Never translate original identifiers/strings.
    if isinstance(value, m.BooleanValue):
        return words["yes" if value.value else "no"]
    if isinstance(value, m.UnavailableValue):
        return words["missing"] + ": " + value.explanation
    if isinstance(value, m.ReferencesValue):
        return ", ".join(_entity_name(item, bundle) for item in value.entity_ids[:12]) or words["none"]
    if isinstance(value, m.ListValue):
        return "; ".join(_value(item, bundle, words) for item in value.items[:12]) or words["none"]
    if isinstance(value, m.RecordValue):
        return "; ".join(f"{key}: {_value(item, bundle, words)}" for key, item in value.fields.items())
    labels = {column.key: column.label.text for column in value.columns}
    return " | ".join("; ".join(f"{labels[key]}: {_value(item, bundle, words)}" for key, item in row.items())
                      for row in value.rows[:12]) or words["none"]


def realize_answer(response: m.AnswerResponse) -> list[m.AnswerSentence]:
    """Render only existing typed claims/issues; no inference or arithmetic."""
    language = response.interpretation.language.split("-")[0].lower()
    words = _TEXT.get(language, _TEXT["en"])
    visual_words = _VISUAL_TEXT.get(language, _VISUAL_TEXT["en"])
    contexts = {item.id: item.bundle for item in response.evidence_contexts}
    sentences: list[m.AnswerSentence] = []
    for part in response.parts:
        result = part.result
        bundle = contexts.get(part.evidence_context_id)
        for claim in result.claims if result is not None else []:
            if bundle is None:
                raise ValueError("claim realization requires its source evidence context")
            candidate = any(binding.evidence_kind == "candidate" for binding in claim.evidence)
            visual_match = candidate and isinstance(claim.value, m.ReferencesValue) and claim.output_key == "visual_match"
            if visual_match:
                text = visual_words[0 if len(claim.value.entity_ids) == 1 else 1].format(
                    value=_value(claim.value, bundle, words))
                ranking = claim.count_policy and claim.count_policy.rule_key == "drawing.unverified_visual_rank.v1"
                text += " " + visual_words[2 if ranking else 3]
            elif isinstance(claim.value, m.CountValue):
                if candidate:
                    text = words["detected"].format(value=claim.value.value, name=claim.name)
                else:
                    value = words.get(claim.quality, "") + str(claim.value.value)
                    grain = claim.count_policy.grain.replace("_", " ") if claim.count_policy else "source object"
                    text = words["count"].format(name=claim.name, value=value, grain=grain,
                                                universe=claim.scope.universe.replace("_", " "))
            else:
                qualifier = words.get(claim.quality, "") if not isinstance(claim.value, m.QuantityValue) else ""
                rendered_value = claim.value
                if isinstance(rendered_value, m.QuantityValue) and claim.quality != rendered_value.quality:
                    # The claim's scope/membership qualification can be weaker
                    # than the scalar input's precision. Preserve that limit.
                    rendered_value = rendered_value.model_copy(update={"quality": claim.quality})
                text = f"{claim.name}: {qualifier}{_value(rendered_value, bundle, words)}."
            if not candidate:
                text += " " + words["scope"].format(scope=response.interpretation.scope_label)
            total = (len(claim.value.rows) if isinstance(claim.value, m.TableValue)
                     else len(claim.value.entity_ids) if isinstance(claim.value, m.ReferencesValue)
                     else len(claim.value.items) if isinstance(claim.value, m.ListValue) else 0)
            if total > 12:
                text += " " + words["rows"].format(shown=12, total=total)
            sentences.append(m.AnswerSentence(
                id=f"sentence:{part.key}:{claim.id}", part_key=part.key, kind="claim", text=text,
                claim_ids=[claim.id], value_paths=[""],
                anchor_ids=sorted({anchor for binding in claim.evidence for anchor in binding.anchor_ids}),
                qualification=claim.quality))
        issues = result.issues if result is not None else []
        for index, issue in enumerate(issues):
            text = (words["partial"] + " " if part.status == "partial" else "") + issue.message.text
            if result.executor_version == "drawing-observations-1" and part.status == "unsupported_operation" and issue.anchor_ids:
                # Preserve the implementation diagnostic in result.issues/export;
                # the primary unavailable answer is short and user-facing.
                text = visual_words[4]
            sentences.append(m.AnswerSentence(id=f"sentence:{part.key}:issue:{index}", part_key=part.key,
                kind="issue", text=text,
                anchor_ids=issue.anchor_ids, qualification="unavailable"))
        if not issues and part.message is not None:
            sentences.append(m.AnswerSentence(id=f"sentence:{part.key}:reason", part_key=part.key,
                kind="issue", text=part.message.text, qualification="unavailable"))
    return sentences


def with_narrative(response: m.AnswerResponse) -> m.AnswerResponse:
    """Populate the envelope without permitting unconstrained prose overrides."""
    return response.model_copy(update={"narrative": realize_answer(response)})
