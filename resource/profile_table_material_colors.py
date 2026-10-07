"""Profile only material references in the two identified physical table units."""

import hashlib
import importlib
import json
from pathlib import Path
import re
import sys

from extract_holo_materials import GAME, SOURCE, EXPECTED_BUNDLE_SHA256, check_ownership, read_records
from inspect_hologram import murmur64


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1] / "analysis" / "stock-table-materials-24735202"
TABLE = OUT.parent / "stock-table-units-24735202"
sys.path.insert(0, str(ROOT / "docs/analysis-flame-target-20260917-a1"))
parser = importlib.import_module("parse_materials")


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    if OUT.exists():
        raise ValueError("Research output already exists")
    check_ownership()
    if sha(SOURCE) != EXPECTED_BUNDLE_SHA256:
        raise ValueError("Hub bundle differs from target build")
    existing = json.loads((TABLE / "provenance.json").read_text())
    names = json.loads((OUT.parent / "table-material-names-24735202.json").read_text())
    targets = {}
    for entry in names["materials"]:
        key = int(entry["hash"], 16)
        targets[(murmur64("material"), key)] = entry["names"][0] if entry["names"] else entry["hash"]
    if len(targets) != 13:
        raise ValueError("Expected thirteen table material identities")
    selected, chunks = read_records(targets, stop_index=4350, count_required=len(targets))
    managed = json.loads((ROOT / "mods/active/RainbowFlame/payload/manifest.json").read_text())
    managed_paths = {row["target"].lower() for row in managed["files"]}
    vortex = json.loads((GAME / "vortex.deployment.json").read_text())
    deployed_paths = {row["relPath"].replace("\\", "/").lower() for row in vortex["files"]}
    rows = []
    for name, index, raw, _ in selected:
        pointers = [x.decode() for x in re.findall(rb"data/[0-9a-f]{2}/[0-9a-f]{16}", raw)]
        material = {"name": name, "index": index, "registration_sha256": hashlib.sha256(raw).hexdigest(),
                    "streams": []}
        for pointer in pointers:
            relative = "bundle/" + pointer
            if relative.lower() in managed_paths or relative.lower() in deployed_paths:
                raise ValueError("Installed table material managed by another mod: " + name)
            path = GAME / relative
            if not path.is_file() or path.is_symlink():
                material["streams"].append({"pointer": pointer, "present": False})
                continue
            data = path.read_bytes()
            row = {"pointer": pointer, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            try:
                parsed = parser.parse(data)
                row["version"] = parsed["version"]
                row["textures"] = parsed["textures"]
                row["green_biased_variables"] = [v for v in parsed["variables"] if
                                                    v.get("type") in ("vector3", "vector4") and
                                                    v["value"][1] > 0.04 and
                                                    v["value"][1] > 1.25 * max(v["value"][0],
                                                                                 v["value"][2])]
            except ValueError as exc:
                row["unsupported_material_profile"] = str(exc)
            material["streams"].append(row)
        rows.append(material)
    OUT.mkdir(parents=True)
    report = {"build": "24735202", "hub_bundle_sha256": EXPECTED_BUNDLE_SHA256,
              "decoded_chunks": chunks, "status": "offline table-material leads, visual contribution unverified",
              "materials": rows}
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps([{k: m[k] for k in ("name", "index", "streams")} for m in rows], indent=2))


if __name__ == "__main__":
    main()
