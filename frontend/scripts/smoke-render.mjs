import assert from 'node:assert/strict';
import { createServer } from 'vite';
import { createElement } from 'react';
import { renderToString } from 'react-dom/server';

// Pure server rendering: this does not launch or automate a browser.
const server = await createServer({
  server: { middlewareMode: true, ws: false },
  appType: 'custom',
  logLevel: 'error',
});
try {
  const { default: App } = await server.ssrLoadModule('/src/App.tsx');
  const html = renderToString(createElement(App));
  assert.match(html, /Start with a drawing/);
  assert.match(html, /Select files/);
  assert.match(html, /drag and drop them here/);
  assert.match(html, /type="file"/);
  assert.doesNotMatch(html, /Ground floor|West Harbour|Demo drawings/);
  assert.doesNotMatch(html, /class="drawing-stage|class="answer-panel/);
  assert.doesNotMatch(html, /Question about the drawing/);
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(
    new Set(ids).size,
    ids.length,
    'Rendered element IDs must be unique.',
  );
  console.log(
    'Initial import screen rendered without demo drawings or a chat panel.',
  );
} finally {
  await server.close();
}
