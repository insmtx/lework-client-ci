# LeWork Desktop CI

Open **Actions → LeWork Desktop Build → Run workflow**. The optional **Verify GitHub runner availability without building** mode checks the standard Ubuntu, Windows and macOS runners. It needs no Secrets.

For a desktop build, configure the following in **Settings → Secrets and variables → Actions** first.

| Secret | Value |
| --- | --- |
| `LEWORK_SOURCE_URL` | Private GitLab HTTPS clone URL without credentials |
| `LEWORK_SOURCE_USERNAME`, `LEWORK_SOURCE_TOKEN` | Read-only repository credentials |
| `LEWORK_SOURCE_SHA` | Full lowercase SHA of the source commit to build |
| `LEWORK_UPDATE_BASE_URL`, `LEWORK_LEGACY_UPDATE_BASE_URL` | Current and legacy standard update URLs ending in `/releases/latest` |
| `LEWORK_CUSTOMER_MODE` | Edition key expected by the private source when building the customer edition |
| `MAC_CERTS`, `MAC_CERTS_PASSWORD` | Base64 Developer ID PKCS#12 bundle and its password |
| `APPLE_API_KEY_P8_BASE64`, `APPLE_API_KEY_ID`, `APPLE_API_ISSUER` | App Store Connect notarization credentials |

Run from `main`. Choose the platform, edition and version. The default build verifies packages without saving them. For a release build, check **Save verified packages to private release staging**. Runner checks skip packaging. A customer build rejects a standard or unknown edition key.

### Release handoff

Configure repository variables `LEWORK_STAGING_BUCKET` and `LEWORK_STAGING_ENDPOINT` (HTTPS OSS endpoint). Use the existing release bucket and a private prefix, `ci-staging/desktop/`. Configure `LEWORK_STAGING_KEY_ID` and `LEWORK_STAGING_KEY_SECRET` as Secrets for an identity limited to putting private objects under that prefix. The private publisher needs read access there. Configure expiry on the staging prefix to match your retention period.

Each platform uploads its verified packages, updater metadata and a SHA-256 receipt under the run ID and attempt. The receipt is written last. An anonymous probe must receive HTTP 403 before payload upload. Private build details are suppressed in public Actions logs. The private publisher consumes the run ID; choose a dry run there first. Publication of installer downloads and update manifests is a separate operation.
