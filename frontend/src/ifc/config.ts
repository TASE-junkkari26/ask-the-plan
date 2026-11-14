import type { IfcImporter } from '@thatopen/fragments';
import {
  IFCUNITASSIGNMENT,
  IFCSIUNIT,
  IFCCONVERSIONBASEDUNIT,
  IFCMEASUREWITHUNIT,
  IFCDERIVEDUNIT,
  IFCDERIVEDUNITELEMENT,
  IFCMONETARYUNIT,
  IFCCONTEXTDEPENDENTUNIT,
  IFCCONVERSIONBASEDUNITWITHOFFSET,
} from 'web-ifc';

// Bump this identity when conversion settings or dependencies change.
export const IFC_CONVERTER_ID =
  'fragments-3.6.1_web-ifc-0.0.77_preserve-source_face-recovery-v3';
export const IFC_RUNTIME_PATH = 'ifc-runtime/web-ifc-0.0.77/';
export function configureImporter(importer: IfcImporter, wasmPath: string) {
  importer.wasm = { absolute: true, path: wasmPath };
  importer.parseOnce = true;
  importer.includeUniqueAttributes = true;
  importer.includeRelationNames = true;
  importer.includeMaterialProperties = true;
  importer.replaceStoreyElevation = false;
  importer.replaceSiteElevation = false;
  importer.distanceThreshold = null;
  for (const type of [
    IFCUNITASSIGNMENT,
    IFCSIUNIT,
    IFCCONVERSIONBASEDUNIT,
    IFCMEASUREWITHUNIT,
    IFCDERIVEDUNIT,
    IFCDERIVEDUNITELEMENT,
    IFCMONETARYUNIT,
    IFCCONTEXTDEPENDENTUNIT,
    IFCCONVERSIONBASEDUNITWITHOFFSET,
  ])
    importer.classes.abstract.add(type);
  importer.webIfcSettings.COORDINATE_TO_ORIGIN = true;
}
