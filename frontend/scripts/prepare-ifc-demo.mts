import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { IfcImporter } from '@thatopen/fragments';
import { configureImporter, IFC_CONVERTER_ID } from '../src/ifc/config.ts';

const frontend = fileURLToPath(new URL('../', import.meta.url));
const source =
  process.argv[2] ??
  path.resolve(
    frontend,
    '../dataset/junction-dataset/data/ifc_models/kit-fzk-haus_ac20-fzk-haus.ifc',
  );
const bytes = await readFile(source);
const sha256 = createHash('sha256').update(bytes).digest('hex');
if (
  sha256 !== '70cc8ff245fc0894201d96496c031005a5cbd7a96b22d8a1b87c5a883fb77994'
)
  throw new Error(
    'Demo preparation expects the original Junction FZK-Haus IFC. Use a matching copy to preserve its attribution and provenance.',
  );
const importer = new IfcImporter();
configureImporter(importer, path.join(frontend, 'node_modules/web-ifc/'));
const fragments = await importer.process({ bytes });
const output = path.join(frontend, 'public/models');
await mkdir(output, { recursive: true });
await writeFile(path.join(output, 'fzk-haus.frag'), fragments);
await writeFile(
  path.join(output, 'fzk-haus.json'),
  JSON.stringify(
    {
      name: 'FZK-Haus',
      source: path.basename(source),
      sha256,
      sourceBytes: bytes.length,
      converter: IFC_CONVERTER_ID,
      attribution:
        'Institute for Automation and Applied Informatics, Karlsruhe Institute of Technology (KIT)',
      license: 'LicenseRef-KIT-unrestricted',
      sourceUrl:
        'https://www.ifcwiki.org/index.php?title=KIT_IFC_Examples&oldid=552',
    },
    null,
    2,
  ) + '\n',
);
console.log(
  `Prepared FZK-Haus: ${bytes.length} IFC bytes → ${fragments.length} Fragment bytes. SHA-256 ${sha256}`,
);
