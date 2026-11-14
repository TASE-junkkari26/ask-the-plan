import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import * as WEBIFC from 'web-ifc';
import { recoverInvalidFaces } from './geometryRecovery.ts';

const wasmPath = fileURLToPath(
  new URL('../../node_modules/web-ifc/', import.meta.url),
);
function fixture(lines: string) {
  return new TextEncoder().encode(`ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');
FILE_NAME('geometry-recovery.ifc','2026-11-14T00:00:00',(''),(''),'test','test','');
FILE_SCHEMA(('IFC2X3'));
ENDSEC;
DATA;
#1=IFCCARTESIANPOINT((0.,0.,0.));
#2=IFCCARTESIANPOINT((1.,0.,0.));
#3=IFCCARTESIANPOINT((0.,1.,0.));
#4=IFCDIRECTION((1.,0.,0.));
#10=IFCPOLYLOOP((#1,#2,#3));
#20=IFCFACEOUTERBOUND(#10,.T.);
#31=IFCFACE((#20));
#50=IFCFLOWSEGMENT('0000000000000000000001',$,'121.A - M\\X2\\00E4\\X0\\rk\\X2\\00E4\\X0\\tila',$,$,$,$,'7.16');
#60=IFCPROPERTYSINGLEVALUE('NetArea',$,IFCAREAMEASURE(12.34),$);
${lines}
ENDSEC;
END-ISO-10303-21;
`);
}
async function inspect(
  bytes: Uint8Array,
  check: (api: WEBIFC.IfcAPI, model: number) => void,
) {
  const api = new WEBIFC.IfcAPI();
  api.SetWasmPath(wasmPath, true);
  await api.Init();
  try {
    check(api, api.OpenModel(bytes));
  } finally {
    api.Dispose();
  }
}

test('valid geometry is left alone and does not produce a recovery claim', async () => {
  const bytes = fixture('#40=IFCCLOSEDSHELL((#31));');
  assert.equal(await recoverInvalidFaces(bytes, wasmPath), undefined);
});

test('dangling/non-point vertices and missing bounds/loops omit whole faces, preserving metadata and IDs', async () => {
  const bytes = fixture(`
#11=IFCPOLYLOOP((#1,#2,#999));
#12=IFCPOLYLOOP((#1,#2,#4));
#21=IFCFACEBOUND(#11,.T.);
#22=IFCFACEOUTERBOUND(#12,.T.);
#23=IFCFACEOUTERBOUND(#888,.T.);
#30=IFCFACE((#20,#21));
#32=IFCFACE((#22));
#33=IFCFACE((#23));
#34=IFCFACE((#777));
#40=IFCCLOSEDSHELL((#30,#31,#32,#33,#34));
#41=IFCOPENSHELL((#30,#31));
#42=IFCCONNECTEDFACESET((#30,#31));`);
  const original = bytes.slice();
  const result = await recoverInvalidFaces(bytes, wasmPath);
  assert.ok(result);
  assert.deepEqual(
    bytes,
    original,
    'Original source bytes must remain authoritative and unchanged',
  );
  assert.deepEqual(result.report, {
    omittedFaceCount: 4,
    invalidLoopCount: 2,
    missingPointCount: 1,
    modifiedFaceSetCount: 3,
    sampleFaceIds: [30, 32, 33, 34],
    sampleMissingPointIds: [999],
  });
  await inspect(result.bytes, (api, model) => {
    for (const id of [40, 41, 42])
      assert.deepEqual(
        api
          .GetLine(model, id)
          .CfsFaces.map((ref: { value: number }) => ref.value),
        [31],
      );
    assert.deepEqual(
      api.GetLine(model, 30).Bounds.map((ref: { value: number }) => ref.value),
      [20, 21],
      'Do not fill an invalid inner hole by removing only its bound',
    );
    const product = api.GetLine(model, 50);
    assert.equal(product.GlobalId.value, '0000000000000000000001');
    assert.equal(product.Name.value, '121.A - Märkätila');
    assert.equal(product.Tag.value, '7.16');
    assert.equal(api.GetLine(model, 60).NominalValue.value, 12.34);
    assert.equal(
      api.GetLineIDsWithType(model, WEBIFC.IFCFLOWSEGMENT).size(),
      1,
    );
  });
});

test('orphan invalid topology does not rewrite an otherwise unchanged source', async () => {
  const bytes = fixture(
    '#11=IFCPOLYLOOP((#1,#2,#999));\n#21=IFCFACEBOUND(#11,.T.);\n#30=IFCFACE((#21));\n#40=IFCCLOSEDSHELL((#31));',
  );
  assert.equal(await recoverInvalidFaces(bytes, wasmPath), undefined);
});

test('diagnostic samples stay bounded while omission counts remain exact', async () => {
  const lines: string[] = [];
  const faces: number[] = [];
  for (let index = 0; index < 20; index++) {
    const loop = 100 + index,
      bound = 200 + index,
      face = 300 + index;
    lines.push(
      `#${loop}=IFCPOLYLOOP((#1,#2,#${1000 + index}));`,
      `#${bound}=IFCFACEOUTERBOUND(#${loop},.T.);`,
      `#${face}=IFCFACE((#${bound}));`,
    );
    faces.push(face);
  }
  lines.push(
    `#40=IFCCLOSEDSHELL((#31,${faces.map((id) => `#${id}`).join(',')}));`,
  );
  const result = await recoverInvalidFaces(fixture(lines.join('\n')), wasmPath);
  assert.ok(result);
  assert.equal(result.report.omittedFaceCount, 20);
  assert.equal(result.report.missingPointCount, 20);
  assert.equal(result.report.sampleFaceIds.length, 12);
  assert.deepEqual(
    result.report.sampleFaceIds,
    [300, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311],
  );
  assert.equal(result.report.sampleMissingPointIds.length, 12);
});

test('native API is disposed even if recovery progress handling fails after parsing', async (t) => {
  let disposals = 0;
  const original = WEBIFC.IfcAPI.prototype.Dispose;
  t.mock.method(
    WEBIFC.IfcAPI.prototype,
    'Dispose',
    function (this: WEBIFC.IfcAPI) {
      disposals++;
      original.call(this);
    },
  );
  await assert.rejects(
    recoverInvalidFaces(
      fixture('#40=IFCCLOSEDSHELL((#31));'),
      wasmPath,
      (message) => {
        if (message.includes('face boundaries'))
          throw new Error('preview cancelled');
      },
    ),
    /preview cancelled/,
  );
  assert.equal(disposals, 1);
});
