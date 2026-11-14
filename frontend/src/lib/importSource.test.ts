import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  importSource,
  MAX_IFC_BYTES,
  releaseSource,
  SOURCE_ACCEPT,
  sourceKind,
} from './importSource.ts';
import { ifcCache, SingleModelCache } from '../ifc/cache.ts';

function sizedFile(name: string, size: number) {
  const file = new File(['IFC'], name, { type: 'application/octet-stream' });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

test('IFC routing precedes the 2D size limit and accepts uppercase desktop filenames', async () => {
  const file = sizedFile('Model.121.A.IFC', MAX_IFC_BYTES);
  assert.equal(sourceKind(file), 'ifc');
  const entry = await importSource(file, 'local-123');
  assert.deepEqual(entry, {
    id: 'local-123',
    kind: 'ifc',
    file,
    name: file.name,
    status: 'idle',
  });
  assert.ok(!('url' in entry));
  assert.ok(!('pages' in entry));
  assert.ok(SOURCE_ACCEPT.includes('.ifc'));
});

test('100 MiB applies only to IFC; invalid and empty files fail independently', () => {
  assert.throws(
    () => sourceKind(sizedFile('large.ifc', MAX_IFC_BYTES + 1)),
    /100 MiB/,
  );
  assert.throws(() => sourceKind(sizedFile('empty.ifc', 0)), /empty/);
  assert.throws(
    () => sourceKind(sizedFile('sheet.pdf', 36 * 1024 * 1024)),
    /35 MB/,
  );
  assert.equal(sourceKind(sizedFile('sheet.PDF', 35 * 1024 * 1024)), 'pdf');
  assert.throws(() => sourceKind(new File(['x'], 'sheet.dwg')), /PDF or SVG/);
});

test('a cancelled IFC registration never creates a library entry', async () => {
  const abort = new AbortController();
  abort.abort();
  await assert.rejects(
    importSource(sizedFile('model.ifc', 500), 'cancelled', abort.signal),
    { name: 'AbortError' },
  );
});

test('converted model cache evicts older buffers and is scoped to source removal', () => {
  const cache = new SingleModelCache();
  const first = new Uint8Array([1]);
  const second = new Uint8Array([2]);
  cache.set('source-1', 'hash-1:config-v1', first);
  assert.equal(cache.get('hash-1:config-v2'), undefined);
  assert.equal(cache.get('hash-1:config-v1'), first);
  cache.set('source-2', 'hash-2:config-v1', second);
  assert.equal(cache.get('hash-1:config-v1'), undefined);
  cache.forget('source-1');
  assert.equal(cache.get('hash-2:config-v1'), second);
  cache.forget('source-2');
  assert.equal(cache.get('hash-2:config-v1'), undefined);
});

test('removing IFC releases its converted cache without treating it as a 2D URL', async () => {
  const entry = await importSource(sizedFile('model.ifc', 100), 'model');
  ifcCache.set('model', 'hash:converter', new Uint8Array([1]));
  releaseSource(entry);
  assert.equal(ifcCache.get('hash:converter'), undefined);
});
