import type { ImportedDrawing } from '../types';

export const MAX_IMPORT_BYTES = 35 * 1024 * 1024;
const imageTypes: Record<string, string> = {
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  webp: 'image/webp',
  svg: 'image/svg+xml',
  gif: 'image/gif',
  bmp: 'image/bmp',
};
export const IMPORT_ACCEPT =
  '.pdf,' +
  Object.keys(imageTypes)
    .map((ext) => `.${ext}`)
    .join(',');
export const IMPORT_FORMATS = 'PDF, PNG, JPG, WebP, SVG, GIF, BMP';

export function documentType(file: File): {
  kind: 'pdf' | 'image';
  mime: string;
} {
  if (file.size === 0) throw new Error('This file is empty.');
  if (file.size > MAX_IMPORT_BYTES)
    throw new Error('Choose a file no larger than 35 MB for local preview.');
  const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
  if (extension === 'ifc')
    throw new Error(
      'IFC preview is not available yet. Choose a 2D image or PDF.',
    );
  if (extension === 'dwg' || extension === 'dxf')
    throw new Error('Export this CAD drawing as PDF or SVG to preview it.');
  if (file.type === 'application/pdf' || extension === 'pdf')
    return { kind: 'pdf', mime: 'application/pdf' };
  // Desktop file pickers and drag-and-drop may omit or generalize the MIME type.
  const mime =
    imageTypes[extension] ??
    (Object.values(imageTypes).includes(file.type) ? file.type : undefined);
  if (!mime) throw new Error(`Choose a supported drawing: ${IMPORT_FORMATS}.`);
  return { kind: 'image', mime };
}

export function releaseDrawing(drawing: Pick<ImportedDrawing, 'url'>) {
  if (drawing.url.startsWith('blob:')) URL.revokeObjectURL(drawing.url);
}

async function previewImage(
  file: File,
  mime: string,
  signal?: AbortSignal,
): Promise<ImportedDrawing> {
  // An explicit MIME type also allows SVG files with a blank file.type to decode.
  const url = URL.createObjectURL(new Blob([file], { type: mime }));
  const image = new Image();
  try {
    await new Promise<void>((resolve, reject) => {
      const finish = (error?: unknown) => {
        image.onload = null;
        image.onerror = null;
        signal?.removeEventListener('abort', abort);
        if (error) reject(error);
        else resolve();
      };
      const abort = () => {
        finish(new DOMException('Preview cancelled.', 'AbortError'));
        image.src = '';
      };
      image.onload = () => finish();
      image.onerror = () =>
        finish(
          new Error(
            'This image could not be opened. It may be damaged or unsupported.',
          ),
        );
      signal?.addEventListener('abort', abort, { once: true });
      if (signal?.aborted) abort();
      else image.src = url;
    });
    signal?.throwIfAborted();
    if (!image.naturalWidth || !image.naturalHeight)
      throw new Error('This image has no visible dimensions.');
    return {
      file,
      url,
      width: image.naturalWidth,
      height: image.naturalHeight,
      page: 1,
      pages: 1,
      kind: 'image',
    };
  } catch (error) {
    URL.revokeObjectURL(url);
    throw error;
  }
}

async function previewPdf(
  file: File,
  page: number,
  signal?: AbortSignal,
): Promise<ImportedDrawing> {
  // The compatibility build supplies newer JS methods on browsers such as Firefox 142.
  const pdfjs = await import('pdfjs-dist/legacy/build/pdf.mjs');
  const { default: worker } =
    await import('pdfjs-dist/legacy/build/pdf.worker.min.mjs?url');
  signal?.throwIfAborted();
  pdfjs.GlobalWorkerOptions.workerSrc = worker;
  const data = new Uint8Array(await file.arrayBuffer());
  signal?.throwIfAborted();
  const task = pdfjs.getDocument({ data });
  const abort = () => {
    void task.destroy().catch(() => {});
  };
  signal?.addEventListener('abort', abort, { once: true });
  let url: string | undefined;
  try {
    const pdf = await task.promise;
    signal?.throwIfAborted();
    if (page > pdf.numPages)
      throw new Error(`This PDF has only ${pdf.numPages} pages.`);
    const pdfPage = await pdf.getPage(page);
    const original = pdfPage.getViewport({ scale: 1 });
    if (!(original.width > 0 && original.height > 0))
      throw new Error('This PDF page has no visible dimensions.');
    // Large architectural sheets must not allocate an unbounded browser canvas.
    const scale = Math.min(
      2,
      4096 / Math.max(original.width, original.height),
      Math.sqrt(8_000_000 / (original.width * original.height)),
    );
    const viewport = pdfPage.getViewport({ scale });
    const canvas = document.createElement('canvas');
    canvas.width = Math.ceil(viewport.width);
    canvas.height = Math.ceil(viewport.height);
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Canvas rendering is unavailable.');
    try {
      signal?.throwIfAborted();
      await pdfPage.render({ canvasContext: context, canvas, viewport })
        .promise;
      signal?.throwIfAborted();
      const blob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob(
          (result) =>
            result
              ? resolve(result)
              : reject(new Error('This PDF page could not be previewed.')),
          'image/png',
        );
      });
      signal?.throwIfAborted();
      url = URL.createObjectURL(blob);
      return {
        file,
        url,
        width: canvas.width,
        height: canvas.height,
        page,
        pages: pdf.numPages,
        kind: 'pdf',
      };
    } finally {
      canvas.width = canvas.height = 0;
    }
  } catch (error) {
    if (url) URL.revokeObjectURL(url);
    signal?.throwIfAborted();
    if (error instanceof Error && error.name === 'PasswordException')
      throw new Error(
        'This PDF is password protected. Open an unlocked copy to preview it.',
      );
    throw new Error(
      error instanceof Error
        ? `PDF preview failed: ${error.message}`
        : 'This PDF could not be opened.',
    );
  } finally {
    signal?.removeEventListener('abort', abort);
    await task.destroy();
  }
}

export async function importDocument(
  file: File,
  page = 1,
  signal?: AbortSignal,
): Promise<ImportedDrawing> {
  signal?.throwIfAborted();
  if (!Number.isInteger(page) || page < 1)
    throw new Error('Choose a valid page number.');
  const type = documentType(file);
  return type.kind === 'pdf'
    ? previewPdf(file, page, signal)
    : previewImage(file, type.mime, signal);
}
