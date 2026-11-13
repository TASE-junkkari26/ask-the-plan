import { compileFromFile } from 'json-schema-to-typescript';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const output = new URL('../src/contracts/', import.meta.url);
await mkdir(output, { recursive: true });
for (const name of ['QueryResult', 'QuestionRequest']) {
  const source = new URL(
    `../../contracts/jsonschema/${name}.schema.json`,
    import.meta.url,
  );
  const type = await compileFromFile(fileURLToPath(source), {
    bannerComment:
      '/* Generated from the shared Python contracts. Run npm run generate:contracts. */',
    style: { singleQuote: true, semi: true },
  });
  await writeFile(new URL(`${name}.ts`, output), type);
}
console.log('Generated frontend request/result wire types.');
