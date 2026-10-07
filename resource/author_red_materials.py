"""Build a bounded offline red-color trial for three pinned hub hologram materials."""

import hashlib
import importlib
import json
from pathlib import Path
import struct
import sys

from inspect_hologram import murmur64


ROOT = Path(__file__).resolve().parents[4]
INPUT = Path(__file__).resolve().parents[1] / "analysis" / "stock-hub-hologram-24735202"
OUT = Path(__file__).resolve().parents[1] / "analysis" / "red-material-trial-24735202"
sys.path.insert(0, str(ROOT / "docs/analysis-flame-target-20260917-a1"))
parser = importlib.import_module("parse_materials")
COLORS = {
    "hologram_bottom": {"base_color": (0.4, 0.02, 0.008)},
    "hologram_side": {"base_color": (0.7, 0.035, 0.014)},
    "hologram": {"base_color": (0.15, 0.0075, 0.003),
                  "material_variable_046f8451": (0.3, 0.015, 0.006)},
}
EXPECTED = {
    "hologram_bottom": "078ed294f4bab50fa984a035d9c94da4e5521da858c148cc52316f5fcfe448e8",
    "hologram_side": "28a94fa9b2a988d8dd93925c40e4687091b6e766f57d1c283eab9fddbaa03a03",
    "hologram": "e0d63444385473b9b4e299318cd3fdc85e2188f9df9da06ab2224a41654cb616",
}


def value_start(data, model):
    c = parser.Cursor(data[model["material_offset"]:model["material_offset"] + model["material_size"]])
    c.read(20)
    for width in ("I", "IQ", "II", "5I"):
        c.array(width)
    size = c.u32()
    if size != model["variable_data_size"]:
        raise ValueError("Material value array size mismatch")
    return model["material_offset"] + c.pos


def build(data, target):
    before = parser.parse(data)
    if before["version"] != 61 or before["parent_hashes"] != ["0000000000000000"] * 2:
        raise ValueError("Unexpected target material profile")
    base = value_start(data, before)
    result = bytearray(data)
    edits = []
    for parameter, color in COLORS[target].items():
        key = f"{murmur64(parameter) >> 32:08x}"
        matched = [row for row in before["variables"] if row["name_hash"] == key]
        if len(matched) != 1 or matched[0]["type"] != "vector3":
            raise ValueError("Source material color descriptor changed")
        row = matched[0]
        offset = base + row["offset"]
        original = data[offset:offset + 12]
        if struct.unpack("<3f", original) != tuple(row["value"]):
            raise ValueError("Source color storage is not byte-aligned to reflection")
        encoded = struct.pack("<3f", *color)
        result[offset:offset + 12] = encoded
        edits.append({"parameter": parameter, "hash": key, "offset": offset,
                      "original": row["value"], "candidate": struct.unpack("<3f", encoded)})
    after = parser.parse(result)
    if len(result) != len(data) or before["shader_offset"] != after["shader_offset"] or \
       before["shader_size"] != after["shader_size"]:
        raise ValueError("Unexpected material extent mutation")
    restored = bytearray(result)
    for row in edits:
        at = row["offset"]
        restored[at:at + 12] = data[at:at + 12]
    if restored != data:
        raise ValueError("Candidate changed bytes outside color fields")
    for row in edits:
        observed = [item for item in after["variables"] if item["name_hash"] == row["hash"]]
        if len(observed) != 1 or observed[0]["value"] != row["candidate"]:
            raise ValueError("Authored color did not round-trip")
    return bytes(result), edits


def main():
    if OUT.exists():
        raise ValueError("Research output exists; do not overwrite")
    provenance = json.loads((INPUT / "provenance.json").read_text())
    rows = []
    candidates = []
    for item in provenance["resources"]:
        label = item["name"].rsplit("/", 1)[-1]
        if label not in COLORS:
            continue
        stream = item["installed_streams"][0]
        if stream["sha256"] != EXPECTED[label]:
            raise ValueError("Unexpected pinned source SHA-256")
        original = Path(stream["path"]).read_bytes()
        if len(original) != stream["size"] or hashlib.sha256(original).hexdigest() != stream["sha256"]:
            raise ValueError("Installed source differs from research baseline")
        result, edits = build(original, label)
        filename = label + ".material.candidate"
        candidates.append((filename, result))
        rows.append({"name": item["name"], "source": stream["path"],
                     "source_sha256": stream["sha256"], "output": filename,
                     "output_sha256": hashlib.sha256(result).hexdigest(),
                     "bytes": len(result), "edits": edits})
    if len(rows) != len(COLORS):
        raise ValueError("Not all target materials resolved")
    OUT.mkdir(parents=True)
    for filename, data in candidates:
        (OUT / filename).write_bytes(data)
    manifest = {"build": "24735202", "status": "OFFLINE COLOR TRIAL; no installer or game acceptance",
                "stock_provenance": "Installed resources not owned by known mods; independent Steam hashes pending",
                "material_shader_programs_unchanged": True, "materials": rows}
    (OUT / "report.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
