import type { IfcSource, IfcStatus } from '../types';
import { ifcCache } from './cache';
import { IFC_CONVERTER_ID, IFC_RUNTIME_PATH } from './config';
import { convertIfc } from './conversion';
import { convertWithGeometryRecovery } from './conversionError';

export interface LoadState {
  status: IfcStatus;
  progress?: number;
  message?: string;
}
export async function loadIfc(
  source: IfcSource,
  signal: AbortSignal,
  report: (state: LoadState) => void,
) {
  signal.throwIfAborted();
  const generation = ifcCache.beginLoad(source.id);
  const checkActive = () => {
    signal.throwIfAborted();
    if (!ifcCache.isCurrent(generation))
      throw new DOMException(
        'This IFC load was superseded or removed.',
        'AbortError',
      );
  };
  const keyFor = (hash: string) => `${hash}:${IFC_CONVERTER_ID}`;
  report({ status: 'reading' });
  if (source.file) {
    const file = source.file;
    const knownHash = ifcCache.getFileHash(file);
    const cached = knownHash
      ? ifcCache.get(keyFor(knownHash), source.id)
      : undefined;
    if (cached)
      return {
        bytes: cached,
        hash: knownHash!,
        geometryRecovery: ifcCache.getGeometryRecovery(keyFor(knownHash!)),
      };
    const convert = (recoverGeometry: boolean) =>
      convertIfc(
        new Worker(new URL('./convert.worker.ts', import.meta.url), {
          type: 'module',
        }),
        {
          type: 'read',
          file,
          knownHash: ifcCache.getFileHash(file),
          recoverGeometry,
          wasmPath: new URL(
            `${import.meta.env.BASE_URL}${IFC_RUNTIME_PATH}`,
            location.href,
          ).href,
        },
        signal,
        (hash) => {
          checkActive();
          ifcCache.rememberFileHash(file, hash);
          const existing = ifcCache.get(keyFor(hash), source.id);
          if (!existing) {
            // Keep at most one converted buffer, and release it before parsing.
            ifcCache.evictBuffer();
            report({
              status: 'converting',
              progress: 0,
              ...(recoverGeometry
                ? { message: 'Checking invalid source geometry…' }
                : {}),
            });
          }
          return existing;
        },
        (progress, message) => {
          checkActive();
          report({ status: 'converting', progress, message });
        },
      );
    const result = await convertWithGeometryRecovery(
      convert,
      ifcCache.needsGeometryRecovery(file),
      checkActive,
      () => {
        report({
          status: 'converting',
          progress: 0,
          message:
            'The native geometry parser stopped. Checking for invalid source faces…',
        });
      },
    );
    checkActive();
    const geometryRecovery =
      result.geometryRecovery ??
      ifcCache.getGeometryRecovery(keyFor(result.hash));
    if (geometryRecovery) ifcCache.rememberGeometryRecovery(file);
    ifcCache.set(
      source.id,
      keyFor(result.hash),
      result.bytes,
      geometryRecovery,
    );
    return { ...result, geometryRecovery };
  }
  if (!source.manifestUrl || !source.fragmentUrl)
    throw new Error('This IFC source has no local file or prepared model.');
  const response = await fetch(source.manifestUrl, { signal });
  if (!response.ok)
    throw new Error('The demo manifest is missing. Run prepare:ifc-demo.');
  const manifest = await response.json();
  checkActive();
  if (manifest.converter !== IFC_CONVERTER_ID)
    throw new Error(
      'The demo was built with a different converter. Run prepare:ifc-demo.',
    );
  const hash = manifest.sha256;
  if (typeof hash !== 'string' || !/^[a-f0-9]{64}$/.test(hash))
    throw new Error(
      'The prepared model manifest has an invalid source hash. Run prepare:ifc-demo.',
    );
  const key = keyFor(hash);
  const cached = ifcCache.get(key, source.id);
  if (cached)
    return {
      bytes: cached,
      hash,
      geometryRecovery: ifcCache.getGeometryRecovery(key),
    };
  ifcCache.evictBuffer();
  report({ status: 'reading', message: 'Opening prepared demo…' });
  const modelResponse = await fetch(source.fragmentUrl, { signal });
  if (!modelResponse.ok)
    throw new Error('The demo model is missing. Run prepare:ifc-demo.');
  const bytes = new Uint8Array(await modelResponse.arrayBuffer());
  checkActive();
  ifcCache.set(source.id, key, bytes);
  return { bytes, hash };
}
