import { IfcImporter } from '@thatopen/fragments';
import { configureImporter } from './config';
import type { ConversionInput } from './conversion';
import { validateStepFile } from './stepFile';

let pending: { bytes: Uint8Array; wasmPath: string } | undefined;
let busy = false;

self.onmessage = async (
  event: MessageEvent<ConversionInput | { type: 'convert' }>,
) => {
  try {
    if (event.data.type === 'read') {
      if (busy || pending)
        throw new Error('The IFC worker is already processing a file.');
      busy = true;
      const { file, wasmPath, knownHash } = event.data;
      await validateStepFile(file);
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (!crypto.subtle)
        throw new Error(
          'Opening IFC files requires HTTPS or localhost for source hashing.',
        );
      const hash =
        knownHash ??
        Array.from(
          new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)),
          (byte) => byte.toString(16).padStart(2, '0'),
        ).join('');
      pending = { bytes, wasmPath };
      busy = false;
      self.postMessage({ type: 'hash', hash });
      return;
    }
    if (event.data.type !== 'convert' || busy || !pending)
      throw new Error('The IFC worker has no pending file to convert.');
    busy = true;
    const { bytes, wasmPath } = pending;
    pending = undefined;
    const importer = new IfcImporter();
    configureImporter(importer, wasmPath);
    let lastProgress = 0;
    const result = await importer.process({
      bytes,
      progressCallback: (progress) => {
        // Some models report per element. Ten updates/second keep the UI smooth
        // without flooding React or the worker message queue on large imports.
        const now = performance.now();
        if (progress < 1 && now - lastProgress < 100) return;
        lastProgress = now;
        self.postMessage({ type: 'progress', progress });
      },
    });
    self.postMessage(
      { type: 'result', bytes: result },
      { transfer: [result.buffer as ArrayBuffer] },
    );
  } catch (error) {
    pending = undefined;
    self.postMessage({
      type: 'error',
      message:
        error instanceof Error ? error.message : 'IFC conversion failed.',
    });
  }
};
