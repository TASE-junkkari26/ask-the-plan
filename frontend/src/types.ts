import type { QueryResult } from './contracts/QueryResult';

export type Language = 'en' | 'fi';
export type DemoKind = 'plan' | 'schedule' | 'elevation';
export interface Drawing {
  id: string;
  code: string;
  title: string;
  titleFi: string;
  level: string;
  kind: DemoKind;
  revision: string;
}
export interface Mark {
  id: string;
  entityId: string;
  ordinal: number;
  label: string;
  detail: string;
  kind: 'box' | 'area' | 'dimension';
  bounds: [number, number, number, number];
  polygon?: number[][];
  holes?: number[][][];
}
export interface TraceStep {
  title: string;
  detail: string;
  expression?: string;
  markIds: string[];
}
/** UI-only presentation resolved from wire results and evidence records. */
export interface DemoResponse {
  result: QueryResult;
  intent: 'doors' | 'windows' | 'area' | 'width' | 'schedule' | 'missing';
  question: string;
  summary: string;
  value: string;
  unit: string;
  description: string;
  marks: Mark[];
  steps: TraceStep[];
}
export interface ImportedDrawing {
  file: File;
  url: string;
  width: number;
  height: number;
  page: number;
  pages: number;
  kind: 'image' | 'pdf';
}
/** A tab-local preview identity, independent of backend source identities. */
export interface LocalDrawing extends ImportedDrawing {
  id: string;
}
