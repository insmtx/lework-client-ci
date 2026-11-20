#!/usr/bin/env bash
set -euo pipefail

source_url="${SOURCE_URL:?LEWORK_SOURCE_URL secret is required}"
source_sha="${LEWORK_SOURCE_SHA:?LEWORK_SOURCE_SHA secret is required}"
username="${SOURCE_USERNAME:?LEWORK_SOURCE_USERNAME secret is required}"
token="${SOURCE_TOKEN:?LEWORK_SOURCE_TOKEN secret is required}"

if [[ ! "$source_url" =~ ^https://[^@[:space:]]+$ || ! "$source_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'Use an HTTPS source URL without embedded credentials and a full commit SHA.' >&2
  exit 1
fi

auth="$(printf '%s:%s' "$username" "$token" | base64 | tr -d '\n')"
printf '::add-mask::%s\n' "$auth"
git init -q source
if ! git -C source -c "http.extraHeader=Authorization: Basic ${auth}" \
  -c http.followRedirects=false fetch --quiet --no-tags --depth=1 "$source_url" "$source_sha" >/dev/null 2>&1; then
  echo 'GitLab checkout failed. Verify the URL, read-only credentials and source SHA.' >&2
  exit 1
fi
git -C source checkout --quiet --detach FETCH_HEAD >/dev/null 2>&1
if [[ "$(git -C source rev-parse HEAD)" != "$source_sha" ]]; then
  echo 'The checked-out source does not match the requested commit.' >&2
  exit 1
fi
echo 'Verified the requested GitLab commit.'
