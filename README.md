# LeWork Desktop CI

Open [LeWork Desktop Build](https://github.com/insmtx/lework-client-ci/actions/workflows/desktop-package.yml) → **Run workflow**. Use the separate **Desktop Runner Check** workflow to check Ubuntu, Windows and macOS runner availability. The optional runner-check switch on the build form calls the same workflow for compatibility. It needs no Secrets.

For a desktop build, configure the following in **Settings → Secrets and variables → Actions** first.

| Secret | Value |
| --- | --- |
| `LEWORK_SOURCE_URL` | Private GitLab HTTPS clone URL without credentials |
| `LEWORK_SOURCE_USERNAME`, `LEWORK_SOURCE_TOKEN` | Read-only repository credentials |
| `LEWORK_SOURCE_SHA` | Full lowercase SHA of the source commit to build |
| `LEWORK_UPDATE_BASE_URL`, `LEWORK_LEGACY_UPDATE_BASE_URL` | Current and legacy standard update URLs ending in `/releases/latest` |
| `MAC_CERTS`, `MAC_CERTS_PASSWORD` | Base64 Developer ID PKCS#12 bundle and its password |
| `APPLE_API_KEY_P8_BASE64`, `APPLE_API_KEY_ID`, `APPLE_API_ISSUER` | App Store Connect notarization credentials |

Run from `main`. Choose the platform, edition (`customer_mode=standard` or `shanjian`) and version. The default build verifies packages without saving them. For a release build, check **Save verified packages to private release staging**. Runner checks skip packaging. Existing scripts calling `desktop-build.yml` with `customer` are forwarded as `shanjian`.

### Release handoff

Configure repository variables `LEWORK_STAGING_BUCKET` and `LEWORK_STAGING_ENDPOINT` (HTTPS OSS endpoint). Use the existing release bucket and a private prefix, `ci-staging/desktop/`. Configure `LEWORK_STAGING_KEY_ID` and `LEWORK_STAGING_KEY_SECRET` as Secrets for an identity limited to putting private objects under that prefix. The release identity needs read access there. Configure expiry on the staging prefix to match your retention period.

Each platform uploads its verified packages, updater metadata and a SHA-256 receipt under the run ID and attempt. The receipt is written last. An anonymous probe must receive HTTP 403 before payload upload. Private build details are suppressed in public Actions logs. Use the successful run ID for the release dry run. The private publisher remains available for the standard edition.

### Publish a staged Shanjian build

Use **Publish Shanjian desktop to OSS** on `main`. Enter the run ID of a successful
`Desktop shanjian v<version> all staged` build and the same version. Run once
with **dry run** selected, then use the same inputs with dry run cleared to publish.
Both operations use the `shanjian-release` GitHub environment restricted to the
`main` branch. Configure environment secrets `OSS_ACCESS_KEY_ID` and
`OSS_ACCESS_KEY_SECRET` for a dedicated release identity with object read access
under `ci-staging/desktop/` and object read/write access under
`electron/lework/releases/shanjian/` in the configured staging bucket.
The build's staging credentials retain their existing scope.
