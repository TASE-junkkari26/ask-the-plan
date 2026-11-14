import type { IfcSource, IfcStatus } from '../types';
import { ifcCache } from './cache';
import { IFC_CONVERTER_ID, IFC_RUNTIME_PATH } from './config';

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
  report({ status: 'reading' });
  signal.throwIfAborted();
  let hash: string;
  let bytes: Uint8Array;
  if (source.file) {
    bytes = new Uint8Array(await source.file.arrayBuffer());
    signal.throwIfAborted();
    hash = Array.from(
      new Uint8Array(
        await crypto.subtle.digest('SHA-256', bytes as Uint8Array<ArrayBuffer>),
      ),
      (b) => b.toString(16).padStart(2, '0'),
    ).join('');
  } else {
    const response = await fetch(source.manifestUrl!, { signal });
    if (!response.ok)
      throw new Error('The demo manifest is missing. Run prepare:ifc-demo.');
    const manifest = await response.json();
    if (manifest.converter !== IFC_CONVERTER_ID)
      throw new Error(
        'The demo was built with a different converter. Run prepare:ifc-demo.',
      );
    hash = manifest.sha256;
    bytes = new Uint8Array();
  }
  signal.throwIfAborted();
  const key = `${hash}:${IFC_CONVERTER_ID}`;
  const cached = ifcCache.get(key);
  if (cached) return { bytes: cached, hash };
  // Release the previous model's converted copy before allocating the next one.
  ifcCache.clear();
  if (source.fragmentUrl) {
    report({ status: 'reading', message: 'Opening prepared demo…' });
    const response = await fetch(source.fragmentUrl, { signal });
    if (!response.ok)
      throw new Error('The demo model is missing. Run prepare:ifc-demo.');
    bytes = new Uint8Array(await response.arrayBuffer());
  } else {
    report({ status: 'converting', progress: 0 });
    bytes = await new Promise<Uint8Array>((resolve, reject) => {
      const worker = new Worker(
        new URL('./convert.worker.ts', import.meta.url),
        { type: 'module' },
      );
      const finish = () => {
        worker.terminate();
        signal.removeEventListener('abort', abort);
      };
      const abort = () => {
        finish();
        reject(new DOMException('IFC conversion cancelled.', 'AbortError'));
      };
      signal.addEventListener('abort', abort, { once: true });
      worker.onerror = () => {
        finish();
        reject(
          new Error(
            'The IFC conversion worker failed. Check that the worker and WASM assets are available.',
          ),
        );
      };
      worker.onmessage = ({ data }) => {
        if (data.type === 'progress')
          report({
            status: 'converting',
            progress: Math.max(0, Math.min(1, data.progress)),
            message: data.message,
          });
        else {
          finish();
          if (data.type === 'result') resolve(data.bytes);
          else reject(new Error(data.message));
        }
      };
      worker.postMessage(
        {
          bytes,
          wasmPath: new URL(
            `${import.meta.env.BASE_URL}${IFC_RUNTIME_PATH}`,
            location.href,
          ).href,
        },
        [bytes.buffer],
      );
    });
  }
  signal.throwIfAborted();
  ifcCache.set(source.id, key, bytes);
  return { bytes, hash };
}
