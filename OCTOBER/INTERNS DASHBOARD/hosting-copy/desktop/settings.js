'use strict';
const fs = require('node:fs');
const path = require('node:path');

function backendOptions({ packaged, resourcesPath, userData, environment = process.env }) {
  fs.mkdirSync(userData, { recursive: true });
  const filename = path.join(userData, 'settings.json');
  if (!fs.existsSync(filename)) fs.writeFileSync(filename, JSON.stringify({ fieldMap: {}, backupDirectory: null }, null, 2));
  const settings = JSON.parse(fs.readFileSync(filename, 'utf8'));
  if (!settings || Array.isArray(settings) || typeof settings !== 'object') throw new Error('settings.json must contain a JSON object.');
  const env = {};
  if (!environment.DASHBOARD_FIELD_MAP && settings.fieldMap && Object.keys(settings.fieldMap).length) {
    if (typeof settings.fieldMap !== 'object' || Array.isArray(settings.fieldMap) || !Object.values(settings.fieldMap).every(value => typeof value === 'string')) {
      throw new Error('settings.json fieldMap must contain field names and workbook headers.');
    }
    const mapping = path.join(userData, 'field-map.json');
    fs.writeFileSync(mapping, JSON.stringify(settings.fieldMap));
    env.DASHBOARD_FIELD_MAP = mapping;
  }
  if (!environment.DASHBOARD_BACKUP_DIR && settings.backupDirectory) {
    if (typeof settings.backupDirectory !== 'string' || !path.isAbsolute(settings.backupDirectory)) throw new Error('The backupDirectory setting must be an absolute folder path.');
    env.DASHBOARD_BACKUP_DIR = settings.backupDirectory;
  }
  if (packaged) {
    const executable = path.join(resourcesPath, 'backend', 'InternBackend.exe');
    if (!fs.existsSync(executable)) throw new Error('The bundled Excel backend is missing. Reinstall Intern Program.');
    // All writable application files live outside the installation/portable extraction folder.
    return { executable, args: [], cwd: userData, env };
  }
  return { env };
}

module.exports = { backendOptions };
