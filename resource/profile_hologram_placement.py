"""Locate the identified hologram unit's nearby placement triple in its level record."""

import hashlib
import json
from pathlib import Path
import re
import struct

from inspect_hologram import murmur64


OUT = Path(__file__).resolve().parents[1] / "analysis" / "stock-mourningstar-24735202"
report = json.loads((OUT / "provenance.json").read_text())
raw = (OUT / "mourningstar.level.record").read_bytes()
if hashlib.sha256(raw).hexdigest() != report["resource_sha256"]:
    raise ValueError("Level record differs from pinned input")
unit = "content/environment/artsets/imperial/hub/mission_table_hologram"
at = [m.start() for m in re.finditer(re.escape(struct.pack("<Q", murmur64(unit))), raw)]
if len(at) != 1:
    raise ValueError("Unexpected hub hologram placement count")
matches = []
for position in range(at[0] - 24, at[0] + 80):
    x, y, z = struct.unpack_from("<3f", raw, position)
    if abs(x) < 0.2 and -165 < y < -146 and 100 < z < 108:
        matches.append({"offset": position, "relative_to_unit_hash": position - at[0],
                        "xyz": [x, y, z], "raw": raw[position:position + 12].hex()})
print(json.dumps({"unit_name": unit, "world_resource_ref_offset": at[0],
                  "plausible_placement_triples": matches}, indent=2))
