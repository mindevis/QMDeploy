#!/usr/bin/env node
/**
 * Обновляет VERSION и helm/qm-project/Chart.yaml (version, appVersion).
 */
import fs from 'node:fs';

const v = process.argv[2];
if (!v) {
  console.error('usage: bump-qmdeploy.mjs <semver>');
  process.exit(1);
}

fs.writeFileSync('VERSION', `${v}\n`);

const chartPath = 'helm/qm-project/Chart.yaml';
let c = fs.readFileSync(chartPath, 'utf8');
c = c.replace(/^version:.*$/m, `version: ${v}`);
c = c.replace(/^appVersion:.*$/m, `appVersion: "${v}"`);
fs.writeFileSync(chartPath, c);
console.log('QMDeploy bumped to', v);
