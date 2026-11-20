"""Write one verified platform to a private prefix, completing its receipt last."""
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse
import oss2


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    directory, slot = Path(sys.argv[1]), sys.argv[2]
    version = os.environ["LEWORK_VERSION"]
    names = {
        "windows-x64": [f"lework-{version}-setup.exe", "latest.yml"],
        "macos-arm64": [f"lework-{version}-arm64.dmg", f"LeWork-{version}-arm64-mac.zip", "latest-mac.yml"],
        "macos-x64": [f"lework-{version}-x64.dmg", f"LeWork-{version}-mac.zip", "latest-mac.yml"],
    }[slot]
    files = []
    for name in names:
        path = directory / name
        if not path.stat().st_size:
            raise ValueError("Empty output file")
        files.append(dict(name=name, size=path.stat().st_size, sha256=digest(path)))
    run, attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    prefix = f"ci-staging/desktop/{run}/{attempt}/{slot}/"
    endpoint, bucket_name = os.environ["STAGING_ENDPOINT"], os.environ["STAGING_BUCKET"]
    bucket = oss2.Bucket(oss2.Auth(os.environ["STAGING_KEY_ID"], os.environ["STAGING_KEY_SECRET"]), endpoint, bucket_name)
    private = {"x-oss-object-acl": "private"}
    probe = prefix + "access-check"
    bucket.put_object(probe, b"private staging check", headers=private)
    url = f"https://{bucket_name}.{urlparse(endpoint).hostname}/{probe}"
    try:
        with urllib.request.urlopen(url, timeout=20):
            raise ValueError("Staging prefix is publicly readable")
    except urllib.error.HTTPError as failure:
        if failure.code != 403:
            raise
    for file in files:
        bucket.put_object_from_file(prefix + file["name"], str(directory / file["name"]), headers=private)
    receipt = dict(repository=os.environ["GITHUB_REPOSITORY"], run=run, attempt=attempt,
                   pipeline_sha=os.environ["GITHUB_SHA"], source_sha=os.environ["LEWORK_SOURCE_SHA"],
                   version=version, edition=os.environ["LEWORK_CUSTOMER_MODE"], slot=slot, files=files)
    bucket.put_object(prefix + "receipt.json", json.dumps(receipt).encode(), headers=private)


if __name__ == "__main__":
    main()
