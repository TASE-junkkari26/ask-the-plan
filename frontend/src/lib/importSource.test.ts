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

test('512 MiB applies only to IFC and admits the largest supplied models', () => {
  assert.throws(
    () => sourceKind(sizedFile('large.ifc', MAX_IFC_BYTES + 1)),
    /512 MiB/,
  );
  assert.equal(
    sourceKind(sizedFile('sixty5_arc.ifc', 327 * 1024 * 1024)),
    'ifc',
  );
  assert.throws(() => sourceKind(sizedFile('empty.ifc', 0)), /empty/);
  assert.throws(
    () => sourceKind(sizedFile('sheet.pdf', 36 * 1024 * 1024)),
    /35 MB/,
  );
  assert.equal(sourceKind(sizedFile('sheet.PDF', 35 * 1024 * 1024)), 'pdf');
  assert.throws(() => sourceKind(new File(['x'], 'sheet.dwg')), /PDF or SVG/);
});

test('reopening an immutable File reuses its hash without retaining source bytes', () => {
  const cache = new SingleModelCache();
  const file = sizedFile('model.ifc', 200);
  cache.rememberFileHash(file, 'source-hash');
  assert.equal(cache.getFileHash(file), 'source-hash');
  assert.equal(cache.getFileHash(sizedFile('model.ifc', 200)), undefined);
  cache.clear();
  assert.equal(cache.getFileHash(file), undefined);
});

test('removal and new loads invalidate pending cache writes, including unmount', () => {
  const cache = new SingleModelCache();
  const first = cache.beginLoad('first');
  const second = cache.beginLoad('second');
  assert.equal(cache.isCurrent(first), false);
  assert.equal(cache.isCurrent(second), true);
  cache.forget('second');
  assert.equal(cache.isCurrent(second), false);
  const third = cache.beginLoad('third');
  cache.clear();
  assert.equal(cache.isCurrent(third), false);
});

test('duplicate-source cache reuse survives until the last owning import is removed', () => {
  const cache = new SingleModelCache();
  const bytes = new Uint8Array([1]);
  cache.set('first', 'same-hash', bytes);
  assert.equal(cache.get('same-hash', 'second'), bytes);
  cache.forget('first');
  assert.equal(cache.get('same-hash'), bytes);
  cache.forget('second');
  assert.equal(cache.get('same-hash'), undefined);
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
