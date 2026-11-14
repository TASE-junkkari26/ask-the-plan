import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const frontend = fileURLToPath(new URL('../', import.meta.url));
const pkg = JSON.parse(
  await readFile(
    path.join(frontend, 'node_modules/web-ifc/package.json'),
    'utf8',
  ),
);
if (pkg.version !== '0.0.77')
  throw new Error(
    'Update the converter identity and runtime path before upgrading web-ifc.',
  );
const destination = path.join(frontend, 'public/ifc-runtime/web-ifc-0.0.77');
await mkdir(destination, { recursive: true });
await copyFile(
  path.join(frontend, 'node_modules/web-ifc/web-ifc.wasm'),
  path.join(destination, 'web-ifc.wasm'),
);
await copyFile(
  path.join(frontend, 'node_modules/web-ifc/LICENSE.md'),
  path.join(destination, 'LICENSE.md'),
);
await writeFile(path.join(destination, 'version.txt'), `${pkg.version}\n`);
console.log(`Prepared self-hosted web-ifc ${pkg.version} runtime.`);
