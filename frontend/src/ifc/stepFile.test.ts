import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validateStepFile } from './stepFile.ts';

test('STEP validation accepts source headers, BOM and trailing export comments', async () => {
  await validateStepFile(
    new File(
      [
        '\ufeffISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n/* source comment */',
      ],
      'model.ifc',
    ),
  );
});

test('plain files and truncated IFC reject before full source allocation', async () => {
  await assert.rejects(
    validateStepFile(new File(['not IFC'], 'model.ifc')),
    /not a STEP IFC/,
  );
  await assert.rejects(
    validateStepFile(new File(['ISO-10303-21;\nHEADER;'], 'model.ifc')),
    /end marker is missing/,
  );
});

test('validation reads bounded header/tail slices even for large files', async () => {
  const slices: [number, number | undefined][] = [];
  const source = {
    size: 512 * 1024 * 1024,
    slice(start: number, end?: number) {
      slices.push([start, end]);
      return new Blob([start === 0 ? 'ISO-10303-21;' : 'END-ISO-10303-21;']);
    },
  } as Blob;
  await validateStepFile(source);
  assert.deepEqual(slices, [
    [0, 4096],
    [source.size - 65536, undefined],
  ]);
});
