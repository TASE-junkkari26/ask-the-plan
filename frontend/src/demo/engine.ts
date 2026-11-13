import type { QueryResult, Scope } from '../contracts/QueryResult.ts';
import type {
  DemoResponse,
  Drawing,
  Language,
  Mark,
  TraceStep,
} from '../types.ts';
import { BEDROOM, SCHEDULE, doorMarks, windowMarks } from './data.ts';

/** Deterministic demo fixtures only. No model call and no inference on uploaded files. */
export function resolveDemo(
  drawing: Drawing,
  question: string,
  language: Language,
): DemoResponse {
  const text = question.toLocaleLowerCase().trim();
  const fi = language === 'fi';
  let intent: DemoResponse['intent'] = 'missing';
  let marks: Mark[] = [];
  let value = '';
  let unit = '';
  let summary = fi
    ? 'Tietoa ei näy tässä piirustuksessa'
    : 'Not shown in this drawing';
  let description = fi
    ? 'Tähän kysymykseen ei ole demovastausta. Kokeile ehdotettua kysymystä.'
    : 'This prototype has no fixture for that question. Try one of the suggested questions.';
  let steps: TraceStep[] = [];
  const outOfScope =
    /whole (building|model)|entire (building|model)|all floors|koko rakenn|kaikki kerrok/.test(
      text,
    );
  const unavailable =
    /fire|paloluokka|rating|price|cost|hinta|maksaa|load|kantav/.test(text);
  if (outOfScope)
    description = fi
      ? 'Kysymys koskee useampaa näkymää. Tässä demossa vastataan vain valitun piirustuksen perusteella.'
      : 'That question extends beyond the selected drawing. This demo answers from the current view only.';
  else if (unavailable)
    description = fi
      ? 'Paloluokkaa tai hintatietoja ei ole merkitty valittuun piirustukseen.'
      : 'The selected source does not specify fire ratings, prices, or structural capacity. These cannot be established from the visible drawing.';
  else if (/width|levey/.test(text) && drawing.kind === 'schedule') {
    const doorId = text.match(/d\s*0?([1-8])\b/i)?.[1];
    if (doorId) {
      const i = Number(doorId) - 1;
      const row = SCHEDULE[i];
      intent = 'schedule';
      value = row[3];
      unit = 'mm';
      summary = fi ? `Oven ${row[0]} leveys` : `${row[0]} door width`;
      marks = [
        {
          id: `cell-${row[0]}`,
          entityId: `demo:door:${row[0]}`,
          ordinal: i + 1,
          label: row[0],
          detail: `${row[1]} · width cell`,
          kind: 'box',
          bounds: [570, 215 + i * 42, 120, 42],
        },
      ];
      description = fi
        ? 'Leveys on ilmoitettu oviluettelon leveys-sarakkeessa.'
        : 'The width is specified in the door schedule. The highlighted cell is the source of this answer.';
      steps = [
        {
          title: fi
            ? 'Rajaa valittuun luetteloon'
            : 'Use the selected schedule',
          detail: `${drawing.code} · ${drawing.title}`,
          markIds: [],
        },
        {
          title: fi
            ? 'Etsi ovi tunnisteella'
            : 'Find the exact door identifier',
          detail: `${row[0]} · ${row[1]}`,
          markIds: [marks[0].id],
        },
        {
          title: fi ? 'Lue leveys-sarake' : 'Read the width column',
          detail: 'Original schedule unit: millimetres.',
          expression: `${row[0]} → Width → ${value} mm`,
          markIds: [marks[0].id],
        },
      ];
    }
  } else if (
    /area|nettoala|pinta-ala|makuuhuone/.test(text) &&
    drawing.kind === 'plan' &&
    !/bedroom\s*0?2|makuuhuone\s*0?2|living|kitchen|whole|total|olohuone|keitti?|koko|yhteens?/.test(
      text,
    )
  ) {
    intent = 'area';
    value = '13.23';
    unit = 'm²';
    summary = fi ? 'Makuuhuoneen 01 nettoala' : 'Bedroom 01 net floor area';
    marks = [{ ...BEDROOM, entityId: `${drawing.id}:room:B01` }];
    description = fi
      ? 'Huoneen pinta-alasta on vähennetty näkyvä pilari. Mitat perustuvat tämän demopiirustuksen mittaviivaan.'
      : 'The visible column is excluded from the room boundary. Measurements use the dimension shown on this demo drawing.';
    steps = [
      {
        title: fi ? 'Valitse huoneen rajaus' : 'Trace the room boundary',
        detail: 'Bedroom 01 · 320 × 185 drawing units',
        expression: '320 × 185 × 0.015² = 13.32 m²',
        markIds: [BEDROOM.id],
      },
      {
        title: fi ? 'Vähennä pilari' : 'Subtract the column footprint',
        detail: 'One visible column · 20 × 20 drawing units',
        expression: '20 × 20 × 0.015² = 0.09 m²',
        markIds: [BEDROOM.id],
      },
      {
        title: fi ? 'Laske nettoala' : 'Calculate net area',
        detail: 'Net floor area · square metres',
        expression: '13.32 − 0.09 = 13.23 m²',
        markIds: [BEDROOM.id],
      },
    ];
  } else if (/width|wide|levey/.test(text) && drawing.kind === 'plan') {
    intent = 'width';
    value = '2.40';
    unit = 'm';
    summary = fi ? 'Käytävän leveys' : 'Corridor width';
    marks = [
      {
        id: 'corridor-width',
        entityId: `${drawing.id}:room:C01`,
        ordinal: 1,
        label: '2.40 m',
        detail: 'Clear width · horizontal dimension',
        kind: 'dimension',
        bounds: [490, 360, 160, 20],
      },
    ];
    description = fi
      ? 'Leveys perustuu piirustukseen merkittyyn mittaviivaan.'
      : 'Read from the indicated corridor dimension. The two endpoints show the measured span.';
    steps = [
      {
        title: 'Locate the dimension',
        detail: `${drawing.code} · Corridor`,
        markIds: [marks[0].id],
      },
      {
        title: 'Convert the source unit',
        detail: 'Original dimension: 2400 millimetres',
        expression: '2400 mm ÷ 1000 = 2.40 m',
        markIds: [marks[0].id],
      },
    ];
  } else if (/window|ikkun/.test(text) && drawing.kind !== 'schedule') {
    intent = 'windows';
    marks = windowMarks(drawing);
  } else if (/door|ove|ovia|ovi/.test(text)) {
    intent = 'doors';
    marks = doorMarks(drawing);
  }
  if (intent === 'doors' || intent === 'windows') {
    value = String(marks.length);
    unit = fi ? (intent === 'doors' ? 'ovea' : 'ikkunaa') : intent;
    summary = fi
      ? 'Näkyvät kohteet laskettu'
      : drawing.kind === 'schedule'
        ? 'Doors listed in this schedule'
        : `${intent === 'doors' ? 'Doors' : 'Windows'} on this drawing`;
    description = fi
      ? 'Jokainen numeroitu merkintä vastaa yhtä kohdetta valitussa näkymässä.'
      : `Each numbered mark corresponds to one ${intent === 'doors' ? 'door opening' : 'window'} in the selected view. No other floors are included.`;
    steps = [
      {
        title: fi ? 'Rajaa valittuun näkymään' : 'Scope to the current drawing',
        detail: `${drawing.code} · ${drawing.title} · Revision ${drawing.revision}`,
        markIds: [],
      },
      {
        title: fi ? 'Tunnista yksittäiset kohteet' : 'Identify unique objects',
        detail:
          intent === 'doors'
            ? 'Count openings fitted with a door. Multiple leaves belong to one opening.'
            : 'Count each window once; do not count individual frame lines.',
        markIds: marks.map((m) => m.id),
      },
      {
        title: fi ? 'Laske löydetyt kohteet' : 'Count the matched objects',
        detail: fi
          ? 'Kaikki merkinnät ovat tässä näkymässä.'
          : 'All matched objects are located in this view.',
        expression: `${marks.map((m) => m.label).join(' + ')} → ${marks.length}`,
        markIds: marks.map((m) => m.id),
      },
    ];
  }
  const scope: Scope = {
    project_id: 'demo:west-harbour',
    document_ids: [`demo:${drawing.id}:rev-${drawing.revision}`],
    view_ids: [`demo:${drawing.id}:view`],
    universe:
      drawing.kind === 'schedule'
        ? ('schedule_entries' as const)
        : ('depicted_objects' as const),
  };
  const questionKey =
    [...question.trim()].reduce(
      (hash, letter) => Math.imul(hash ^ letter.charCodeAt(0), 16777619),
      2166136261,
    ) >>> 0;
  const requestId = `demo:${drawing.id}:${questionKey.toString(16)}`;
  if (intent === 'missing' && !unavailable && !outOfScope)
    summary = fi ? 'Kokeile demokysymyst?' : 'Try a prepared demo question';
  const policy = {
    grain:
      drawing.kind === 'schedule'
        ? ('schedule_row' as const)
        : ('logical_object' as const),
    hierarchy: 'topmost_matches' as const,
    rule_key:
      intent === 'windows'
        ? 'window.logical_opening.v1'
        : 'door.opening_with_leaf.v1',
  };
  let result: QueryResult;
  if (intent === 'missing')
    result = {
      schema_version: '0.1.0',
      id: `${requestId}:result`,
      request_id: requestId,
      status:
        unavailable || outOfScope
          ? 'missing_information'
          : 'unsupported_operation',
      issues: [
        {
          code:
            unavailable || outOfScope
              ? 'missing_information'
              : 'unsupported_operation',
          message: { text: description, language },
        },
      ],
      executor_version: 'demo-fixtures-1',
    };
  else {
    const count = intent === 'doors' || intent === 'windows';
    const answerValue = count
      ? { kind: 'count' as const, value: marks.length }
      : {
          kind: 'quantity' as const,
          magnitude: value,
          unit_id:
            intent === 'area'
              ? 'unit:m2'
              : intent === 'schedule'
                ? 'unit:mm'
                : 'unit:m',
          quantity_kind: intent === 'area' ? 'area' : 'length',
          basis: intent === 'area' ? 'net' : 'specified',
          unit_resolution:
            intent === 'area' ? ('derived' as const) : ('explicit' as const),
        };
    result = {
      schema_version: '0.1.0',
      id: `${requestId}:result`,
      request_id: requestId,
      plan_id: `${requestId}:plan`,
      status: 'answered',
      claims: [
        {
          id: `${requestId}:claim`,
          output_key: 'answer',
          name: summary,
          scope,
          concept_ids: [`concept:${count ? intent : 'room'}`],
          value: answerValue,
          quality: 'exact',
          coverage_ids: [`demo:${drawing.id}:coverage`],
          ...(count ? { count_policy: policy } : {}),
          evidence: [
            {
              calculation_id: `${requestId}:calculation`,
              anchor_ids: marks.map((m) => `${m.id}:anchor`),
              ...(count ? { entity_set_ids: [`${requestId}:set`] } : {}),
            },
          ],
        },
      ],
      entity_sets: count
        ? [
            {
              id: `${requestId}:set`,
              scope,
              count_policy: policy,
              count: marks.length,
              entity_ids: marks.map((m) => m.entityId),
            },
          ]
        : [],
      calculations: [
        {
          id: `${requestId}:calculation`,
          plan_step_id: 'answer',
          operation: count
            ? 'count'
            : intent === 'area'
              ? 'subtract'
              : 'lookup',
          ...(count ? { included_set_id: `${requestId}:set` } : {}),
          anchor_ids: marks.map((m) => `${m.id}:anchor`),
          output: answerValue,
          quality: 'exact',
        },
      ],
      executor_version: 'demo-fixtures-1',
    };
  }
  if (intent === 'area' && result.calculations) {
    const makeArea = (magnitude: string) => ({
      kind: 'quantity' as const,
      magnitude,
      unit_id: 'unit:m2',
      quantity_kind: 'area',
      basis: 'calculated',
      unit_resolution: 'derived' as const,
    });
    result.calculations = [
      {
        id: `${requestId}:shell`,
        operation: 'measure',
        anchor_ids: ['bedroom-shell:anchor', 'drawing-dimension:anchor'],
        output: makeArea('13.32'),
        quality: 'exact',
      },
      {
        id: `${requestId}:column`,
        operation: 'measure',
        anchor_ids: ['bedroom-column:anchor', 'drawing-dimension:anchor'],
        output: makeArea('0.09'),
        quality: 'exact',
      },
      {
        ...result.calculations[0],
        input_node_ids: [`${requestId}:shell`, `${requestId}:column`],
      },
    ];
  }
  return {
    result,
    intent,
    question,
    summary,
    value,
    unit,
    description,
    marks,
    steps,
  };
}

/** Replace this adapter with the backend HTTP client; UI receives the same presentation shape. */
export async function askDemo(
  drawing: Drawing,
  question: string,
  language: Language,
  signal: AbortSignal,
): Promise<DemoResponse> {
  if (signal.aborted) throw new DOMException('Cancelled', 'AbortError');
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, 420);
    signal.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(new DOMException('Cancelled', 'AbortError'));
      },
      { once: true },
    );
  });
  if (signal.aborted) throw new DOMException('Cancelled', 'AbortError');
  return resolveDemo(drawing, question, language);
}
