import { test } from 'node:test';
import assert from 'node:assert/strict';
import { FrameTask, TaskQueue } from './tasks.ts';
const tick = () => new Promise<void>((resolve) => setImmediate(resolve));

test('section bursts coalesce while the last change during an in-flight update is still flushed', async () => {
  const frames: (() => void)[] = [];
  let finishFirst!: () => void;
  let calls = 0;
  const task = new FrameTask(
    async () => {
      if (++calls === 1)
        await new Promise<void>((resolve) => {
          finishFirst = resolve;
        });
    },
    () => new Promise((resolve) => frames.push(resolve)),
  );
  const pending = task.request();
  for (let i = 0; i < 40; i++) task.request();
  assert.equal(frames.length, 1);
  frames.shift()!();
  await tick();
  assert.equal(calls, 1);
  task.request();
  task.request();
  finishFirst();
  await tick();
  assert.equal(frames.length, 1);
  frames.shift()!();
  await pending;
  assert.equal(calls, 2);
});
test('disposing section work skips a scheduled update', async () => {
  let frame!: () => void;
  let calls = 0;
  const task = new FrameTask(
    async () => {
      calls++;
    },
    () =>
      new Promise((resolve) => {
        frame = resolve;
      }),
  );
  const pending = task.request();
  task.dispose();
  frame();
  await pending;
  assert.equal(calls, 0);
});
test('visibility mutations stay ordered, recover after errors, and skip work for a disposed viewer', async () => {
  const queue = new TaskQueue();
  const actions: string[] = [];
  let finish!: () => void;
  const first = queue.run(async () => {
    actions.push('hide-all');
    await new Promise<void>((resolve) => {
      finish = resolve;
    });
    actions.push('show-floor');
  });
  const next = queue.run(async () => {
    actions.push('show-all');
  });
  await tick();
  assert.deepEqual(actions, ['hide-all']);
  finish();
  await Promise.all([first, next]);
  assert.deepEqual(actions, ['hide-all', 'show-floor', 'show-all']);
  await assert.rejects(
    queue.run(async () => {
      throw new Error('failed');
    }),
    /failed/,
  );
  assert.equal(await queue.run(async () => 7), 7);
  const skipped = queue.run(async () => {
    throw new Error('ran after disposal');
  });
  queue.dispose();
  assert.equal(await skipped, undefined);
});
