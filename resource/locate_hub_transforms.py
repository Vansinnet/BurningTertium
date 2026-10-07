"""Test if known mission-board interactable positions are encoded in the pinned world record."""

import hashlib
import argparse
import json
from pathlib import Path
import struct


cli = argparse.ArgumentParser(description=__doc__)
cli.add_argument("--level", choices=("root", "world"), default="world")
which = cli.parse_args().level
OUT = Path(__file__).resolve().parents[1] / "analysis" / (
    "stock-hub-24735202" if which == "root" else "stock-mourningstar-24735202")
report = json.loads((OUT / "provenance.json").read_text())
data = (OUT / ("hub_ship.level.record" if which == "root" else "mourningstar.level.record")).read_bytes()
if hashlib.sha256(data).hexdigest() != report["resource_sha256"]:
    raise ValueError("World record differs from evidence")

# Positions are the read-only ComponentSystem results for six mission-board interactables.
observed = ((6.64877, -159.33347, 101.75676), (6.65, -151.7, 101.8),
            (0, -163.2, 101.8), (-6.6, -159.3, 101.8),
            (-6.7, -151.7, 101.8), (0, -147.8, 101.8))
floats = [value[0] for value in struct.iter_unpack("<f", data[:len(data) // 4 * 4])]


def nearby(index, target, tolerance):
    return abs(floats[index] - target) <= tolerance


rows = []
for x, y, z in observed:
    # Check local windows before making any claim about a level transform layout.
    y_offsets = [i * 4 for i in range(len(floats)) if nearby(i, y, 0.035)]
    hits = []
    for at in y_offsets:
        window = [(p * 4, floats[p]) for p in range(max(0, at // 4 - 16),
                  min(len(floats), at // 4 + 17))]
        xs = [pos for pos, value in window if abs(value - x) < 0.08]
        zs = [pos for pos, value in window if abs(value - z) < 0.08]
        if xs and zs:
            hits.append({"y_offset": at, "x_offsets": xs[:5], "z_offsets": zs[:5],
                         "window": [(pos, round(value, 3)) for pos, value in window
                                    if abs(value) < 5000][:35]})
    rows.append({"observed_xyz": (x, y, z), "y_matches": len(y_offsets),
                 "candidate_windows": hits[:6], "candidate_count": len(hits)})
print(json.dumps({"record_size": len(data), "results": rows}, indent=2))
