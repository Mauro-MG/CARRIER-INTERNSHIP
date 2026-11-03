'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { backendOptions } = require('../desktop/settings');
const { PythonBridge } = require('../server');
const config = require('../electron-builder.cjs');

function folder(t) {
  const root = path.resolve(__dirname);
  const temporary = fs.mkdtempSync(path.join(root, 'run_desktop_'));
  t.after(() => {
    assert.ok(path.resolve(temporary).startsWith(root + path.sep));
    fs.rmSync(temporary, { recursive: true, force: true });
  });
  return temporary;
}

test('packaged backend uses its own executable and writable per-user settings', t => {
  const root = folder(t);
  const resourcesPath = path.join(root, 'installation/resources');
  const userData = path.join(root, 'profile');
  fs.mkdirSync(path.join(resourcesPath, 'backend'), { recursive: true });
  fs.writeFileSync(path.join(resourcesPath, 'backend/InternBackend.exe'), 'fixture');
  fs.mkdirSync(userData);
  fs.writeFileSync(path.join(userData, 'settings.json'), JSON.stringify({ fieldMap: { phone: 'Phone' }, backupDirectory: path.join(root, 'backups') }));
  const options = backendOptions({ packaged: true, resourcesPath, userData, environment: {} });
  assert.equal(options.executable, path.join(resourcesPath, 'backend/InternBackend.exe'));
  assert.deepEqual(options.args, []);
  assert.equal(options.cwd, userData);
  assert.equal(options.env.DASHBOARD_BACKUP_DIR, path.join(root, 'backups'));
  assert.deepEqual(JSON.parse(fs.readFileSync(options.env.DASHBOARD_FIELD_MAP)), { phone: 'Phone' });
});

test('development settings preserve environment overrides and report missing bundle', t => {
  const root = folder(t);
  assert.deepEqual(backendOptions({ packaged: false, userData: root, environment: {} }), { env: {} });
  fs.writeFileSync(path.join(root, 'settings.json'), JSON.stringify({ fieldMap: { phone: 'Phone' }, backupDirectory: path.join(root, 'backups') }));
  const options = backendOptions({ packaged: false, userData: root, environment: { DASHBOARD_FIELD_MAP: 'existing.json', DASHBOARD_BACKUP_DIR: 'existing' } });
  assert.deepEqual(options.env, {});
  assert.throws(() => backendOptions({ packaged: true, userData: root, resourcesPath: root }), /bundled Excel backend is missing/);
});

test('backend shutdown drains work and rejects new requests before terminating', async t => {
  const bridge = new PythonBridge();
  t.after(() => bridge.close());
  const first = bridge.request('state');
  const second = bridge.request('render');
  const finished = bridge.shutdown();
  await assert.rejects(bridge.request('state'), /shutting down/);
  assert.equal((await first).connected, false);
  assert.equal((await second).filters.length, 5);
  await finished;
  assert.equal(bridge.child.exitCode, 0);
});

test('bridge can run a frozen-style executable without interpreter arguments', async t => {
  const code = "require('node:readline').createInterface({input:process.stdin}).on('line',line=>{const q=JSON.parse(line);process.stdout.write(JSON.stringify({id:q.id,ok:true,data:{action:q.action}})+'\\n')})";
  const bridge = new PythonBridge({ executable: process.execPath, args: ['-e', code] });
  t.after(() => bridge.close());
  assert.deepEqual(await bridge.request('state'), { action: 'state' });
  await bridge.shutdown();
});

test('build targets both installer and portable without embedding source workbooks', () => {
  assert.deepEqual(config.win.target.map(value => value.target), ['nsis', 'portable']);
  assert.equal(config.nsis.perMachine, false);
  assert.equal(config.nsis.allowElevation, false);
  assert.equal(config.win.requestedExecutionLevel, 'asInvoker');
  assert.ok(config.files.includes('!**/*.xlsx'));
  assert.ok(!config.files.includes('**/*'));
});
