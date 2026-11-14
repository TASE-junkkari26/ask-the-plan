export interface ConversionInput {
  type: 'read';
  file: File;
  wasmPath: string;
  knownHash?: string;
}
export interface ConvertedIfc {
  bytes: Uint8Array;
  hash: string;
}
export type ConversionWorker = Pick<
  Worker,
  'onerror' | 'onmessage' | 'onmessageerror' | 'postMessage' | 'terminate'
>;

/** Own the worker until it succeeds, fails or is aborted. No raw IFC buffer
 * crosses the main thread: File structured cloning shares its immutable data.
 */
export function convertIfc(
  worker: ConversionWorker,
  input: ConversionInput,
  signal: AbortSignal,
  onHash: (hash: string) => Uint8Array | undefined,
  onProgress: (progress: number) => void,
): Promise<ConvertedIfc> {
  return new Promise((resolve, reject) => {
    let settled = false;
    let hash: string | undefined;
    const finish = (result?: ConvertedIfc, error?: unknown) => {
      if (settled) return;
      settled = true;
      worker.onmessage = worker.onerror = worker.onmessageerror = null;
      signal.removeEventListener('abort', abort);
      worker.terminate();
      if (result) resolve(result);
      else reject(error);
    };
    const abort = () =>
      finish(
        undefined,
        new DOMException('IFC conversion cancelled.', 'AbortError'),
      );
    signal.addEventListener('abort', abort, { once: true });
    worker.onerror = () =>
      finish(
        undefined,
        new Error(
          'The IFC conversion worker failed. Check that its worker and WASM assets are available.',
        ),
      );
    worker.onmessageerror = () =>
      finish(
        undefined,
        new Error('The IFC worker returned unreadable model data.'),
      );
    worker.onmessage = ({ data }) => {
      if (settled) return;
      if (signal.aborted) {
        abort();
        return;
      }
      try {
        if (
          data?.type === 'hash' &&
          typeof data.hash === 'string' &&
          /^[a-f0-9]{64}$/.test(data.hash) &&
          !hash
        ) {
          const sourceHash: string = data.hash;
          hash = sourceHash;
          const cached = onHash(sourceHash);
          if (cached) finish({ bytes: cached, hash: sourceHash });
          else worker.postMessage({ type: 'convert' });
        } else if (
          data?.type === 'progress' &&
          hash &&
          Number.isFinite(data.progress)
        ) {
          onProgress(Math.max(0, Math.min(1, data.progress)));
        } else if (
          data?.type === 'result' &&
          hash &&
          data.bytes instanceof Uint8Array &&
          data.bytes.byteLength
        ) {
          finish({ bytes: data.bytes, hash });
        } else if (data?.type === 'error' && typeof data.message === 'string') {
          finish(undefined, new Error(data.message));
        } else {
          finish(
            undefined,
            new Error(
              'The IFC worker returned an unexpected response. Reopen the model to retry.',
            ),
          );
        }
      } catch (error) {
        finish(undefined, error);
      }
    };
    if (signal.aborted) {
      abort();
      return;
    }
    try {
      worker.postMessage(input);
    } catch (error) {
      finish(undefined, error);
    }
  });
}
