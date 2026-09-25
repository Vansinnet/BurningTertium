"""Read-only envelope and shader43 offsets of the identified candle material."""

import hashlib
import json
from pathlib import Path
import struct


INPUT = Path(__file__).resolve().parents[1] / "analysis/stock-hub-candle-material-24735202/provenance.json"
record = json.loads(INPUT.read_text())
source = Path(record["stream"]).read_bytes()
if hashlib.sha256(source).hexdigest() != record["stream_sha256"]:
    raise ValueError("Candle stock material changed")
material = struct.unpack_from("<7I", source)
_, mo, ms, so, ss, tail, ts = material
shader = source[so:so + ss]
header = struct.unpack_from("<12I", shader)
group, size, device, device_size = header[8:12]
print(json.dumps({"material_header": material, "source_bytes": len(source),
                  "shader_header": header, "groups": struct.unpack_from("<I", shader, group)[0],
                  "groups_size": size, "device_start": device, "device_size": device_size,
                  "defaults_start": header[5], "shader_bytes": len(shader),
                  "tail_preview": source[so + ss:so + ss + 40].hex()}, indent=2))
