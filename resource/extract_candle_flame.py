"""Extract only the hub-indexed stationary candle flame particle registration."""

import hashlib
import json
from pathlib import Path
import struct

from extract_holo_materials import SOURCE, EXPECTED_BUNDLE_SHA256, check_ownership, read_records
from inspect_hologram import murmur64


OUT = Path(__file__).resolve().parents[1] / "analysis" / "stock-hub-candle-24735202"
EFFECT = "content/fx/particles/environment/candle_flame_01"


def main():
    if OUT.exists():
        raise ValueError("Research output already exists")
    check_ownership()
    with SOURCE.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != EXPECTED_BUNDLE_SHA256:
            raise ValueError("Hub bundle identity changed")
    found, chunks = read_records({(murmur64("particles"), murmur64(EFFECT)): EFFECT},
                                 stop_index=1652, count_required=1)
    name, index, raw, _ = found[0]
    if index != 1652 or struct.unpack_from("<I", raw, 16)[0] != 1:
        raise ValueError("Unexpected candle particle record")
    descriptor = struct.unpack_from("<IBIBI", raw, 24)
    OUT.mkdir(parents=True)
    (OUT / "candle_flame_01.particles.record").write_bytes(raw)
    report = {"build": "24735202", "effect": name, "source_bundle": str(SOURCE),
              "source_sha256": EXPECTED_BUNDLE_SHA256, "index": index,
              "decoded_chunks": chunks, "descriptor": descriptor,
              "record_size": len(raw), "record_sha256": hashlib.sha256(raw).hexdigest()}
    (OUT / "provenance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
