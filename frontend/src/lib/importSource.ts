import type { LocalSource } from '../types';
import {
  documentType,
  importDocument,
  IMPORT_ACCEPT,
  IMPORT_FORMATS,
  releaseDrawing,
} from './importDocument.ts';
import { forgetIfc } from '../ifc/cache.ts';

export const MAX_IFC_BYTES = 100 * 1024 * 1024;
export const SOURCE_ACCEPT = `${IMPORT_ACCEPT},.ifc`;
export const SOURCE_FORMATS = `${IMPORT_FORMATS}, IFC`;

export function sourceKind(file: File) {
  if (file.name.toLowerCase().endsWith('.ifc')) {
    if (!file.size) throw new Error('This file is empty.');
    if (file.size > MAX_IFC_BYTES)
      throw new Error(
        'Choose an IFC file no larger than 100 MiB for browser conversion.',
      );
    return 'ifc';
  }
  return documentType(file).kind;
}

/** IFC entries are registered immediately; expensive conversion starts on selection. */
export async function importSource(
  file: File,
  id: string,
  signal?: AbortSignal,
): Promise<LocalSource> {
  signal?.throwIfAborted();
  if (sourceKind(file) === 'ifc')
    return { id, kind: 'ifc', file, name: file.name, status: 'idle' };
  return { ...(await importDocument(file, 1, signal)), id };
}

export function releaseSource(source: LocalSource) {
  if (source.kind === 'ifc') forgetIfc(source.id);
  else releaseDrawing(source);
}
