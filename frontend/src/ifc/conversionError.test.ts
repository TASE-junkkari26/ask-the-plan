import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  convertWithGeometryRecovery,
  isNativeIfcAbort,
  NativeIfcConversionError,
} from './conversionError.ts';

test('native abort retries once with a fresh recovery attempt', async () => {
  const attempts: boolean[] = [];
  let notices = 0;
  const result = await convertWithGeometryRecovery(
    async (recover) => {
      attempts.push(recover);
      if (!recover)
        throw new NativeIfcConversionError(
          'Aborted(native code called abort())',
        );
      return 'partial artifact';
    },
    false,
    () => {},
    () => {
      notices++;
    },
  );
  assert.equal(result, 'partial artifact');
  assert.deepEqual(attempts, [false, true]);
  assert.equal(notices, 1);
});

test('ordinary errors and cancellations do not retry', async () => {
  for (const error of [
    new Error('Invalid source'),
    new DOMException('Cancelled', 'AbortError'),
  ]) {
    let calls = 0;
    await assert.rejects(
      convertWithGeometryRecovery(
        async () => {
          calls++;
          throw error;
        },
        false,
        () => {},
        () => assert.fail('Unexpected recovery'),
      ),
      error,
    );
    assert.equal(calls, 1);
  }
});

test('a cancelled source cannot start a recovery worker', async () => {
  const controller = new AbortController();
  let calls = 0;
  await assert.rejects(
    convertWithGeometryRecovery(
      async () => {
        calls++;
        controller.abort();
        throw new NativeIfcConversionError('Aborted()');
      },
      false,
      () => controller.signal.throwIfAborted(),
      () => assert.fail('Recovery after cancellation'),
    ),
    { name: 'AbortError' },
  );
  assert.equal(calls, 1);
});

test('a failed recovery never enters a native-abort retry loop', async () => {
  for (const alreadyRecovering of [false, true]) {
    let calls = 0;
    await assert.rejects(
      convertWithGeometryRecovery(
        async () => {
          calls++;
          throw new NativeIfcConversionError('Aborted()');
        },
        alreadyRecovering,
        () => {},
        () => {},
      ),
      /could not be recovered safely/,
    );
    assert.equal(calls, alreadyRecovering ? 1 : 2);
  }
});

test('native classification distinguishes WASM failures from user cancellation', () => {
  assert.equal(
    isNativeIfcAbort(new WebAssembly.RuntimeError('unreachable')),
    true,
  );
  assert.equal(
    isNativeIfcAbort(new Error('Aborted(native code called abort())')),
    true,
  );
  assert.equal(
    isNativeIfcAbort(new DOMException('Preview cancelled.', 'AbortError')),
    false,
  );
  assert.equal(isNativeIfcAbort(new Error('Invalid STEP header')), false);
});
