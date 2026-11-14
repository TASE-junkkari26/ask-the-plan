import { IfcImporter } from '@thatopen/fragments';
import { configureImporter } from './config';

self.onmessage = async (
  event: MessageEvent<{ bytes: Uint8Array; wasmPath: string }>,
) => {
  try {
    const { bytes, wasmPath } = event.data;
    if (
      !new TextDecoder()
        .decode(bytes.subarray(0, 4096))
        .includes('ISO-10303-21;')
    )
      throw new Error(
        'This is not a STEP IFC file. Export an uncompressed .ifc file.',
      );
    const importer = new IfcImporter();
    configureImporter(importer, wasmPath);
    const result = await importer.process({
      bytes,
      progressCallback: (progress) => {
        self.postMessage({ type: 'progress', progress });
      },
    });
    self.postMessage(
      { type: 'result', bytes: result },
      { transfer: [result.buffer as ArrayBuffer] },
    );
  } catch (error) {
    self.postMessage({
      type: 'error',
      message:
        error instanceof Error ? error.message : 'IFC conversion failed.',
    });
  }
};
