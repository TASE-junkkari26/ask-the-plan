import { test } from 'node:test';
import assert from 'node:assert/strict';
import { previewDxf } from './dxfApi.ts';
import { importSource, releaseSource } from './importSource.ts';

const file = new File(['source DXF bytes'], 'pohja.121.A.DXF');
const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer())),
  (n) => n.toString(16).padStart(2, '0')).join('');

function result(overrides: Record<string, unknown> = {}) {
  return { schema_version: '0.1.0', source_sha256: digest,
    svg: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"></svg>',
    width: 100, height: 50, page: 1, layouts: ['Model', 'Piirustus 7.16'], insunits: 6,
    status: 'partial', warnings: ['Preview omitted source features: INSERT (1).'], ...overrides };
}

test('DXF import uploads once to the preview endpoint and preserves original source/layout warnings', async (t) => {
  const blobs: Blob[] = [];
  const revoked: string[] = [];
  t.mock.method(URL, 'createObjectURL', (blob: Blob) => { blobs.push(blob); return 'blob:dxf-preview'; });
  t.mock.method(URL, 'revokeObjectURL', (url: string) => revoked.push(url));
  const calls: RequestInit[] = [];
  t.mock.method(globalThis, 'fetch', async (url: string, init: RequestInit) => {
    assert.equal(url, '/api/dxf/preview');
    calls.push(init);
    return Response.json(result());
  });
  const source = await importSource(file, 'dxf-source');
  assert.equal(source.kind, 'dxf');
  if (source.kind !== 'dxf') throw new Error('Expected DXF');
  assert.equal(source.file, file);
  assert.equal(source.id, 'dxf-source');
  assert.deepEqual([source.width, source.height, source.page, source.pages], [100, 50, 1, 2]);
  assert.equal(source.dxf?.source_sha256, digest);
  assert.equal(source.dxf?.layouts[1], 'Piirustus 7.16');
  assert.equal(source.dxf?.status, 'partial');
  assert.equal(source.dxf?.warnings.length, 1);
  assert.equal('svg' in source.dxf!, false);
  assert.equal(blobs[0].type, 'image/svg+xml');
  const form = calls[0].body as FormData;
  assert.equal(form.get('page'), '1');
  assert.equal((form.get('file') as File).name, file.name);
  assert.equal(calls.length, 1);
  releaseSource(source);
  assert.deepEqual(revoked, ['blob:dxf-preview']);
});

test('selected layout index is sent literally and validated before allocating a preview', async (t) => {
  t.mock.method(URL, 'createObjectURL', () => 'blob:layout');
  t.mock.method(globalThis, 'fetch', async (_url: string, init: RequestInit) => {
    assert.equal((init.body as FormData).get('page'), '2');
    return Response.json(result({ page: 2 }));
  });
  const preview = await previewDxf(file, 2);
  assert.equal(preview.page, 2);
  assert.equal(preview.dxf?.layouts[preview.page - 1], 'Piirustus 7.16');
});

test('wrong source, stale layout, malformed dimensions and unexplained partial previews reject', async (t) => {
  const create = t.mock.method(URL, 'createObjectURL', () => 'blob:unexpected');
  for (const overrides of [
    { source_sha256: 'a'.repeat(64) }, { page: 2 }, { width: 0 }, { height: 4097 },
    { width: 4096, height: 4096 }, { warnings: [] }, { layouts: ['Model', 'Model'] },
    { svg: '<html>proxy failure</html>' }, { insunits: -1 },
  ]) {
    t.mock.method(globalThis, 'fetch', async () => Response.json(result(overrides)));
    await assert.rejects(previewDxf(file, 1), /different source|invalid DXF/);
  }
  assert.equal(create.mock.callCount(), 0);
});

test('DXF preview reports backend configuration/errors and handles proxy HTML', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({ message: 'Install the backend api extra.' }, { status: 503 }));
  await assert.rejects(previewDxf(file, 1), /Install the backend api extra/);
  t.mock.method(globalThis, 'fetch', async () => new Response('<html>Vite</html>', { status: 500 }));
  await assert.rejects(previewDxf(file, 1), /Start the Python API/);
  t.mock.method(globalThis, 'fetch', async () => { throw new TypeError('fetch failed'); });
  await assert.rejects(previewDxf(file, 1), /Start the Python API/);
});

test('DXF preview forwards cancellation and never creates a stale object URL', async (t) => {
  const create = t.mock.method(URL, 'createObjectURL', () => 'blob:unexpected');
  const controller = new AbortController();
  t.mock.method(globalThis, 'fetch', async (_url: string, init: RequestInit) => {
    assert.equal(init.signal, controller.signal);
    controller.abort();
    return Response.json(result());
  });
  await assert.rejects(previewDxf(file, 1, controller.signal), { name: 'AbortError' });
  assert.equal(create.mock.callCount(), 0);
  await assert.rejects(previewDxf(file, 1, controller.signal), { name: 'AbortError' });
});
