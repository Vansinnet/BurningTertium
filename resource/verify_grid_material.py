"""Independent readback of grid shader replacement and unchanged material dependencies."""

import hashlib
import json
from pathlib import Path
import struct

from inspect_hologram_shaders import shader_programs


BASE = Path(__file__).resolve().parents[1] / "analysis"
OUT = BASE / "red-grid-material-24735202"
report = json.loads((OUT / "report.json").read_text())
original = Path(report["source"]).read_bytes()
trial = (OUT / "hologram_grid.material.candidate").read_bytes()
if hashlib.sha256(original).hexdigest() != report["source_sha256"] or \
   hashlib.sha256(trial).hexdigest() != report["candidate_sha256"]:
    raise ValueError("Material SHA-256 drift")
_, mo, ms, so, ss, tail, ts = struct.unpack_from("<7I", original)
_, m2, n2, s2, shader_size, t2, tail_size = struct.unpack_from("<7I", trial)
if (mo, ms, so, ts) != (m2, n2, s2, tail_size) or t2 != s2 + shader_size:
    raise ValueError("Material layout or external tail changed")
if original[mo:so] != trial[mo:so] or original[tail:tail + ts] != trial[t2:t2 + tail_size]:
    raise ValueError("Grid template or tail changed")
orig_shader = original[so:tail]
next_shader = trial[s2:t2]
a, b = struct.unpack_from("<2I", orig_shader, 32)
c, d = struct.unpack_from("<2I", next_shader, 32)
if (a, b) != (c, d) or orig_shader[a:a + b] != next_shader[c:c + d]:
    raise ValueError("Shader-group binding data changed")
if orig_shader[:20] != next_shader[:20] or orig_shader[24:40] != next_shader[24:40]:
    raise ValueError("Unexpected shader header mutation")
before = shader_programs(original)
after = shader_programs(trial)
if len(before) != 28 or len(after) != 28 or [a[0] for a in before] != [b[0] for b in after]:
    raise ValueError("Pixel/vertex program order changed")
expected = json.loads((BASE / "red-grid-shaders-24735202/report.json").read_text())
replacement_map = {row["source_sha256"]: row["outputs"]["red"]["sha256"]
                   for row in expected["programs"]}
changed = 0
for (stage, old), (_, new) in zip(before, after):
    old_hash = hashlib.sha256(old).hexdigest()
    new_hash = hashlib.sha256(new).hexdigest()
    if old_hash in replacement_map:
        if stage != 0 or new_hash != replacement_map[old_hash]:
            raise ValueError("Red color program missing from grid material")
        changed += 1
    elif new != old:
        raise ValueError("Untargeted grid program changed")
if changed < 2 or changed > 14:
    raise ValueError("Unexpected number of repeated color programs")
print(json.dumps({"source_sha256": report["source_sha256"],
                  "candidate_sha256": report["candidate_sha256"],
                  "programs": len(before), "replaced_color_instances": changed,
                  "untargeted_programs_byte_identical": len(before) - changed,
                  "material_template_and_tail_unchanged": True}, indent=2))
