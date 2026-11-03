'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { verifyBackend, verifyContents } = require('./verify_package');
const root = path.join(__dirname, '..');

function run(command, args, env) {
  const result = spawnSync(command, args, { cwd: root, stdio: 'inherit', windowsHide: true, env });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${path.basename(command)} failed (exit ${result.status}).`);
}

function main() {
  if (process.platform !== 'win32' || process.arch !== 'x64') throw new Error('Build this Windows x64 package on Windows x64.');
  const python = process.env.DASHBOARD_BUILD_PYTHON || path.join(root, '.venv/Scripts/python.exe');
  if (!fs.existsSync(python)) throw new Error('Create .venv and install requirements-build.txt, or set DASHBOARD_BUILD_PYTHON.');
  const env = { ...process.env, NODE_USE_SYSTEM_CA: '1', ELECTRON_CACHE: path.join(root, '.build-cache/electron'),
    electron_config_cache: path.join(root, '.build-cache/electron'),
    ELECTRON_BUILDER_CACHE: path.join(root, '.build-cache/electron-builder'), CSC_IDENTITY_AUTO_DISCOVERY: 'false' };
  // Build tools may replace their output directories; keep every target inside this checkout.
  for (const relative of ['build/backend', 'build/pyinstaller', 'release']) {
    if (!path.resolve(root, relative).startsWith(path.resolve(root) + path.sep)) throw new Error('Build output escaped the workspace.');
  }
  fs.mkdirSync(path.join(root, 'build'), { recursive: true });
  run(python, ['-m', 'unittest', 'discover', '-s', 'tests', '-v'], env);
  run(process.execPath, ['--test', 'tests/server.test.js', 'tests/management.test.js', 'tests/desktop.test.js'], { ...env, DASHBOARD_PYTHON: python });
  run(python, ['packaging/build_icon.py'], env);
  run(python, ['packaging/collect_licenses.py'], env);
  run(python, ['-m', 'PyInstaller', '--noconfirm', '--distpath', 'build/backend', '--workpath', 'build/pyinstaller', 'packaging/InternBackend.spec'], env);
  verifyBackend(root);
  if (process.argv.includes('--backend-only')) return;
  // Recent Electron packages use an explicit installer instead of a postinstall hook.
  run(process.execPath, [require.resolve('electron/install.js')], env);
  const args = [require.resolve('electron-builder/cli.js'), '--config', 'electron-builder.cjs', '--win', '--x64', '--publish', 'never'];
  if (process.argv.includes('--dir')) args.push('--dir');
  run(process.execPath, args, env);
  verifyContents(root);
  const versions = spawnSync(python, ['-m', 'pip', 'freeze'], { cwd: root, encoding: 'utf8', windowsHide: true });
  fs.writeFileSync(path.join(root, 'release/build-manifest.json'), JSON.stringify({
    application: require('../package.json').version, builtAt: new Date().toISOString(),
    electron: require('electron/package.json').version, builder: require('electron-builder/package.json').version,
    architecture: 'windows-x64', pythonPackages: versions.stdout.trim().split(/\r?\n/),
  }, null, 2));
  console.log('Windows package ready in release/. Run npm run verify:package for packaged startup checks.');
}
if (require.main === module) { try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; } }
