"""Promote a verified, all-platform Shanjian build from private staging."""
import base64
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from urllib.request import urlopen

import oss2
import yaml

PREFIX = "electron/lework/releases/shanjian"
REPO = "insmtx/lework-client-ci"


def version_tuple(version):
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Invalid release version")
    return tuple(map(int, version.split(".")))


def staged_files(bucket, run, version, directory):
    platforms = {
        "windows-x64": [f"lework-{version}-setup.exe", "latest.yml"],
        "macos-arm64": [f"LeWork-{version}-arm64-mac.zip", f"lework-{version}-arm64.dmg", "latest-mac.yml"],
        "macos-x64": [f"LeWork-{version}-mac.zip", f"lework-{version}-x64.dmg", "latest-mac.yml"],
    }
    source = None
    packages = {}
    for slot, names in platforms.items():
        for attempt in range(run["run_attempt"], 0, -1):
            prefix = f"ci-staging/desktop/{run['id']}/{attempt}/{slot}/"
            try:
                receipt = json.loads(bucket.get_object(prefix + "receipt.json").read())
                break
            except oss2.exceptions.NoSuchKey:
                continue
        else:
            raise ValueError(f"Missing receipt for {slot}")
        expected = dict(repository=REPO, edition="shanjian", slot=slot, run=str(run["id"]),
                        pipeline_sha=run["head_sha"], attempt=str(attempt), version=version)
        if any(receipt.get(key) != value for key, value in expected.items()):
            raise ValueError(f"Incorrect build receipt for {slot}")
        commit = receipt["source_sha"]
        if not re.fullmatch(r"[0-9a-f]{40}", commit) or (source and source != commit):
            raise ValueError("Inconsistent source commit")
        source = commit
        entries = receipt["files"]
        if sorted(entry["name"] for entry in entries) != sorted(names):
            raise ValueError(f"Unexpected files for {slot}")
        for entry in entries:
            name = entry["name"]
            path = directory / slot / name
            path.parent.mkdir(exist_ok=True)
            bucket.get_object_to_file(prefix + name, str(path))
            with path.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if not path.stat().st_size or path.stat().st_size != entry["size"] or actual != entry["sha256"]:
                raise ValueError(f"Staged content mismatch for {slot}/{name}")
            if name.endswith(".yml"):
                if yaml.safe_load(path.read_bytes())["version"] != version:
                    raise ValueError(f"Wrong updater version in {slot}")
            else:
                with path.open("rb") as stream:
                    sha = hashlib.file_digest(stream, "sha512").digest()
                packages[name] = (path, sha)
    return packages


def make_manifest(packages, names, version):
    # Keep the ZIPs first for electron-updater, with an entry for each Mac CPU.
    entries = []
    for name in sorted(names, key=lambda n: (not n.endswith(".zip"), n)):
        path, sha = packages[name]
        entries.append(dict(url=name, sha512=base64.b64encode(sha).decode(), size=path.stat().st_size))
    return dict(version=version, files=entries, path=entries[0]["url"], sha512=entries[0]["sha512"])


def verify_stream(stream, expected):
    digest = hashlib.sha512()
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    if digest.digest() != expected:
        raise ValueError("Published package bytes differ from the verified build")


def promote(bucket, origin, packages, version, dry_run):
    manifests = {
        name: make_manifest(packages, names, version)
        for name, names in [
            ("latest.yml", [n for n in packages if n.endswith(".exe")]),
            ("latest-mac.yml", [n for n in packages if not n.endswith(".exe")]),
        ]
    }
    folders = (f"{PREFIX}/v{version}", f"{PREFIX}/latest")
    pending = set()
    for folder in folders:
        for name, desired in manifests.items():
            key = f"{folder}/{name}"
            try:
                current = yaml.safe_load(bucket.get_object(key).read())
            except oss2.exceptions.NoSuchKey:
                continue
            if current == desired:
                continue
            if folder == folders[0] or version_tuple(current["version"]) >= version_tuple(version):
                raise ValueError(f"Conflicting or newer manifest at {key}")
        for name, (_, sha) in packages.items():
            key = f"{folder}/{name}"
            try:
                response = bucket.get_object(key)
            except oss2.exceptions.NoSuchKey:
                pending.add(key)
                continue
            verify_stream(response, sha)
    if dry_run:
        print("Verified three platform receipts and five packages. No objects written.")
        return
    for folder in folders:
        for name, (path, sha) in packages.items():
            key = f"{folder}/{name}"
            if key in pending:
                bucket.put_object_from_file(key, str(path), headers={"x-oss-forbid-overwrite": "true", "Cache-Control": "no-cache"})
            with closing(urlopen(f"{origin}/{key}", timeout=90)) as response:
                verify_stream(response, sha)
    for folder in folders:
        for name, manifest in manifests.items():
            key = f"{folder}/{name}"
            headers = {"Content-Type": "text/yaml", "Cache-Control": "no-cache, must-revalidate"}
            if folder == folders[0]:
                if bucket.object_exists(key):
                    if yaml.safe_load(bucket.get_object(key).read()) != manifest:
                        raise ValueError(f"Immutable manifest changed at {key}")
                    continue
                headers["x-oss-forbid-overwrite"] = "true"
            bucket.put_object(key, yaml.safe_dump(manifest, sort_keys=False).encode(), headers=headers)
    for folder in folders:
        for name, manifest in manifests.items():
            with urlopen(f"{origin}/{folder}/{name}", timeout=30) as response:
                if yaml.safe_load(response.read()) != manifest:
                    raise ValueError(f"Public manifest mismatch for {name}")
    print("Published and verified five packages and both updater manifests.")


def main():
    env = os.environ
    version = env["VERSION"]
    version_tuple(version)
    endpoint = urlsplit(env["OSS_ENDPOINT"])
    if endpoint.scheme != "https" or not re.fullmatch(r"oss-[a-z0-9-]+\.aliyuncs\.com", endpoint.netloc):
        raise ValueError("Expected an Alibaba Cloud HTTPS OSS endpoint")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", env["OSS_BUCKET"]):
        raise ValueError("Invalid OSS bucket")
    if not all(env.get(k) for k in ("OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_SECRET")):
        raise ValueError("Missing OSS release credentials in shanjian-release")
    if env["DRY_RUN"] not in ("true", "false"):
        raise ValueError("Invalid dry run input")
    origin = f"https://{env['OSS_BUCKET']}.{endpoint.netloc}"
    bucket = oss2.Bucket(oss2.Auth(env["OSS_ACCESS_KEY_ID"], env["OSS_ACCESS_KEY_SECRET"]),
                         "https://" + endpoint.netloc, env["OSS_BUCKET"])
    with TemporaryDirectory() as directory:
        run = json.loads(Path(sys.argv[1]).read_bytes())
        packages = staged_files(bucket, run, version, Path(directory))
        promote(bucket, origin, packages, version, env["DRY_RUN"] == "true")


if __name__ == "__main__":
    try:
        main()
    except oss2.exceptions.OssError as error:
        sys.exit(f"OSS rejected the release operation ({error.status}, {error.code})")
