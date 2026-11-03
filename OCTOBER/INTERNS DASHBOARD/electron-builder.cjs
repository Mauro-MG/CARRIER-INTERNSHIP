'use strict';

module.exports = {
  appId: 'local.internprogram.desktop',
  productName: 'Intern Program',
  executableName: 'Intern Program',
  asar: true,
  directories: { output: 'release', buildResources: 'build-resources' },
  files: [
    'desktop/**/*.js', 'server.js', 'public/**/*', 'package.json',
    'build-resources/icon.png', 'node_modules/highcharts/**/*',
    '!**/*.map', '!**/test{,s}/**', '!**/*.xlsx', '!**/*.xls', '!**/*.csv',
  ],
  extraResources: [
    { from: 'build/backend/InternBackend', to: 'backend', filter: ['**/*'] },
    { from: 'packaging/USER-GUIDE.txt', to: 'USER-GUIDE.txt' },
    { from: 'node_modules/highcharts/LICENSE.txt', to: 'licenses/Highcharts-license.txt' },
    { from: 'build/licenses', to: 'licenses/runtime', filter: ['**/*'] },
  ],
  npmRebuild: false,
  forceCodeSigning: false,
  win: {
    signExecutable: false,
    target: [{ target: 'nsis', arch: ['x64'] }, { target: 'portable', arch: ['x64'] }],
    icon: 'build-resources/icon.ico',
    requestedExecutionLevel: 'asInvoker',
    artifactName: 'Intern-Program-${version}-${arch}.${ext}',
  },
  nsis: {
    artifactName: 'Intern-Program-${version}-Setup.exe',
    oneClick: false, perMachine: false, allowElevation: false,
    allowToChangeInstallationDirectory: true,
    createDesktopShortcut: true, createStartMenuShortcut: true,
    shortcutName: 'Intern Program', deleteAppDataOnUninstall: false,
    runAfterFinish: false,
  },
  portable: { artifactName: 'Intern-Program-${version}-Portable.exe', requestExecutionLevel: 'user' },
};
