import type { ImportedDrawing } from '../types';

export async function importDocument(
  file: File,
  page = 1,
): Promise<ImportedDrawing> {
  if (file.size > 35 * 1024 * 1024)
    throw new Error(
      'Please choose a file smaller than 35 MB for this local preview.',
    );
  if (
    file.type === 'application/pdf' ||
    file.name.toLowerCase().endsWith('.pdf')
  ) {
    const pdfjs = await import('pdfjs-dist');
    const { default: worker } =
      await import('pdfjs-dist/build/pdf.worker.min.mjs?url');
    pdfjs.GlobalWorkerOptions.workerSrc = worker;
    const pdf = await pdfjs.getDocument({
      data: new Uint8Array(await file.arrayBuffer()),
    }).promise;
    try {
      const pdfPage = await pdf.getPage(page);
      const viewport = pdfPage.getViewport({ scale: 1.5 });
      const canvas = document.createElement('canvas');
      canvas.width = Math.ceil(viewport.width);
      canvas.height = Math.ceil(viewport.height);
      const context = canvas.getContext('2d');
      if (!context) throw new Error('Canvas rendering is unavailable.');
      await pdfPage.render({ canvasContext: context, canvas, viewport })
        .promise;
      return {
        file,
        url: canvas.toDataURL('image/png'),
        width: viewport.width,
        height: viewport.height,
        page,
        pages: pdf.numPages,
        kind: 'pdf',
      };
    } finally {
      await pdf.destroy();
    }
  }
  if (!/^image\/(png|jpeg|webp|svg\+xml)$/.test(file.type))
    throw new Error('Choose a PDF, PNG, JPG, WebP, or SVG drawing.');
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () =>
        reject(new Error('This image could not be opened.'));
      image.src = url;
    });
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
