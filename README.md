# LeWork Desktop CI

Open **Actions → LeWork Desktop Build → Run workflow**. The default **Verify GitHub runner availability without building** option checks the standard Ubuntu, Windows and macOS runners. It needs no Secrets.

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

Run the workflow from the default branch, turn off the runner check, and select the platform, edition and version. The build verifies installers on the runner. It does not upload installers or publish a release. Commands that process private source suppress detailed output because Actions logs are public.
