import * as WEBIFC from 'web-ifc';

/** Diagnostics refer to the original source STEP IDs, not viewer item IDs. */
export interface GeometryRecoveryReport {
  omittedFaceCount: number;
  invalidLoopCount: number;
  missingPointCount: number;
  modifiedFaceSetCount: number;
  sampleFaceIds: number[];
  sampleMissingPointIds: number[];
}

const SAMPLE_LIMIT = 12;
const boundTypes = new Set([WEBIFC.IFCFACEBOUND, WEBIFC.IFCFACEOUTERBOUND]);

function sample(ids: Set<number>) {
  const selected: number[] = [];
  for (const id of ids) {
    if (selected.length === SAMPLE_LIMIT && id >= selected[selected.length - 1])
      continue;
    selected.push(id);
    selected.sort((a, b) => a - b);
    if (selected.length > SAMPLE_LIMIT) selected.pop();
  }
  return selected;
}

function reference(value: unknown): number | undefined {
  if (!value || typeof value !== 'object' || !('value' in value))
    return undefined;
  const id = value.value;
  return typeof id === 'number' && Number.isSafeInteger(id) && id > 0
    ? id
    : undefined;
}

/** Build a partial rendering derivative after a native tessellation abort.
 *
 * Never invent missing points, fill a broken hole, delete products/properties,
 * or mutate the caller's original source bytes. Remove whole invalid faces only
 * from connected/shell face lists. Retaining their records preserves source IDs
 * and makes omissions explicit; the original source remains authoritative.
 * Run in a fresh worker because a native abort can poison its WASM instance.
 */
export async function recoverInvalidFaces(
  bytes: Uint8Array,
  wasmPath: string,
  progress?: (message: string) => void,
): Promise<{ bytes: Uint8Array; report: GeometryRecoveryReport } | undefined> {
  const api = new WEBIFC.IfcAPI();
  api.SetWasmPath(wasmPath, true);
  let initialized = false;
  try {
    progress?.('Checking source geometry references…');
    await api.Init();
    initialized = true;
    api.SetLogLevel(WEBIFC.LogLevel.LOG_LEVEL_OFF);
    // No geometry processing occurs here; placements and source quantities stay
    // in their original coordinates/units for the normal importer afterward.
    const model = api.OpenModel(bytes);
    if (model < 0)
      throw new Error(
        'The source IFC could not be parsed for geometry recovery.',
      );
    const visit = (
      type: number,
      callback: (
        line: ReturnType<WEBIFC.IfcAPI['GetLine']>,
        id: number,
      ) => void,
    ) => {
      const ids = api.GetLineIDsWithType(model, type, true);
      for (let index = 0; index < ids.size(); index++) {
        const id = ids.get(index);
        callback(api.GetLine(model, id), id);
      }
    };
    const invalidLoops = new Set<number>();
    const missingPoints = new Set<number>();
    const pointTypes = new Map<number, number>();
    visit(WEBIFC.IFCPOLYLOOP, (line, id) => {
      const points: unknown[] = Array.isArray(line?.Polygon)
        ? line.Polygon
        : [];
      let invalid = points.length < 3;
      for (const point of points) {
        const pointId = reference(point);
        if (pointId === undefined) {
          invalid = true;
          continue;
        }
        let type = pointTypes.get(pointId);
        if (type === undefined) {
          type = api.GetLineType(model, pointId) as number;
          pointTypes.set(pointId, type);
        }
        if (type !== WEBIFC.IFCCARTESIANPOINT) invalid = true;
        if (type === 0) missingPoints.add(pointId);
      }
      if (invalid) invalidLoops.add(id);
    });
    pointTypes.clear();

    progress?.('Checking face boundaries…');
    const invalidBounds = new Set<number>();
    visit(WEBIFC.IFCFACEBOUND, (line, id) => {
      const loop = reference(line?.Bound);
      if (
        loop === undefined ||
        api.GetLineType(model, loop) === 0 ||
        invalidLoops.has(loop)
      )
        invalidBounds.add(id);
    });

    progress?.('Identifying unrenderable faces…');
    const invalidFaces = new Set<number>();
    visit(WEBIFC.IFCFACE, (line, id) => {
      const bounds: unknown[] = Array.isArray(line?.Bounds) ? line.Bounds : [];
      const invalid =
        !bounds.length ||
        bounds.some((bound) => {
          const boundId = reference(bound);
          return (
            boundId === undefined ||
            !boundTypes.has(api.GetLineType(model, boundId) as number) ||
            invalidBounds.has(boundId)
          );
        });
      if (invalid) invalidFaces.add(id);
    });
    if (!invalidFaces.size) return undefined;

    progress?.('Preparing a partial geometry preview…');
    let modifiedFaceSetCount = 0;
    const omittedFaces = new Set<number>();
    visit(WEBIFC.IFCCONNECTEDFACESET, (line) => {
      if (!Array.isArray(line?.CfsFaces)) return;
      const kept = line.CfsFaces.filter((face: unknown) => {
        const id = reference(face);
        if (id !== undefined && invalidFaces.has(id)) {
          omittedFaces.add(id);
          return false;
        }
        return true;
      });
      if (kept.length === line.CfsFaces.length) return;
      line.CfsFaces = kept;
      api.WriteLine(model, line);
      modifiedFaceSetCount++;
    });
    // Do not claim recovery or serialize an unchanged source for unrelated
    // native failures, unsupported geometry, or orphan invalid topology.
    if (!omittedFaces.size) return undefined;
    progress?.('Saving the partial rendering derivative…');
    const derived = api.SaveModel(model);
    return {
      bytes: derived,
      report: {
        omittedFaceCount: omittedFaces.size,
        invalidLoopCount: invalidLoops.size,
        missingPointCount: missingPoints.size,
        modifiedFaceSetCount,
        sampleFaceIds: sample(omittedFaces),
        sampleMissingPointIds: sample(missingPoints),
      },
    };
  } finally {
    if (initialized) api.Dispose();
  }
}
