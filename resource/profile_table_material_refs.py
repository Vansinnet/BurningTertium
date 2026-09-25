"""Match only nearby mission-table unit material references to the hub index."""

import hashlib
import json
from pathlib import Path
import struct

from extract_holo_materials import SOURCE, EXPECTED_BUNDLE_SHA256
from inspect_hologram import murmur64


ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "analysis/stock-table-units-24735202"
report = json.loads((TABLE / "provenance.json").read_text())
with SOURCE.open("rb") as handle:
    if hashlib.file_digest(handle, "sha256").hexdigest() != EXPECTED_BUNDLE_SHA256:
        raise ValueError("Hub bundle changed")
    handle.seek(268)
    index = list(struct.iter_unpack("<QQI", handle.read(4376 * 20)))
materials = {name: i for i, (kind, name, _) in enumerate(index) if kind == murmur64("material")}
result = []
for item in report["resources"]:
    raw = (TABLE / item["record"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != item["record_sha256"]:
        raise ValueError("Table unit differs from extracted evidence")
    matches = []
    for position in range(len(raw) - min(len(raw), 8192), len(raw) - 7):
        name_hash, = struct.unpack_from("<Q", raw, position)
        if name_hash in materials:
            slot = struct.unpack_from("<I", raw, position - 4)[0] if position >= 4 else None
            matches.append({"offset": position, "offset_from_end": len(raw) - position,
                            "hash": f"{name_hash:016x}", "hub_index": materials[name_hash],
                            "preceding_slot_hash32": f"{slot:08x}" if slot is not None else None})
    result.append({"unit": item["name"], "material_refs": matches[:50], "total": len(matches)})
print(json.dumps(result, indent=2))
