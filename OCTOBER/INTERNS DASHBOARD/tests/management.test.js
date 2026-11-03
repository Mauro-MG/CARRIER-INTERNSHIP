'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createServer } = require('../server');

async function fixture(t) {
  const calls = [];
  const server = createServer({ request: async (action, filters, parameters) => {
    calls.push({ action, filters, parameters }); return { ok: true };
  } });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => { server.close(resolve); server.closeAllConnections(); }));
  const url = `http://127.0.0.1:${server.address().port}`;
  const request = (route, method = 'GET', body = {}, headers = {}) => fetch(url + route, {
    method, headers: { ...(method === 'GET' ? {} : { 'Content-Type': 'application/json', 'X-Dashboard-Request': '1' }), ...headers },
    ...(method === 'GET' ? {} : { body: JSON.stringify(body) }),
  });
  return { calls, request };
}

test('local management details, registration, editing, and migration work without login', async t => {
  const { request, calls } = await fixture(t);
  for (const [route, method, action] of [['/api/interns/a', 'GET', 'intern_detail'],
    ['/api/interns', 'POST', 'intern_create'], ['/api/interns/a', 'PATCH', 'intern_update'],
    ['/api/interns/a', 'DELETE', 'intern_delete'],
    ['/api/management/migrate', 'POST', 'intern_migrate']]) {
    assert.equal((await request(route, method)).status, 200);
    assert.equal(calls.at(-1).action, action);
  }
  assert.equal((await request('/api/auth')).status, 404);
  assert.equal((await request('/api/login', 'POST')).status, 404);
});

test('management preserves request boundaries and uses server dates and record identity', async t => {
  const { request, calls } = await fixture(t);
  assert.equal((await request('/api/interns', 'POST', {}, { Origin: 'https://example.com' })).status, 403);
  assert.equal((await request('/api/interns/a', 'PATCH', {}, { 'X-Dashboard-Request': '0' })).status, 403);
  assert.equal((await request('/api/interns/a', 'DELETE', {}, { 'X-Dashboard-Request': '0' })).status, 403);
  assert.equal(calls.length, 0);
  assert.equal((await request('/api/interns/a', 'PATCH', { id: 'other', today: '1900-01-01', fields: { name: 'New' } })).status, 200);
  assert.equal(calls[0].parameters.id, 'a');
  assert.notEqual(calls[0].parameters.today, '1900-01-01');
});
