'use strict';
const { app, BrowserWindow, Menu, dialog, shell } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const { PythonBridge, createServer } = require('../server');
const { backendOptions } = require('./settings');

app.setName('Intern Program');
if (process.platform === 'win32') app.setAppUserModelId('local.internprogram.desktop');
const smokeArgument = process.argv.find(value => value.startsWith('--smoke-test='));
const smokeOutput = smokeArgument ? path.resolve(smokeArgument.slice('--smoke-test='.length)) : null;
if (smokeOutput) {
  app.setPath('userData', path.join(path.dirname(smokeOutput), 'desktop-test-profile'));
  app.disableHardwareAcceleration();
}
const primary = app.requestSingleInstanceLock();
let window, bridge, server, origin, logFile;
let stopping = false, stopped = false;

function log(message) {
  if (logFile) fs.appendFileSync(logFile, `${new Date().toISOString()} ${message}\n`);
}

async function stop() {
  if (stopping) return;
  stopping = true;
  if (server) { server.close(); server.closeIdleConnections(); }
  // EOF is sent only after outstanding Excel work completes; never interrupt a save on normal close.
  if (bridge) await bridge.shutdown();
  if (server) server.closeAllConnections();
  stopped = true;
  log('Application stopped.');
  app.quit();
}

async function smokeTest() {
  const deadline = Date.now() + 20000;
  let result;
  do {
    result = await window.webContents.executeJavaScript(`({
      title: document.title,
      chartCount: document.querySelectorAll('.highcharts-root').length,
      hasManagement: Boolean(document.getElementById('intern-form')),
      hasLogin: Boolean(document.getElementById('admin-login')),
      status: document.getElementById('status').textContent,
      error: document.getElementById('error').hidden ? '' : document.getElementById('error').textContent
    })`);
    if (result.chartCount === 5 && result.hasManagement && !result.hasLogin && !result.error && !result.status.includes('Starting')) break;
    await new Promise(resolve => setTimeout(resolve, 100));
  } while (Date.now() < deadline);
  result.packaged = app.isPackaged;
  result.backend = path.basename(bridge.child.spawnfile);
  result.backendPid = bridge.child.pid;
  result.applicationPid = process.pid;
  result.ok = result.chartCount === 5 && result.hasManagement && !result.hasLogin && !result.error;
  fs.writeFileSync(smokeOutput, JSON.stringify(result, null, 2));
  if (!result.ok) process.exitCode = 1;
  await stop();
}

async function start() {
  const userData = app.getPath('userData');
  fs.mkdirSync(userData, { recursive: true });
  logFile = path.join(userData, 'desktop.log');
  if (fs.existsSync(logFile) && fs.statSync(logFile).size > 2 * 1024 * 1024) fs.renameSync(logFile, logFile + '.previous');
  log(`Starting Intern Program ${app.getVersion()} (${app.isPackaged ? 'packaged' : 'development'}).`);
  bridge = new PythonBridge({ ...backendOptions({ packaged: app.isPackaged, resourcesPath: process.resourcesPath, userData }),
    onStderr: chunk => log(chunk.toString().trim()) });
  await bridge.request('state');
  server = createServer(bridge);
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  origin = `http://127.0.0.1:${server.address().port}`;
  window = new BrowserWindow({ width: 1440, height: 960, minWidth: 1024, minHeight: 720,
    title: 'Intern Program', show: false, backgroundColor: '#F5F7FA',
    icon: path.join(__dirname, '../build-resources/icon.png'),
    webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true, webSecurity: true } });
  const external = target => {
    try { const url = new URL(target); if (url.protocol === 'https:' && (url.hostname === 'www.highcharts.com' || url.hostname === 'highcharts.com')) shell.openExternal(url.href).catch(error => log(error.message)); }
    catch { /* Unrecognized navigation is ignored. */ }
  };
  window.webContents.setWindowOpenHandler(({ url }) => { external(url); return { action: 'deny' }; });
  window.webContents.on('will-navigate', (event, url) => {
    if (url !== origin + '/') { event.preventDefault(); external(url); }
  });
  window.webContents.session.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  window.webContents.session.webRequest.onBeforeRequest({ urls: ['http://*/*', 'https://*/*'] }, (details, callback) => {
    callback({ cancel: new URL(details.url).origin !== origin });
  });
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: 'File', submenu: [{ label: 'Open settings folder', click: () => shell.openPath(userData) }, { type: 'separator' }, { role: 'quit' }] },
    { label: 'Edit', submenu: [{ role: 'undo' }, { role: 'redo' }, { type: 'separator' }, { role: 'cut' }, { role: 'copy' }, { role: 'paste' }, { role: 'selectAll' }] },
    { label: 'View', submenu: [{ role: 'reload' }, { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' }, { role: 'togglefullscreen' }] },
    { label: 'Help', submenu: [{ label: 'About Intern Program', click: () => dialog.showMessageBox(window, { type: 'info', title: 'Intern Program', message: `Intern Program ${app.getVersion()}`, detail: 'Excel-backed intern management with Highcharts. Open your source workbook in desktop Excel, then select Connect to Excel.' }) }] },
  ]));
  if (!smokeOutput) window.once('ready-to-show', () => window.show());
  window.webContents.on('render-process-gone', (_event, details) => log(`Renderer stopped: ${details.reason}`));
  await window.loadURL(origin);
  log('Desktop interface loaded.');
  if (smokeOutput) await smokeTest();
}

if (!primary) app.quit();
else {
  app.on('second-instance', () => { if (window) { if (window.isMinimized()) window.restore(); window.show(); window.focus(); } });
  app.on('window-all-closed', () => app.quit());
  app.on('before-quit', event => { if (!stopped) { event.preventDefault(); stop().catch(error => { log(error.message); bridge?.close(); app.exit(1); }); } });
  app.whenReady().then(start).catch(async error => {
    log(`Startup failed: ${error.message}`);
    if (smokeOutput) fs.writeFileSync(smokeOutput, JSON.stringify({ ok: false, error: error.message }));
    else dialog.showErrorBox('Intern Program could not start', `${error.message}\n\nSee the desktop.log file in ${app.getPath('userData')}.`);
    process.exitCode = 1;
    await stop();
  });
}
