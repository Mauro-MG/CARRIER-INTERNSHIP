'use strict';
// Standalone browser fixture using only disposable local workbook data.
const path = require('node:path');
const { PythonBridge, createServer } = require('../server');

(async () => {
  const bridge = new PythonBridge({ script: path.join(__dirname, 'ui_fixture.py') });
  await bridge.request('state');
  const server = createServer(bridge);
  server.listen(3211, '127.0.0.1', () => console.log('Disposable UI fixture: http://127.0.0.1:3211'));
  const stop = () => { bridge.child.stdin.end(); server.close(); server.closeAllConnections(); };
  process.once('SIGINT', stop); process.once('SIGTERM', stop);
})().catch(error => { console.error(error.message); process.exitCode = 1; });
