"""Bounded header and device-layout checks for the identified hub grid material."""

import hashlib
import json
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "analysis/stock-hub-hologram-24735202/provenance.json").read_text())
record = next(row for row in manifest["resources"] if row["name"].endswith("/hologram_grid"))
stream = record["installed_streams"][0]
data = Path(stream["path"]).read_bytes()
if hashlib.sha256(data).hexdigest() != stream["sha256"]:
    raise ValueError("Grid stream drift")
header = struct.unpack_from("<7I", data)
version, mo, ms, so, ss, tail, ts = header
shader = data[so:so + ss]
words = struct.unpack_from("<12I", shader)
groups, group_size, device, device_size = words[8:12]
print(json.dumps({"material_header": header, "shader_header": words,
                  "shader_bytes": len(shader), "source_bytes": len(data),
                  "group_count": struct.unpack_from("<I", shader, groups)[0],
                  "group_start": groups, "group_size": group_size,
                  "device_start": device, "device_size": device_size,
                  "defaults_start": words[5], "tail_bytes": data[so + ss:].hex()[:100]}, indent=2))
