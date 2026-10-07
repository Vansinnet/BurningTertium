"""Map only the pinned hub candle flame's cloud names and visualizer materials."""

import hashlib
import json
from pathlib import Path
import struct


OUT = Path(__file__).resolve().parents[1] / "analysis" / "stock-hub-candle-24735202"
report = json.loads((OUT / "provenance.json").read_text())
raw = (OUT / "candle_flame_01.particles.record").read_bytes()
if hashlib.sha256(raw).hexdigest() != report["record_sha256"]:
    raise ValueError("Candle particle changed")
body = raw[38:]
if len(body) != report["descriptor"][2] or struct.unpack_from("<I", body)[0] != 102:
    raise ValueError("Unknown particle version")
variables, count = struct.unpack_from("<II", body, 36)
if variables > 64 or not 1 <= count <= 16:
    raise ValueError("Unexpected candle cloud layout")
cursor = 44 + variables * 16
clouds = []
for index in range(count):
    if cursor + 576 > len(body):
        raise ValueError("Incomplete cloud header")
    words = struct.unpack_from("<144I", body, cursor)
    sections = [words[i] for i in (134, 136, 137, 140, 143)]
    if not (576 <= sections[0] <= sections[1] <= sections[2] <= sections[3] <= sections[4]
            <= len(body) - cursor):
        raise ValueError("Candle cloud sections")
    visualizer = cursor + sections[3]
    visual_type, = struct.unpack_from("<I", body, visualizer)
    material_hash = struct.unpack_from("<Q", body, visualizer + 12)[0] if visual_type == 0 else None
    clouds.append({"index": index, "id32": f"{words[0]:08x}", "visualizer": visual_type,
                   "material_hash": f"{material_hash:016x}" if material_hash is not None else None,
                   "record_size": sections[4], "visualizer_size": sections[4] - sections[3]})
    cursor += sections[4]
if cursor != len(body):
    raise ValueError("Candle particle body not exhausted")
print(json.dumps({"effect": report["effect"], "variables": variables, "clouds": clouds}, indent=2))
