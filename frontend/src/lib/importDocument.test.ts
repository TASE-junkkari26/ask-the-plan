import { test } from 'node:test';
import type { TestContext } from 'node:test';
import assert from 'node:assert/strict';
import {
  documentType,
  importDocument,
  MAX_IMPORT_BYTES,
  releaseDrawing,
} from './importDocument.ts';

const file = (name: string, type = '') => new File(['drawing'], name, { type });

test('desktop uploads resolve uppercase extensions and blank or generic MIME types', () => {
  assert.deepEqual(documentType(file('floor.121.A.PNG')), {
    kind: 'image',
    mime: 'image/png',
  });
  assert.deepEqual(
    documentType(file('door-schedule.SVG', 'application/octet-stream')),
    { kind: 'image', mime: 'image/svg+xml' },
  );
  assert.deepEqual(documentType(file('plans.PDF')), {
    kind: 'pdf',
    mime: 'application/pdf',
  });
  assert.deepEqual(documentType(file('drawing', 'image/jpeg')), {
    kind: 'image',
    mime: 'image/jpeg',
  });
  for (const [extension, mime] of [
    ['jpg', 'image/jpeg'],
    ['webp', 'image/webp'],
    ['gif', 'image/gif'],
    ['bmp', 'image/bmp'],
  ])
    assert.equal(documentType(file(`floor.${extension}`)).mime, mime);
});

test('empty, oversized, CAD, IFC, and unknown files have useful import errors', () => {
  assert.throws(() => documentType(new File([], 'empty.pdf')), /empty/);
  const oversized = file('large.png');
  Object.defineProperty(oversized, 'size', {
    configurable: true,
    value: MAX_IMPORT_BYTES + 1,
  });
  assert.throws(() => documentType(oversized), /35 MB/);
  Object.defineProperty(oversized, 'size', { value: MAX_IMPORT_BYTES });
  assert.equal(documentType(oversized).kind, 'image');
  assert.throws(
    () => documentType(file('model.IFC')),
    /IFC preview is not available/,
  );
  assert.throws(() => documentType(file('plan.dwg')), /PDF or SVG/);
  assert.throws(() => documentType(file('plan.dxf')), /PDF or SVG/);
  assert.throws(
    () => documentType(file('notes.txt', 'text/plain')),
    /supported drawing/,
  );
});

function imageHarness(
  t: TestContext,
  mode: 'load' | 'fail' | 'pending' | 'zero' = 'load',
) {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'Image');
  const blobs: Blob[] = [];
  const revoked: string[] = [];
  let image: MockImage;
  class MockImage {
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    naturalWidth = mode === 'zero' ? 0 : 2400;
    naturalHeight = mode === 'zero' ? 0 : 1200;
    constructor() {
      image = this;
    }
    set src(value: string) {
      if (!value || mode === 'pending') return;
      queueMicrotask(() =>
        mode === 'fail' ? this.onerror?.() : this.onload?.(),
      );
    }
  }
  Object.defineProperty(globalThis, 'Image', {
    configurable: true,
    value: MockImage,
  });
  t.after(() => {
    if (original) Object.defineProperty(globalThis, 'Image', original);
    else Reflect.deleteProperty(globalThis, 'Image');
  });
  t.mock.method(URL, 'createObjectURL', (blob: Blob) => {
    blobs.push(blob);
    return 'blob:preview';
  });
  t.mock.method(URL, 'revokeObjectURL', (url: string) => {
    revoked.push(url);
  });
  return {
    blobs,
    revoked,
    get image() {
      return image;
    },
  };
}

test('image preview preserves original file, dimensions, and MIME fallback until released', async (t) => {
  const harness = imageHarness(t);
  const source = file('7.16.SVG');
  const result = await importDocument(source);
  assert.equal(result.file, source);
  assert.deepEqual(
    [result.width, result.height, result.page, result.pages, result.kind],
    [2400, 1200, 1, 1, 'image'],
  );
  assert.equal(harness.blobs[0].type, 'image/svg+xml');
  assert.deepEqual(harness.revoked, []);
  assert.equal(harness.image.onload, null);
  releaseDrawing(result);
  assert.deepEqual(harness.revoked, ['blob:preview']);
});

test('corrupt images release their preview URL', async (t) => {
  const harness = imageHarness(t, 'fail');
  await assert.rejects(
    importDocument(file('corrupt.png')),
    /could not be opened/,
  );
  assert.deepEqual(harness.revoked, ['blob:preview']);
});

test('zero-dimension images are not accepted as visible drawings', async (t) => {
  const harness = imageHarness(t, 'zero');
  await assert.rejects(
    importDocument(file('empty-view.svg')),
    /no visible dimensions/,
  );
  assert.deepEqual(harness.revoked, ['blob:preview']);
});

test('cancelling image decoding clears handlers and releases the pending URL', async (t) => {
  const harness = imageHarness(t, 'pending');
  const controller = new AbortController();
  const pending = importDocument(file('slow.jpg'), 1, controller.signal);
  controller.abort();
  await assert.rejects(pending, { name: 'AbortError' });
  assert.deepEqual(harness.revoked, ['blob:preview']);
  assert.equal(harness.image.onload, null);
  assert.equal(harness.image.onerror, null);
});

test('already cancelled previews allocate no URL and invalid pages reject before loading', async (t) => {
  const harness = imageHarness(t);
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(
    importDocument(file('floor.png'), 1, controller.signal),
    { name: 'AbortError' },
  );
  for (const page of [0, -1, 1.5, NaN])
    await assert.rejects(
      importDocument(file('floor.pdf'), page),
      /valid page number/,
    );
  assert.equal(harness.blobs.length, 0);
});
