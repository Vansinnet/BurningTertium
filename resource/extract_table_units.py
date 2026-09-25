"""Retain only the two source-identified mission-table units near the hologram."""

import hashlib
import json
from pathlib import Path
import struct

from inspect_hologram import murmur64
from extract_holo_materials import SOURCE, EXPECTED_BUNDLE_SHA256, check_ownership, read_records


OUT = Path(__file__).resolve().parents[1] / "analysis" / "stock-table-units-24735202"
PREFIX = "content/environment/artsets/imperial/hub/"
NAMES = (PREFIX + "mission_table_01", PREFIX + "mission_table_cogitator")


def main():
    if OUT.exists():
        raise ValueError("Research output already exists")
    check_ownership()
    with SOURCE.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != EXPECTED_BUNDLE_SHA256:
            raise ValueError("Hub bundle changed")
    targets = {(murmur64("unit"), murmur64(name)): name for name in NAMES}
    selected, count = read_records(targets, stop_index=3248, count_required=2)
    OUT.mkdir(parents=True)
    resources = []
    for name, index, raw, pointer in selected:
        filename = name.rsplit("/", 1)[-1] + ".unit.record"
        (OUT / filename).write_bytes(raw)
        payload = raw[38:]
        resources.append({"name": name, "index": index, "record": filename,
                          "record_sha256": hashlib.sha256(raw).hexdigest(),
                          "size": len(raw), "pointer_paths": pointer,
                          "variant_descriptors": list(struct.iter_unpack("<IBIBI", raw[24:38]))})
    report = {"build": "24735202", "hub_bundle_sha256": EXPECTED_BUNDLE_SHA256,
              "decoded_chunks": count, "resources": resources}
    (OUT / "provenance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
