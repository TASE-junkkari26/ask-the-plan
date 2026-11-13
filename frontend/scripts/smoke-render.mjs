import assert from 'node:assert/strict';
import { createServer } from 'vite';
import { createElement } from 'react';
import { renderToString } from 'react-dom/server';

// Pure server rendering: this does not launch or automate a browser.
const server = await createServer({
  server: { middlewareMode: true },
  appType: 'custom',
  logLevel: 'error',
});
try {
  const { default: App } = await server.ssrLoadModule('/src/App.tsx');
  const html = renderToString(createElement(App));
  assert.match(html, /Ground floor/);
  assert.match(html, /How many doors are shown/);
  assert.match(html, /Question about the drawing/);
  assert.match(html, /This view only/);
  assert.equal((html.match(/class="evidence-mark /g) ?? []).length, 8);
  assert.equal((html.match(/class="evidence-row /g) ?? []).length, 8);
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(
    new Set(ids).size,
    ids.length,
    'Source/thumbnail SVG IDs must be unique.',
  );
  console.log(
    'Initial workspace rendered with eight matched marks and evidence rows.',
  );
} finally {
  await server.close();
}
