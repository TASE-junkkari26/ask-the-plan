import type { Drawing, Mark } from '../types.ts';

export const DRAWINGS: Drawing[] = [
  {
    id: 'ground',
    code: 'A-101',
    title: 'Ground floor',
    titleFi: 'Pohjakerros',
    level: 'Level 00',
    kind: 'plan',
    revision: 'C',
  },
  {
    id: 'first',
    code: 'A-102',
    title: 'First floor',
    titleFi: 'Ensimmäinen kerros',
    level: 'Level 01',
    kind: 'plan',
    revision: 'B',
  },
  {
    id: 'schedule',
    code: 'A-601',
    title: 'Door schedule',
    titleFi: 'Oviluettelo',
    level: 'Schedules',
    kind: 'schedule',
    revision: 'C',
  },
  {
    id: 'elevation',
    code: 'A-201',
    title: 'South elevation',
    titleFi: 'Eteläjulkisivu',
    level: 'Elevations',
    kind: 'elevation',
    revision: 'A',
  },
];

export interface DoorPosition {
  x: number;
  y: number;
  angle: number;
  room: string;
}
export const DOORS: DoorPosition[] = [
  { x: 535, y: 575, angle: 0, room: 'Entrance' },
  { x: 490, y: 425, angle: 90, room: 'Living room' },
  { x: 490, y: 205, angle: 90, room: 'Bedroom 01' },
  { x: 650, y: 420, angle: -90, room: 'Bedroom 02' },
  { x: 650, y: 220, angle: -90, room: 'Kitchen / dining' },
  { x: 530, y: 285, angle: 0, room: 'Bathroom' },
  { x: 270, y: 510, angle: 90, room: 'Utility' },
  { x: 150, y: 390, angle: -90, room: 'Terrace access' },
];
export const WINDOWS = [
  { x: 210, y: 145, length: 100, vertical: false },
  { x: 750, y: 145, length: 110, vertical: false },
  { x: 150, y: 220, length: 90, vertical: true },
  { x: 340, y: 575, length: 100, vertical: false },
  { x: 950, y: 425, length: 90, vertical: true },
  { x: 760, y: 575, length: 110, vertical: false },
  { x: 950, y: 215, length: 80, vertical: true },
];
export const SCHEDULE = [
  ['D01', 'Entrance', 'A1', '1000', '2100', 'Timber'],
  ['D02', 'Living room', 'A2', '900', '2100', 'Timber'],
  ['D03', 'Bedroom 01', 'A2', '900', '2100', 'Timber'],
  ['D04', 'Bedroom 02', 'A2', '900', '2100', 'Timber'],
  ['D05', 'Kitchen / dining', 'A2', '900', '2100', 'Timber'],
  ['D06', 'Bathroom', 'A3', '800', '2100', 'Timber'],
  ['D07', 'Utility', 'A3', '800', '2100', 'Timber'],
  ['D08', 'Terrace', 'B1', '1200', '2200', 'Glazed'],
];

const doorBounds = ({
  x,
  y,
  angle,
}: DoorPosition): [number, number, number, number] => {
  if (angle === 90) return [x - 68, y - 7, 77, 78];
  if (angle === -90) return [x - 8, y - 67, 77, 78];
  return [x - 8, y - 68, 78, 78];
};

export function doorMarks(drawing: Drawing): Mark[] {
  if (drawing.kind === 'schedule')
    return SCHEDULE.map((row, i) => ({
      id: `schedule-${row[0]}`,
      entityId: `demo:door:${row[0]}`,
      ordinal: i + 1,
      label: row[0],
      detail: row[1],
      kind: 'box',
      bounds: [140, 215 + i * 42, 820, 42],
    }));
  if (drawing.kind === 'elevation')
    return [
      {
        id: 'elevation-door-1',
        entityId: 'demo:door:D01',
        ordinal: 1,
        label: 'D01',
        detail: 'Entrance',
        kind: 'box',
        bounds: [490, 363, 94, 181],
      },
    ];
  return DOORS.slice(0, drawing.id === 'first' ? 6 : 8).map((door, i) => ({
    id: `${drawing.id}-door-${i + 1}`,
    entityId: `demo:door:D${String(drawing.id === 'first' ? i + 11 : i + 1).padStart(2, '0')}`,
    ordinal: i + 1,
    label: `D${String(drawing.id === 'first' ? i + 11 : i + 1).padStart(2, '0')}`,
    detail: door.room,
    kind: 'box',
    bounds: doorBounds(door),
  }));
}

export function windowMarks(drawing: Drawing): Mark[] {
  if (drawing.kind === 'schedule') return [];
  if (drawing.kind === 'elevation')
    return [220, 365, 660, 805].map((x, i) => ({
      id: `elevation-window-${i}`,
      entityId: `elevation:window:W0${i + 1}`,
      ordinal: i + 1,
      label: `W0${i + 1}`,
      detail: 'South façade',
      kind: 'box',
      bounds: [x - 8, 377, 106, 110],
    }));
  return WINDOWS.slice(0, drawing.id === 'first' ? 5 : 7).map((win, i) => ({
    id: `${drawing.id}-window-${i + 1}`,
    entityId: `${drawing.id}:window:W0${i + 1}`,
    ordinal: i + 1,
    label: `W0${i + 1}`,
    detail: win.vertical
      ? 'Exterior wall · vertical'
      : 'Exterior wall · horizontal',
    kind: 'box',
    bounds: win.vertical
      ? [win.x - 13, win.y - 6, 26, win.length + 12]
      : [win.x - 6, win.y - 13, win.length + 12, 26],
  }));
}

export const BEDROOM: Mark = {
  id: 'bedroom-area',
  entityId: 'ground:room:B01',
  ordinal: 1,
  label: 'Bedroom 01',
  detail: 'Net floor area · column excluded',
  kind: 'area',
  bounds: [160, 155, 320, 185],
  polygon: [
    [160, 155],
    [480, 155],
    [480, 340],
    [160, 340],
  ],
  holes: [
    [
      [420, 165],
      [440, 165],
      [440, 185],
      [420, 185],
    ],
  ],
};

export function suggestions(drawing: Drawing, language: 'en' | 'fi'): string[] {
  if (drawing.kind === 'schedule')
    return language === 'fi'
      ? [
          'Kuinka monta ovea luettelossa on?',
          'Mikä on oven D03 leveys?',
          'Mikä on ovien paloluokka?',
        ]
      : [
          'How many doors are listed?',
          'What is the width of door D03?',
          'What is the fire rating of these doors?',
        ];
  if (drawing.kind === 'elevation')
    return language === 'fi'
      ? [
          'Kuinka monta ikkunaa kuvassa näkyy?',
          'Kuinka monta ovea kuvassa näkyy?',
        ]
      : ['How many windows are shown?', 'How many doors are shown?'];
  return language === 'fi'
    ? [
        'Kuinka monta ovea kuvassa näkyy?',
        'Kuinka monta ikkunaa kuvassa näkyy?',
        'Mikä on makuuhuoneen 01 nettoala?',
        'Mikä on käytävän leveys?',
      ]
    : [
        'How many doors are shown?',
        'How many windows are shown?',
        'What is the net area of Bedroom 01?',
        'How wide is the corridor?',
      ];
}
