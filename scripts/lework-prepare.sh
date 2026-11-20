#!/usr/bin/env bash
set -euo pipefail

source_dir="${1:-source}"
cd "$source_dir"

if [[ ! "${LEWORK_SOURCE_SHA:-}" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'A full, lowercase 40-character source SHA is required' >&2
  exit 1
fi
if [[ ! "${LEWORK_VERSION:-}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo 'Version must be major.minor.patch' >&2
  exit 1
fi

actual_sha="$(git rev-parse HEAD)"
if [[ "$actual_sha" != "$LEWORK_SOURCE_SHA" ]]; then
  echo 'Source SHA mismatch' >&2
  exit 1
fi

grep -Fxq 'VITE_APP_CHANNEL=lework' apps/desktop/.env.lework
grep -Fxq 'VITE_APP_ID=com.insmtx.lework' apps/desktop/.env.lework
grep -Fxq 'VITE_APP_URL=https://studio.lework.insmtx.com' apps/desktop/.env.lework
grep -Fxq 'VITE_API_URL=https://api.lework.insmtx.com' apps/desktop/.env.lework
grep -Fxq 'VITE_DESKTOP_SCHEME=lework' apps/studio/.env.lework

node --input-type=module <<'NODE'
import { readFileSync, writeFileSync } from 'node:fs'
const path = 'apps/desktop/package.json'
const pkg = JSON.parse(readFileSync(path, 'utf8'))
pkg.version = process.env.LEWORK_VERSION
writeFileSync(path, `${JSON.stringify(pkg, null, 2)}\n`)
NODE

node --input-type=module <<'NODE'
import { readFileSync, writeFileSync } from 'node:fs'
const path = 'apps/desktop/scripts/lework-config.mjs'
const old = process.env.LEWORK_LEGACY_UPDATE_BASE_URL
const target = process.env.LEWORK_UPDATE_BASE_URL
const mode = process.env.LEWORK_CUSTOMER_MODE
if (!mode || !/^[a-z0-9-]+$/.test(mode)) throw new Error('Missing or invalid desktop edition')
for (const url of [old, target]) {
  if (!url || !/^https:\/\/[^\s]+\/releases\/latest$/.test(url)) {
    throw new Error('Both update base URLs must end in /releases/latest')
  }
}
if (process.env.SELECTED_EDITION === 'customer' && mode === 'standard') throw new Error('Customer selection resolved to standard')
const catalog = JSON.parse(readFileSync('tooling/customer-apps/catalog.json', 'utf8')).customers
if (!Object.hasOwn(catalog, mode)) throw new Error('Selected edition is absent from the application catalog')
if (mode !== 'standard') {
  const config = readFileSync('apps/desktop/electron.vite.config.ts', 'utf8')
  const preload = readFileSync('apps/desktop/src/preload/studio.ts', 'utf8')
  if (!config.includes('process.env.LEWORK_CUSTOMER_MODE') || !config.includes('VITE_CUSTOMER_MODE: customerMode') ||
      !preload.includes('resolveCustomerApps(import.meta.env.VITE_CUSTOMER_MODE')) {
    throw new Error('Selected source does not support the customer desktop package')
  }
}
const feed = mode === 'standard' ? target : target.replace('/releases/latest', `/releases/${mode}/latest`)
const text = readFileSync(path, 'utf8')
const from = [old, target].find(value => text.includes(value))
if (!from) throw new Error('Review changed LeWork update configuration')
writeFileSync(path, text.replace(from, feed))
writeFileSync('../.lework-update-url', feed)
NODE

echo 'LeWork source verified.'
