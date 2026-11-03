'use strict';

const http = require('node:http');
const path = require('node:path');
const fs = require('node:fs');
const readline = require('node:readline');
const { spawn } = require('node:child_process');

const ROOT = __dirname;

function pythonExecutable() {
  if (process.env.DASHBOARD_PYTHON) return process.env.DASHBOARD_PYTHON;
  const local = path.join(ROOT, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  return fs.existsSync(local) ? local : (process.platform === 'win32' ? 'python' : 'python3');
}

class PythonBridge {
  constructor({ executable = pythonExecutable(), script = path.join(ROOT, 'dashboard_bridge.py'),
    args = ['-u', script], cwd = ROOT, env = {}, onStderr = chunk => process.stderr.write(chunk) } = {}) {
    this.pending = new Map();
    this.nextId = 0;
    this.failure = null;
    this.closing = false;
    this.child = spawn(executable, args, {
      cwd, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONIOENCODING: 'utf-8', ...env },
    });
    this.child.stderr.on('data', onStderr);
    this.child.on('error', error => this.fail(new Error(`Could not start Python: ${error.message}. Set DASHBOARD_PYTHON to your Python executable.`)));
    this.child.on('exit', () => this.fail(new Error('The Python connection stopped. Restart the dashboard.')));
    this.child.stdin.on('error', error => this.fail(error));
    readline.createInterface({ input: this.child.stdout }).on('line', line => {
      let response;
      try { response = JSON.parse(line); }
      catch { this.fail(new Error('Invalid response from the Python connection.')); this.child.kill(); return; }
      const request = this.pending.get(response.id);
      if (!request) return;
      clearTimeout(request.timer);
      this.pending.delete(response.id);
      if (response.ok) request.resolve(response.data);
      else request.reject(new Error(response.error || 'Could not load the dashboard.'));
      if (this.closing && !this.pending.size) this.child.stdin.end();
    });
  }

  request(action, filters = {}, parameters = {}) {
    if (this.closing) return Promise.reject(new Error('The dashboard is shutting down.'));
    if (this.failure) return Promise.reject(this.failure);
    if (this.pending.size >= 16) return Promise.reject(new Error('The dashboard is busy. Try again shortly.'));
    const id = ++this.nextId;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.fail(new Error('Excel took too long to respond. Resolve any Excel prompts and restart the dashboard.'));
        this.child.kill();
      }, 60000);
      this.pending.set(id, { resolve, reject, timer });
      this.child.stdin.write(JSON.stringify({ id, action, filters, parameters }) + '\n');
    });
  }

  fail(error) {
    this.failure = error;
    for (const request of this.pending.values()) {
      clearTimeout(request.timer);
      request.reject(error);
    }
    this.pending.clear();
  }

  close() {
    this.fail(new Error('The dashboard is shutting down.'));
    this.child.kill();
  }

  shutdown() {
    if (this.shutdownPromise) return this.shutdownPromise;
    this.closing = true;
    this.shutdownPromise = new Promise(resolve => {
      if (this.child.exitCode !== null || this.child.signalCode !== null) { resolve(); return; }
      this.child.once('close', resolve);
      if (!this.pending.size) this.child.stdin.end();
    });
    return this.shutdownPromise;
  }
}

const ASSETS = {
  '/': ['public/index.html', 'text/html; charset=utf-8'],
  '/styles.css': ['public/styles.css', 'text/css; charset=utf-8'],
  '/management.css': ['public/management.css', 'text/css; charset=utf-8'],
  '/app.js': ['public/app.js', 'text/javascript; charset=utf-8'],
  '/management.js': ['public/management.js', 'text/javascript; charset=utf-8'],
  '/vendor/highcharts.js': ['node_modules/highcharts/highcharts.js', 'text/javascript; charset=utf-8'],
  '/vendor/accessibility.js': ['node_modules/highcharts/modules/accessibility.js', 'text/javascript; charset=utf-8'],
  '/vendor/no-data-to-display.js': ['node_modules/highcharts/modules/no-data-to-display.js', 'text/javascript; charset=utf-8'],
};

function sendJson(response, status, data) {
  response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  response.end(JSON.stringify(data));
}

async function readJson(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > 65536) throw new Error('Dashboard request is too large.');
    chunks.push(chunk);
  }
  const body = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  if (!body || typeof body !== 'object' || Array.isArray(body)) throw new Error('Expected dashboard filters.');
  return body;
}

function todayInMexico() {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Mexico_City', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function createServer(bridge) {
  return http.createServer(async (request, response) => {
    response.setHeader('Cache-Control', 'no-store');
    response.setHeader('X-Content-Type-Options', 'nosniff');
    response.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
    const port = request.socket.localPort;
    const host = `127.0.0.1:${port}`;
    if (request.headers.host !== host || (request.headers.origin && request.headers.origin !== `http://${host}`)) {
      sendJson(response, 403, { error: 'Open the dashboard using its local address.' }); return;
    }
    let url;
    try { url = new URL(request.url, `http://${host}`); }
    catch { sendJson(response, 400, { error: 'Invalid URL.' }); return; }
    const pathname = url.pathname;
    const detail = pathname.match(/^\/api\/interns\/([^/]+)$/);
    if (request.method === 'GET' && (pathname === '/api/interns' || detail)) {
      try {
        const parameters = detail ? { id: decodeURIComponent(detail[1]) } : Object.fromEntries(url.searchParams);
        parameters.today = todayInMexico();
        sendJson(response, 200, await bridge.request(detail ? 'intern_detail' : 'intern_list', {}, parameters));
      } catch (error) { sendJson(response, 422, { error: error.message }); }
      return;
    }
    const managementAction = pathname === '/api/interns' && request.method === 'POST' ? 'intern_create'
      : pathname === '/api/management/migrate' && request.method === 'POST' ? 'intern_migrate'
      : detail && request.method === 'PATCH' ? 'intern_update'
        : detail && request.method === 'DELETE' ? 'intern_delete' : null;
    if (managementAction) {
      if (request.headers['x-dashboard-request'] !== '1' || request.headers['content-type']?.split(';')[0] !== 'application/json') {
        sendJson(response, 403, { error: 'Use the intern management controls.' }); return;
      }
      try {
        const body = await readJson(request);
        const parameters = { ...body, today: todayInMexico() };
        if (detail) parameters.id = decodeURIComponent(detail[1]);
        sendJson(response, 200, await bridge.request(managementAction, {}, parameters));
      } catch (error) { sendJson(response, 422, { error: error.message }); }
      return;
    }
    if (request.method === 'GET' && pathname === '/api/state') {
      try { sendJson(response, 200, await bridge.request('state')); }
      catch (error) { sendJson(response, 503, { error: error.message }); }
      return;
    }
    const action = { '/api/connect': 'connect', '/api/refresh': 'refresh', '/api/render': 'render' }[pathname];
    if (request.method === 'POST' && action) {
      if (request.headers['x-dashboard-request'] !== '1' || request.headers['content-type']?.split(';')[0] !== 'application/json') {
        sendJson(response, 403, { error: 'Use the dashboard controls to load data.' }); return;
      }
      let body;
      try { body = await readJson(request); }
      catch { sendJson(response, 400, { error: 'Invalid dashboard request.' }); return; }
      try { sendJson(response, 200, await bridge.request(action, body.filters ?? {})); }
      catch (error) { sendJson(response, 422, { error: error.message }); }
      return;
    }
    const asset = ASSETS[pathname];
    if (request.method === 'GET' && asset) {
      try {
        const content = await fs.promises.readFile(path.join(ROOT, asset[0]));
        response.writeHead(200, { 'Content-Type': asset[1] }); response.end(content);
      } catch {
        sendJson(response, 503, { error: 'A dashboard asset is missing. Run npm install in the app folder.' });
      }
      return;
    }
    sendJson(response, 404, { error: 'Not found.' });
  });
}

async function main() {
  if (!fs.existsSync(path.join(ROOT, 'node_modules/highcharts/highcharts.js'))) {
    throw new Error('Highcharts is missing. Run npm install in the app folder first.');
  }
  const port = process.env.PORT === undefined ? 3210 : Number(process.env.PORT);
  if (!Number.isInteger(port) || port < 0 || port > 65535) throw new Error('PORT must be between 0 and 65535.');
  const bridge = new PythonBridge();
  try { await bridge.request('state'); }
  catch (error) { bridge.close(); throw error; }
  const server = createServer(bridge);
  const stop = () => { bridge.close(); server.close(); server.closeAllConnections(); };
  process.once('SIGINT', stop);
  process.once('SIGTERM', stop);
  await new Promise((resolve, reject) => {
    server.once('error', error => { bridge.close(); reject(error); });
    server.listen(port, '127.0.0.1', resolve);
  });
  const url = `http://127.0.0.1:${server.address().port}`;
  console.log(`Intern Program: ${url}\nKeep this window open. Press Ctrl+C to stop.`);
  if (process.argv.includes('--open')) {
    const command = process.platform === 'win32' ? 'powershell.exe' : (process.platform === 'darwin' ? 'open' : 'xdg-open');
    const args = process.platform === 'win32' ? ['-NoProfile', '-Command', `Start-Process '${url}'`] : [url];
    const browser = spawn(command, args, { windowsHide: true, stdio: 'ignore' });
    browser.on('error', () => console.log(`Open ${url} in your browser.`));
  }
}

if (require.main === module) main().catch(error => { console.error(error.message); process.exitCode = 1; });
module.exports = { PythonBridge, createServer };
