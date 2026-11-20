#!/usr/bin/env bash
set -euo pipefail

# Run from the source monorepo root. Keep the dependency workaround aligned
# with the existing Electron release pipeline.
node <<'NODE'
const fs = require('node:fs');
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
pkg.workspaces = ['apps/desktop', 'apps/studio', 'apps/agent', 'apps/otterDriver', 'packages/*'];
pkg.dependencies = {
  ...(pkg.dependencies || {}),
  dotenv: pkg.dependencies?.dotenv || pkg.devDependencies?.dotenv || '^17.4.1',
};
pkg.devDependencies ||= {};
// pi-coding-agent imports declarations that are absent in newer codemode
// releases. Preserve the version pair recorded in the reviewed source lockfile.
pkg.overrides = { ...(pkg.overrides || {}), '@earendil-works/pi-codemode': '1.1.0' };
fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2) + '\n');
fs.writeFileSync('bunfig.toml', '[install]\nregistry = "https://registry.npmjs.org"\nlinker = "hoisted"\n');
fs.writeFileSync('apps/desktop/.npmrc', 'electron_mirror=https://npmmirror.com/mirrors/electron/\nelectron_builder_binaries_mirror=https://npmmirror.com/mirrors/electron-builder-binaries/\n');
NODE

rm -f bun.lock bun.lockb
bun pm cache rm || true

installed=false
for attempt in 1 2 3; do
  if bun install --no-save --no-cache --force --registry=https://registry.npmjs.org; then
    installed=true
    break
  fi
  bun pm cache rm || true
  sleep "$((attempt * 10))"
done
if [ "$installed" != true ]; then
  echo 'Dependency installation failed' >&2
  exit 1
fi

node <<'NODE'
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const electronDir = ['node_modules/electron', 'apps/desktop/node_modules/electron']
  .find((candidate) => fs.existsSync(path.join(candidate, 'package.json')));
if (!electronDir) throw new Error('electron package not found');
const dist = path.join(electronDir, 'dist');
if (!fs.existsSync(dist)) {
  const result = spawnSync(process.execPath, [path.join(electronDir, 'install.js')], { stdio: 'inherit' });
  if (result.status !== 0) process.exit(result.status || 1);
}
if (!fs.existsSync(dist)) throw new Error(`Electron dist missing: ${dist}`);
// ffmpeg-static names the Windows binary license ffmpeg.exe.LICENSE, while
// the source packaging script expects ffmpeg.LICENSE on every platform.
if (process.platform === 'win32') {
  const { createRequire } = require('node:module');
  const agentRequire = createRequire(path.resolve('apps/agent/package.json'));
  const binary = agentRequire('ffmpeg-static');
  const actualLicense = `${binary}.LICENSE`;
  const expectedLicense = path.join(path.dirname(binary), 'ffmpeg.LICENSE');
  if (!fs.existsSync(expectedLicense)) {
    if (!fs.existsSync(actualLicense)) throw new Error(`FFmpeg binary license missing: ${actualLicense}`);
    fs.copyFileSync(actualLicense, expectedLicense);
  }
}
NODE

(cd packages/types && bun run build)
