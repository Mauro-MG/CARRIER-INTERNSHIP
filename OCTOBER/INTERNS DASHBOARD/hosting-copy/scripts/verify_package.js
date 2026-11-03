'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');

function verifyBackend(root, folder = path.join(root, 'build/backend/InternBackend')) {
  const executable = path.join(folder, 'InternBackend.exe');
  const result = spawnSync(executable, ['--diagnostics'], { encoding: 'utf8', windowsHide: true, timeout: 30000,
    cwd: root, env: { ...process.env, PYTHONHOME: '', PYTHONPATH: '' } });
  if (result.error) throw result.error;
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout.trim());
  assert.ok(report.ok && report.frozen && report.excelSupport && report.localWorkbookSupport);
  const protocol = spawnSync(executable, [], { input: JSON.stringify({ id: 1, action: 'state' }) + '\n',
    encoding: 'utf8', windowsHide: true, timeout: 30000, cwd: root });
  assert.equal(protocol.status, 0, protocol.stderr);
  const state = JSON.parse(protocol.stdout.trim());
  assert.ok(state.ok && state.data.filters.length === 5 && state.data.connected === false);
  console.log('Frozen backend verified: Excel COM imports, calendar logic, workbook utilities, and JSON-lines protocol.');
  return report;
}

function verifyContents(root) {
  const output = path.join(root, 'release/win-unpacked');
  const files = ['Intern Program.exe', 'resources/app.asar', 'resources/backend/InternBackend.exe', 'resources/USER-GUIDE.txt', 'resources/licenses/Highcharts-license.txt'];
  for (const name of files) assert.ok(fs.existsSync(path.join(output, name)), `Missing packaged file: ${name}`);
  const asar = require('@electron/asar');
  const entries = asar.listPackage(path.join(output, 'resources/app.asar')).map(entry => entry.replace(/\\/g, '/'));
  for (const name of ['/desktop/main.js', '/desktop/settings.js', '/server.js', '/public/index.html', '/public/app.js',
    '/public/styles.css', '/public/management.css', '/public/management.js', '/node_modules/highcharts/highcharts.js',
    '/node_modules/highcharts/modules/accessibility.js', '/node_modules/highcharts/modules/no-data-to-display.js']) {
    assert.ok(entries.includes(name), `Missing app asset: ${name}`);
  }
  for (const entry of entries) assert.ok(!/\.(xlsx|xls|csv)$|[\\/]\.venv[\\/]|[\\/]tests[\\/]|[\\/]\.data[\\/]/i.test(entry), `Private/development file included: ${entry}`);
  verifyBackend(root, path.join(output, 'resources/backend'));
  console.log('Package contents verified; workbook files, backups, and test fixtures are excluded.');
}

function verifyDesktop(root, portable = false) {
  const folder = path.join(root, 'build', portable ? 'portable-check' : 'desktop-check');
  fs.mkdirSync(folder, { recursive: true });
  const output = path.join(folder, 'result.json');
  if (fs.existsSync(output)) fs.unlinkSync(output);
  const executable = portable ? path.join(root, `release/Intern-Program-${require('../package.json').version}-Portable.exe`) : path.join(root, 'release/win-unpacked/Intern Program.exe');
  const env = { ...process.env };
  delete env.ELECTRON_RUN_AS_NODE;
  const result = spawnSync(executable, [`--smoke-test=${output}`], { windowsHide: true, encoding: 'utf8', timeout: 90000, env, cwd: folder });
  if (result.error) throw result.error;
  assert.equal(result.status, 0, result.stderr);
  assert.ok(fs.existsSync(output), 'The desktop did not produce a startup report.');
  const report = JSON.parse(fs.readFileSync(output, 'utf8'));
  assert.ok(report.ok && report.packaged, JSON.stringify(report));
  assert.equal(report.backend, 'InternBackend.exe');
  // A normal close must terminate the frozen Python child, rather than leave a background process.
  assert.throws(() => process.kill(report.backendPid, 0), /ESRCH/);
  console.log(`${portable ? 'Portable executable' : 'Packaged desktop'} startup and shutdown verified: 5 Highcharts graphs and complete management interface.`);
}

if (require.main === module) {
  const root = path.join(__dirname, '..');
  try { verifyContents(root); verifyDesktop(root); if (fs.existsSync(path.join(root, `release/Intern-Program-${require('../package.json').version}-Portable.exe`))) verifyDesktop(root, true); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
module.exports = { verifyBackend, verifyContents, verifyDesktop };
