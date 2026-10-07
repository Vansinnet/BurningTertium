"""Map only the identified hologram unit's material references and record framing."""

import hashlib
import json
from pathlib import Path
import re
import struct

from inspect_hologram import murmur64


OUT = Path(__file__).resolve().parents[1] / "analysis" / "stock-hub-hologram-24735202"
report = json.loads((OUT / "provenance.json").read_text())
unit = next(row for row in report["resources"] if row["record"].endswith(".unit.record"))
raw = (OUT / unit["record"]).read_bytes()
if hashlib.sha256(raw).hexdigest() != unit["record_sha256"]:
    raise ValueError("Hub hologram unit registration differs from pinned extraction")
kind, name, count, reserved = struct.unpack_from("<QQII", raw)
if (kind, name) != (murmur64("unit"), murmur64(unit["name"])) or reserved or not 1 <= count <= 16:
    raise ValueError("Unexpected unit registration")
descriptors = list(struct.iter_unpack("<IBIBI", raw[24:24 + 14 * count]))
targets = {murmur64(item["name"]): item["name"].rsplit("/", 1)[1]
           for item in report["resources"] if item["record"].endswith(".material.record")}
refs = []
for key, label in targets.items():
    token = struct.pack("<Q", key)
    refs.append({"material": label, "name_hash": f"{key:016x}",
                 "offsets": [m.start() for m in re.finditer(re.escape(token), raw)]})
print(json.dumps({"unit": unit["name"], "bytes": len(raw), "variants": descriptors,
                  "identified_material_refs": refs,
                  "mesh_name_hypotheses": [
                      {"name": candidate, "hash64_offsets": [m.start() for m in
                       re.finditer(re.escape(struct.pack("<Q", murmur64(candidate))), raw)][:8],
                       "hash32_offsets": [m.start() for m in re.finditer(re.escape(struct.pack(
                           "<I", murmur64(candidate) >> 32)), raw)][:8]}
                      for candidate in ("g_mission_table_hologram", "hologram", "hologram_grid")],
                  "end_of_record_hex": raw[-128:].hex()}, indent=2))

world_out = OUT.parent / "stock-mourningstar-24735202"
world_report = json.loads((world_out / "provenance.json").read_text())
world_raw = (world_out / "mourningstar.level.record").read_bytes()
if hashlib.sha256(world_raw).hexdigest() != world_report["resource_sha256"]:
    raise ValueError("World record changed")
token = struct.pack("<Q", name)
offsets = [m.start() for m in re.finditer(re.escape(token), world_raw)]
windows = []
for at in offsets[:6]:
    start = max(0, at - 96)
    stop = min(len(world_raw), at + 192)
    a = start + (-start % 4)
    windows.append({"offset": at, "hex": world_raw[start:stop].hex(),
                    "float32_nearby": [(p, round(struct.unpack_from("<f", world_raw, p)[0], 4))
                                       for p in range(a, stop - 3, 4)
                                       if 0.01 < abs(struct.unpack_from("<f", world_raw, p)[0]) < 1000][:50]})
print(json.dumps({"world_unit_reference_hash": f"{name:016x}", "windows": windows}, indent=2))
