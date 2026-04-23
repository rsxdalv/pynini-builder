#!/usr/bin/env python3
"""Repack the conda-installed pynini as a .whl without any compilation."""

import csv
import hashlib
import base64
import os
import sys
import zipfile
import importlib.metadata
from io import StringIO
from pathlib import Path

dist = importlib.metadata.distribution("pynini")
version = dist.metadata["Version"]
site_packages = Path(str(dist.locate_file("."))).resolve()

pyver = f"cp{sys.version_info.major}{sys.version_info.minor}"
wheel_filename = f"pynini-{version}-{pyver}-{pyver}-win_amd64.whl"
dist_info_dir = f"pynini-{version}.dist-info"

os.makedirs("dist", exist_ok=True)
output = os.path.join("dist", wheel_filename)


def sha256_digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return "sha256=" + base64.urlsafe_b64encode(h.digest()).rstrip(b"=").decode()


# Ensure a valid WHEEL metadata file is present
wheel_meta = None
for rel in dist.files or []:
    if str(rel).replace("\\", "/").endswith(".dist-info/WHEEL"):
        wheel_meta = (site_packages / rel).resolve()
        break

generated_wheel_meta: str | None = None
if wheel_meta is None or not wheel_meta.exists():
    generated_wheel_meta = (
        "Wheel-Version: 1.0\n"
        "Generator: repack_wheel\n"
        "Root-Is-Purelib: false\n"
        f"Tag: {pyver}-{pyver}-win_amd64\n"
    )
    print("No WHEEL metadata found in dist-info; generating one.")

records: list[tuple] = []
with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as whl:
    for rel in dist.files or []:
        arc = str(rel).replace("\\", "/")
        if arc.endswith("/RECORD"):
            continue  # regenerated below
        abs_path = (site_packages / rel).resolve()
        if abs_path.is_file():
            with open(abs_path, "rb") as f:
                data = f.read()
            whl.writestr(arc, data)
            records.append((arc, sha256_digest(abs_path), abs_path.stat().st_size))

    # Inject generated WHEEL file when the conda package lacks one
    if generated_wheel_meta is not None:
        arc = f"{dist_info_dir}/WHEEL"
        data = generated_wheel_meta.encode()
        whl.writestr(arc, data)
        h = "sha256=" + base64.urlsafe_b64encode(
            hashlib.sha256(data).digest()
        ).rstrip(b"=").decode()
        records.append((arc, h, len(data)))

    # Write RECORD
    buf = StringIO()
    w = csv.writer(buf)
    for r in records:
        w.writerow(r)
    w.writerow([f"{dist_info_dir}/RECORD", "", ""])
    whl.writestr(f"{dist_info_dir}/RECORD", buf.getvalue())

print(f"Created: {output}")
