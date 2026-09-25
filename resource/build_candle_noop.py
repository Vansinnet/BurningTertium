"""Physical no-op control with only the final hub chunk re-encoded as stored bytes."""

import hashlib
import json
from pathlib import Path

from build_candle_variant import GAME_SOURCE, SOURCE_SHA, read_bundle, serialize
from extract_hub_level import decoder


OUT = Path(__file__).resolve().parents[1] / "analysis/candle-noop-bundle-24735202"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if OUT.exists():
        raise ValueError("Physical no-op output exists")
    source = GAME_SOURCE.read_bytes()
    if sha(source) != SOURCE_SHA:
        raise ValueError("Stock hub bundle changed")
    decoded = read_bundle(source)
    last = decoder()(decoded["blocks"][-1])
    if len(last) != 0x80000 or decoded["blocks"][-1] == last:
        raise ValueError("Expected stock compressed final chunk")
    candidate = serialize(decoded, decoded["index"], decoded["logical"], decoded["blocks"][:-1] + [last])
    if candidate == source or sha(candidate) == SOURCE_SHA:
        raise ValueError("No-op physical encoding did not change")
    roundtrip = read_bundle(candidate)
    if roundtrip["logical"] != decoded["logical"] or roundtrip["index"] != decoded["index"] or \
       roundtrip["blocks"][:-1] != decoded["blocks"][:-1]:
        raise ValueError("Physical no-op changed resource stream or prior chunks")
    OUT.mkdir(parents=True)
    filename = "8aaa27ad87976cf4.noop.bundle"
    (OUT / filename).write_bytes(candidate)
    report = {"build": "24735202", "source_sha256": SOURCE_SHA,
              "candidate_sha256": sha(candidate), "candidate_bytes": len(candidate),
              "filename": filename, "resource_count": 4376, "unchanged_prior_compressed_chunks": 539,
              "logical_data_byte_identical": True, "status": "OFFLINE PHYSICAL NO-OP; in-game acceptance untested"}
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
