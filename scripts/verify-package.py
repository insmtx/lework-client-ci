"""Check the installed update feed and edition in the packaged Electron preload."""
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from zipfile import ZipFile


def inspect_asar(stream, version, mode):
    _, header_size, _, json_size = struct.unpack("<IIII", stream.read(16))
    header = json.loads(stream.read(json_size))

    def read(name):
        entry = header
        for part in name.split("/"):
            entry = entry["files"][part]
        stream.seek(8 + header_size + int(entry["offset"]))
        return stream.read(entry["size"]).decode()

    if json.loads(read("package.json"))["version"] != version:
        raise ValueError("Wrong packaged version")
    preload = read("out/preload/studio.js")
    match = re.search(r'getBusinessApps\s*:\s*\(\)\s*=>\s*\[\.\.\.\w+\(["\x27]([a-z0-9-]+)["\x27]\)\]', preload)
    if not match or match[1] != mode:
        raise ValueError("Could not verify packaged edition")


def verify_feed(data, expected):
    if f"url: {expected}" not in data.decode().splitlines():
        raise ValueError("Wrong packaged update feed")


def verify(directory, slot, version, mode, feed):
    if slot == "windows-x64":
        tool = os.environ.get("SEVEN_ZIP") or shutil.which("7z")
        if not tool:
            raise ValueError("7-Zip is required on the Windows runner")
        with tempfile.TemporaryDirectory() as tmp:
            archive = directory / f"lework-{version}-setup.exe"
            subprocess.run([tool, "x", "-t7z", "-y", str(archive), f"-o{tmp}",
                            "resources/app.asar", "resources/app-update.yml"],
                           check=True, stdout=subprocess.DEVNULL)
            verify_feed(Path(tmp, "resources/app-update.yml").read_bytes(), feed)
            with Path(tmp, "resources/app.asar").open("rb") as stream:
                inspect_asar(stream, version, mode)
    else:
        suffix = "-arm64" if slot == "macos-arm64" else ""
        with ZipFile(directory / f"LeWork-{version}{suffix}-mac.zip") as archive:
            root = "LeWork.app/Contents/Resources/"
            verify_feed(archive.read(root + "app-update.yml"), feed)
            with archive.open(root + "app.asar") as stream:
                inspect_asar(stream, version, mode)


if __name__ == "__main__":
    verify(Path(sys.argv[1]), sys.argv[2], os.environ["LEWORK_VERSION"],
           os.environ["LEWORK_CUSTOMER_MODE"], Path(".lework-update-url").read_text().strip())
