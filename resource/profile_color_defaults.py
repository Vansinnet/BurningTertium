"""Read only the pinned hub materials' template and shader43 default colors."""

import hashlib
import json
from pathlib import Path
import struct


OUT = Path(__file__).resolve().parents[1] / "analysis" / "stock-hub-hologram-24735202"
manifest = json.loads((OUT / "provenance.json").read_text())


def defaults(shader):
    if struct.unpack_from("<I", shader)[0] != 43:
        raise ValueError("Unexpected shader version")
    offset, = struct.unpack_from("<I", shader, 20)
    if not 0 < offset < len(shader) or struct.unpack_from("<I", shader, offset)[0] != 0:
        raise ValueError("Shader defaults header")
    count, = struct.unpack_from("<I", shader, offset + 4)
    if count > 512:
        raise ValueError("Shader default count")
    rows = []
    for i in range(count):
        key, width, at = struct.unpack_from("<III", shader, offset + 8 + 12 * i)
        if not 1 <= width <= 4 or at < 8 + 12 * count or offset + at + width * 4 > len(shader):
            raise ValueError("Shader default extent")
        values = struct.unpack_from("<" + "f" * width, shader, offset + at)
        rows.append({"hash": f"{key:08x}", "width": width,
                     "offset": offset + at, "value": values})
    return rows


results = []
for record in manifest["resources"]:
    if not record["record"].endswith(".material.record"):
        continue
    stream = record["installed_streams"][0]
    data = Path(stream["path"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != stream["sha256"] or len(data) != stream["size"]:
        raise ValueError("Pinned material source changed")
    version, mo, ms, so, ss, tail, ts = struct.unpack_from("<7I", data)
    if version != 61 or mo != 28 or so != mo + ms or so + ss > len(data):
        raise ValueError("Material envelope changed")
    rows = defaults(data[so:so + ss])
    results.append({"name": record["name"], "default_count": len(rows),
                    "color_relevant_defaults": [row for row in rows if row["hash"] in
                                                ("cb577b8f", "8216e41d", "32f447e5")],
                    "all_default_hashes": [row["hash"] for row in rows]})
print(json.dumps(results, indent=2))
