import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { ItemData, RawRelationData } from '@thatopen/fragments';
import { readSourceProperties } from './properties.ts';

function reader(links: Record<number, Record<string, number[]>>) {
  const fetched: number[] = [];
  return {
    fetched,
    async getItemsData(ids: (number | string)[]) {
      fetched.push(...ids.map(Number));
      return ids.map(
        (id) =>
          ({
            _localId: { value: Number(id) },
            Name: { value: `Original ${id}` },
          }) satisfies ItemData,
      );
    },
    async getRelations(ids?: number[]) {
      return new Map(
        (ids ?? []).map((id) => [
          id,
          { data: links[id] ?? {} } satisfies RawRelationData,
        ]),
      );
    },
  };
}

test('source properties follow forward references and exclude inverse object graphs and cycles', async () => {
  const model = reader({
    1: { IsDefinedBy: [2] },
    2: { DefinesOccurrence: [999], HasProperties: [3] },
    3: { Unit: [4] },
    4: { UnitComponent: [3] },
  });
  const result = await readSourceProperties(model, [1], () => {});
  assert.deepEqual(model.fetched, [1, 2, 3, 4]);
  assert.equal(result.truncated, false);
  const text = JSON.stringify(result.data);
  assert.ok(text.includes('Original 4'));
  assert.ok(!text.includes('DefinesOccurrence'));
  assert.ok(!text.includes('999'));
});

test('large property collections are bounded and reported as partial', async () => {
  const model = reader({
    1: { HasProperties: Array.from({ length: 30 }, (_, i) => i + 2) },
  });
  const result = await readSourceProperties(model, [1], () => {}, 10);
  assert.equal(model.fetched.length, 10);
  assert.equal(result.truncated, true);
  assert.equal((result.data[0].HasProperties as ItemData[]).length, 9);
});

test('selection changes stop further source-property requests', async () => {
  const model = reader({ 1: { HasProperties: [2] } });
  const controller = new AbortController();
  let checks = 0;
  await assert.rejects(
    readSourceProperties(model, [1], () => {
      if (++checks === 2) controller.abort();
      controller.signal.throwIfAborted();
    }),
    { name: 'AbortError' },
  );
  assert.deepEqual(model.fetched, [1]);
});

test('shared references cannot expand a small source graph into an unbounded UI tree', async () => {
  const model = reader({
    1: { HasProperties: [2, 3, 4] },
    2: { Unit: [5] },
    3: { Unit: [5] },
    4: { Unit: [5] },
  });
  const result = await readSourceProperties(model, [1], () => {}, 6);
  assert.equal(result.truncated, true);
  const count = (items: ItemData[]): number =>
    items.reduce(
      (total, item) =>
        total +
        1 +
        Object.values(item)
          .filter((value): value is ItemData[] => Array.isArray(value))
          .reduce((sum, values) => sum + count(values), 0),
      0,
    );
  assert.ok(count(result.data) <= 6);
});

test('very wide source relations cannot overflow the JS stack or bypass the fetch budget', async () => {
  const model = reader({
    1: {
      HasProperties: Array.from({ length: 200_000 }, (_, index) => index + 2),
    },
  });
  const result = await readSourceProperties(model, [1], () => {}, 8);
  assert.equal(model.fetched.length, 8);
  assert.equal(result.truncated, true);
  assert.equal((result.data[0].HasProperties as ItemData[]).length, 7);
});

test('duplicate source references are fetched and shown once', async () => {
  const model = reader({ 1: { HasProperties: [2, 2, 2] } });
  const result = await readSourceProperties(model, [1], () => {});
  assert.deepEqual(model.fetched, [1, 2]);
  assert.equal((result.data[0].HasProperties as ItemData[]).length, 1);
  assert.equal(result.truncated, false);
});
