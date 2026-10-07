"""Independently verify offline material trial changes only named red color fields."""

import hashlib
import importlib
import json
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[4]
TRIAL = Path(__file__).resolve().parents[1] / "analysis" / "red-material-trial-24735202"
sys.path.insert(0, str(ROOT / "docs/analysis-flame-target-20260917-a1"))
parse = importlib.import_module("parse_materials").parse


def sha(data):
    return hashlib.sha256(data).hexdigest()


report = json.loads((TRIAL / "report.json").read_text())
if report["build"] != "24735202" or len(report["materials"]) != 3:
    raise ValueError("Unexpected trial inventory")
result = []
for item in report["materials"]:
    baseline = Path(item["source"]).read_bytes()
    candidate = (TRIAL / item["output"]).read_bytes()
    if sha(baseline) != item["source_sha256"] or sha(candidate) != item["output_sha256"]:
        raise ValueError("Unpinned red trial")
    if len(baseline) != item["bytes"] or len(candidate) != len(baseline):
        raise ValueError("Material size changed")
    original = parse(baseline)
    changed = parse(candidate)
    if (original["material_offset"], original["material_size"], original["shader_offset"],
        original["shader_size"], original["textures"], original["parent_hashes"]) != \
       (changed["material_offset"], changed["material_size"], changed["shader_offset"],
        changed["shader_size"], changed["textures"], changed["parent_hashes"]):
        raise ValueError("Unexpected material metadata change")
    permitted = set()
    for edit in item["edits"]:
        offset = edit["offset"]
        if not original["material_offset"] <= offset < offset + 12 <= original["shader_offset"]:
            raise ValueError("Color edit outside material template")
        if struct.unpack_from("<3f", baseline, offset) != tuple(edit["original"]):
            raise ValueError("Source color differs from report")
        if struct.unpack_from("<3f", candidate, offset) != tuple(edit["candidate"]):
            raise ValueError("Candidate color differs from report")
        permitted.update(range(offset, offset + 12))
    differences = {i for i, (a, b) in enumerate(zip(baseline, candidate)) if a != b}
    if not differences or not differences <= permitted or any(
            baseline[i] != candidate[i] for i in range(original["shader_offset"], len(baseline))):
        raise ValueError("Red trial touched non-color or shader bytes")
    result.append({"material": item["name"], "changed_bytes": len(differences),
                   "changed_fields": len(item["edits"]), "shader_unchanged": True})
print(json.dumps(result, indent=2))
