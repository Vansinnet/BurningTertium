"""Read only the pinned candle header and cloud prefix; values are not field contracts."""

import hashlib
import json
from pathlib import Path
import struct

base = Path(__file__).resolve().parents[1] / "analysis/stock-hub-candle-24735202"
evidence = json.loads((base / "provenance.json").read_text())
raw = (base / "candle_flame_01.particles.record").read_bytes()
if hashlib.sha256(raw).hexdigest() != evidence["record_sha256"]:
    raise ValueError("Particle input drift")
body = raw[38:]
if struct.unpack_from("<III", body, 32)[1:] != (0, 1):
    raise ValueError("Expected zero-variable, one-cloud candle profile")
rows = []
for label, start, size in (("effect_header", 0, 44), ("cloud_prefix", 44, 80)):
    values = []
    for at in range(start, start + size, 4):
        word, = struct.unpack_from("<I", body, at)
        scalar, = struct.unpack_from("<f", body, at)
        values.append({"offset": at, "hex": f"{word:08x}", "uint": word,
                       "float": scalar if abs(scalar) < 1e9 else None})
    rows.append({"section": label, "words": values})
print(json.dumps(rows, indent=2))
