'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { createServer, PythonBridge } = require('../server');

async function serve(t, bridge) {
  const server = createServer(bridge);
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => { server.close(resolve); server.closeAllConnections(); }));
  return `http://127.0.0.1:${server.address().port}`;
}

test('HTML, locally served Highcharts, and JSON requests use the view adapter', async t => {
  const calls = [];
  const url = await serve(t, { request: async (action, filters) => {
    calls.push({ action, filters }); return { connected: true, metrics: [['Total interns', 2]] };
  } });
  const html = await fetch(url);
  assert.match(await html.text(), /Intern Program/);
  const library = await fetch(url + '/vendor/highcharts.js');
  assert.equal(library.status, 200);
  assert.match(await library.text(), /Highcharts/);
  const response = await fetch(url + '/api/render', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Dashboard-Request': '1' },
    body: JSON.stringify({ filters: { university: 'UANL' } }),
  });
  assert.equal(response.status, 200);
  assert.deepEqual((await response.json()).metrics, [['Total interns', 2]]);
  assert.deepEqual(calls, [{ action: 'render', filters: { university: 'UANL' } }]);
});

test('errors propagate and external origins, unsafe requests, and file paths are blocked', async t => {
  const url = await serve(t, { request: async () => { throw new Error('Workbook closed'); } });
  const request = options => fetch(url + '/api/refresh', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Dashboard-Request': '1' }, body: '{}', ...options,
  });
  const failure = await request();
  assert.equal(failure.status, 422);
  assert.equal((await failure.json()).error, 'Workbook closed');
  assert.equal((await request({ headers: { 'Content-Type': 'application/json' } })).status, 403);
  assert.equal((await request({ headers: { Origin: 'https://example.com', 'Content-Type': 'application/json', 'X-Dashboard-Request': '1' } })).status, 403);
  assert.equal((await request({ body: 'not-json' })).status, 400);
  assert.equal((await fetch(url + '/excel_store.py')).status, 404);
  const foreignHostStatus = await new Promise((resolve, reject) => {
    http.get(url + '/api/state', { headers: { Host: 'attacker.example' } }, response => {
      response.resume(); resolve(response.statusCode);
    }).on('error', reject);
  });
  assert.equal(foreignHostStatus, 403);
});

test('real Python process handles JSON-lines and stays usable after a rejected request', async t => {
  const bridge = new PythonBridge();
  t.after(() => bridge.close());
  const state = await bridge.request('state');
  assert.equal(state.connected, false);
  assert.equal(state.filters.length, 5);
  await assert.rejects(bridge.request('write'), /Unknown dashboard action/);
  const [first, second] = await Promise.all([bridge.request('render'), bridge.request('state')]);
  assert.deepEqual(first, second);
});
