"""Resolve only the hub candle flame's referenced material registration/stream."""

import hashlib
import importlib
import json
from pathlib import Path
import re
import struct
import sys

from extract_holo_materials import GAME, SOURCE, EXPECTED_BUNDLE_SHA256, check_ownership, read_records
from inspect_hologram import murmur64


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1] / "analysis" / "stock-hub-candle-material-24735202"
MATERIAL = 0xBEA498CE22B86BF9
sys.path.insert(0, str(ROOT / "docs/analysis-flame-target-20260917-a1"))
parser = importlib.import_module("parse_materials")


def main():
    if OUT.exists():
        raise ValueError("Research output already exists")
    check_ownership()
    with SOURCE.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != EXPECTED_BUNDLE_SHA256:
            raise ValueError("Hub bundle has changed")
        handle.seek(268)
        index = list(struct.iter_unpack("<QQI", handle.read(4376 * 20)))
    indices = [i for i, item in enumerate(index) if item[:2] == (murmur64("material"), MATERIAL)]
    if len(indices) != 1 or index[indices[0]][2] != 4:
        raise ValueError("Candle material not uniquely registered in hub")
    entries, chunks = read_records({(murmur64("material"), MATERIAL): f"{MATERIAL:016x}"},
                                   stop_index=indices[0], count_required=1)
    _, at, raw, _ = entries[0]
    pointers = [p.decode() for p in re.findall(rb"data/[0-9a-f]{2}/[0-9a-f]{16}", raw)]
    if len(pointers) != 1:
        raise ValueError("Unexpected candle stream pointers")
    path = GAME / "bundle" / pointers[0]
    installed = json.loads((ROOT / "mods/active/RainbowFlame/payload/manifest.json").read_text())
    vortex = json.loads((GAME / "vortex.deployment.json").read_text())
    relative = "bundle/" + pointers[0]
    if relative.lower() in {row["target"].lower() for row in installed["files"]} or \
       relative.lower() in {row["relPath"].replace("\\", "/").lower() for row in vortex["files"]}:
        raise ValueError("Candle material managed by another mod")
    data = path.read_bytes()
    model = parser.parse(data)
    OUT.mkdir(parents=True)
    (OUT / "candle.material.record").write_bytes(raw)
    report = {"build": "24735202", "hash": f"{MATERIAL:016x}", "index": at,
              "registration_sha256": hashlib.sha256(raw).hexdigest(),
              "bundle_sha256": EXPECTED_BUNDLE_SHA256, "decoded_chunks": chunks,
              "stream": str(path), "stream_sha256": hashlib.sha256(data).hexdigest(),
              "stream_size": len(data), "version": model["version"],
              "shader_bytes": model["shader_size"], "textures": model["textures"],
              "variables": model["variables"]}
    (OUT / "provenance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
