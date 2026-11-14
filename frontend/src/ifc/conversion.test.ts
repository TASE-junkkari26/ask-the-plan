import { test } from 'node:test';
import assert from 'node:assert/strict';
import { convertIfc } from './conversion.ts';
import type { ConversionInput, ConversionWorker } from './conversion.ts';

const hash = 'a'.repeat(64);
const input: ConversionInput = {
  type: 'read',
  file: new File(['source'], 'model.ifc'),
  wasmPath: '/runtime/',
};
function harness() {
  const sent: unknown[] = [];
  let terminations = 0;
  const worker: ConversionWorker = {
    onerror: null,
    onmessage: null,
    onmessageerror: null,
    postMessage(message: unknown) {
      sent.push(message);
    },
    terminate() {
      terminations++;
    },
  };
  return {
    worker,
    sent,
    get terminations() {
      return terminations;
    },
    message(data: unknown) {
      worker.onmessage?.call(worker as Worker, { data } as MessageEvent);
    },
  };
}

test('IFC conversion sends the immutable File and continues only after a cache miss', async () => {
  const mock = harness();
  const progress: number[] = [];
  const result = convertIfc(
    mock.worker,
    input,
    new AbortController().signal,
    () => undefined,
    (value) => progress.push(value),
  );
  assert.equal((mock.sent[0] as ConversionInput).file, input.file);
  assert.ok(!('bytes' in (mock.sent[0] as object)));
  mock.message({ type: 'hash', hash });
  assert.deepEqual(mock.sent[1], { type: 'convert' });
  mock.message({ type: 'progress', progress: 1.2 });
  const bytes = new Uint8Array([1, 2]);
  mock.message({ type: 'result', bytes });
  assert.deepEqual(await result, { bytes, hash });
  assert.deepEqual(progress, [1]);
  assert.equal(mock.terminations, 1);
  assert.equal(mock.worker.onmessage, null);
});

test('a source hash cache hit terminates the worker without converting', async () => {
  const mock = harness();
  const bytes = new Uint8Array([42]);
  const result = convertIfc(
    mock.worker,
    input,
    new AbortController().signal,
    () => bytes,
    () => assert.fail('No conversion progress expected'),
  );
  mock.message({ type: 'hash', hash });
  assert.equal((await result).bytes, bytes);
  assert.equal(mock.sent.length, 1);
  assert.equal(mock.terminations, 1);
});

test('abort stops pending source reading/hash work and queued responses cannot update the UI', async () => {
  const mock = harness();
  const abort = new AbortController();
  const result = convertIfc(
    mock.worker,
    input,
    abort.signal,
    () => assert.fail('Hash callback after abort'),
    () => assert.fail('Progress callback after abort'),
  );
  const queued = mock.worker.onmessage!;
  abort.abort();
  queued.call(
    mock.worker as Worker,
    { data: { type: 'hash', hash } } as MessageEvent,
  );
  await assert.rejects(result, { name: 'AbortError' });
  assert.equal(mock.terminations, 1);
  assert.equal(mock.sent.length, 1);
});

test('already aborted conversion does not send a File to the worker', async () => {
  const mock = harness();
  const abort = new AbortController();
  abort.abort();
  await assert.rejects(
    convertIfc(
      mock.worker,
      input,
      abort.signal,
      () => undefined,
      () => {},
    ),
    { name: 'AbortError' },
  );
  assert.equal(mock.sent.length, 0);
  assert.equal(mock.terminations, 1);
});

test('worker failures and malformed responses reject once and release resources', async () => {
  for (const data of [
    { type: 'error', message: 'bad IFC' },
    { type: 'result', bytes: new Uint8Array() },
    { type: 'hash', hash: 'invalid' },
  ]) {
    const mock = harness();
    const result = convertIfc(
      mock.worker,
      input,
      new AbortController().signal,
      () => undefined,
      () => {},
    );
    mock.message(data);
    await assert.rejects(result, /bad IFC|unexpected response/);
    assert.equal(mock.terminations, 1);
  }
});

test('a superseded or removed load can reject at hash lookup before conversion starts', async () => {
  const mock = harness();
  const result = convertIfc(
    mock.worker,
    input,
    new AbortController().signal,
    () => {
      throw new DOMException('Removed', 'AbortError');
    },
    () => {},
  );
  mock.message({ type: 'hash', hash });
  await assert.rejects(result, { name: 'AbortError' });
  assert.equal(mock.sent.length, 1);
  assert.equal(mock.terminations, 1);
});

test('native abort is identified separately so the loader can replace its poisoned worker', async () => {
  const mock = harness();
  const pending = convertIfc(
    mock.worker,
    input,
    new AbortController().signal,
    () => undefined,
    () => {},
  );
  mock.message({
    type: 'error',
    code: 'native_geometry_abort',
    message: 'Aborted(native code called abort())',
  });
  await assert.rejects(pending, { name: 'NativeIfcConversionError' });
  assert.equal(mock.terminations, 1);
});

test('partial geometry diagnostics survive conversion and malformed reports reject', async () => {
  const report = {
    omittedFaceCount: 2,
    invalidLoopCount: 2,
    missingPointCount: 1,
    modifiedFaceSetCount: 1,
    sampleFaceIds: [10, 20],
    sampleMissingPointIds: [99],
  };
  for (const diagnostics of [report, { omittedFaceCount: 'unknown' }]) {
    const mock = harness();
    const pending = convertIfc(
      mock.worker,
      input,
      new AbortController().signal,
      () => undefined,
      () => {},
    );
    mock.message({ type: 'hash', hash });
    mock.message({
      type: 'result',
      bytes: new Uint8Array([1]),
      geometryRecovery: diagnostics,
    });
    if (diagnostics === report)
      assert.deepEqual((await pending).geometryRecovery, report);
    else await assert.rejects(pending, /unexpected response/);
  }
});
