"""Extract the five identified hologram unit/material registrations from the hub bundle."""

import hashlib
import json
from pathlib import Path
import re
import struct

from extract_hub_level import CHUNK, EXPECTED_BUNDLE_SHA256
from extract_hub_level import SOURCE, check_ownership, decoder, sha
from inspect_hologram import GAME, MAGICS, murmur64


OUT = Path(__file__).resolve().parents[1] / "analysis" / "stock-hub-hologram-24735202"
BASE = "content/environment/artsets/imperial/hub/mission_board_table_hologram/"
NAMES = (BASE + "hologram", BASE + "hologram_side", BASE + "hologram_bottom", BASE + "hologram_grid")
UNIT_NAME = "content/environment/artsets/imperial/hub/mission_table_hologram"
TARGETS = {(murmur64("material"), murmur64(name)): name for name in NAMES}
TARGETS[(murmur64("unit"), murmur64(UNIT_NAME))] = UNIT_NAME


def read_records(targets=TARGETS, stop_index=4088, count_required=5):
    unpack = decoder()
    with SOURCE.open("rb") as source:
        header = source.read(12)
        if header[:8] not in MAGICS:
            raise ValueError("Unknown bundle format")
        count, = struct.unpack_from("<I", header, 8)
        if count != 4376:
            raise ValueError("Unexpected index count")
        source.seek(268)
        index = list(struct.iter_unpack("<QQI", source.read(20 * count)))
        chunks, = struct.unpack("<I", source.read(4))
        if not 0 < chunks <= 1024:
            raise ValueError("Unexpected chunk count")
        sizes = struct.unpack("<" + "I" * chunks, source.read(4 * chunks))
        source.seek((-source.tell()) % 16, 1)
        logical_length, reserved = struct.unpack("<II", source.read(8))
        if reserved or not 0 < logical_length <= chunks * CHUNK:
            raise ValueError("Logical length")
        buffer = bytearray()
        at = 0
        chunk_index = 0

        def read(size):
            nonlocal buffer, at, chunk_index
            if not 0 <= size <= 16 * 1024 * 1024:
                raise ValueError("Resource field exceeds bound")
            while len(buffer) - at < size:
                if chunk_index >= chunks:
                    raise ValueError("Incomplete logical stream")
                stored, = struct.unpack("<I", source.read(4))
                source.seek((-source.tell()) % 16, 1)
                if stored != sizes[chunk_index]:
                    raise ValueError("Chunk length mismatch")
                data = source.read(stored)
                if len(data) != stored:
                    raise ValueError("Short bundle chunk")
                buffer = buffer[at:]
                at = 0
                buffer.extend(unpack(data))
                chunk_index += 1
            result = bytes(buffer[at:at + size])
            at += size
            return result

        selected = []
        for i, (type_hash, name_hash, mode) in enumerate(index):
            head = read(24)
            kind, name, variants, zero = struct.unpack("<QQII", head)
            if (kind, name) != (type_hash, name_hash) or zero or not 1 <= variants <= 64:
                raise ValueError(f"Resource index mismatch at {i}")
            descriptors = read(14 * variants)
            fields = list(struct.iter_unpack("<IBIBI", descriptors))
            if any(first not in (0, 1) or second != 1 for _, first, _, second, _ in fields):
                raise ValueError("Unexpected resource flags")
            payload = b"".join(read(body + tail) for _, _, body, _, tail in fields)
            identity = (kind, name)
            if identity in targets:
                if mode != (4 if identity[0] == murmur64("material") else 0):
                    raise ValueError("Target resource registration mode changed")
                raw = head + descriptors + payload
                pointers = [path.decode() for path in re.findall(rb"data/[0-9a-f]{2}/[0-9a-f]{16}", raw)]
                selected.append((targets[identity], i, raw, pointers))
            if i >= stop_index:
                break
    if len(selected) != count_required:
        raise ValueError("Missing hologram registrations")
    return selected, chunk_index


def main():
    if OUT.exists():
        raise ValueError("Output already exists")
    check_ownership()
    with SOURCE.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != EXPECTED_BUNDLE_SHA256:
            raise ValueError("Bundle differs from pinned level research")
    selected, chunks = read_records()
    outputs = []
    OUT.mkdir(parents=True)
    for name, index, record, pointers in selected:
        filename = name.rsplit("/", 1)[1] + (".unit.record" if name == UNIT_NAME else ".material.record")
        (OUT / filename).write_bytes(record)
        sources = []
        for pointer in pointers:
            path = GAME / "bundle" / pointer
            if path.is_file():
                with path.open("rb") as handle:
                    digest = hashlib.file_digest(handle, "sha256").hexdigest()
                sources.append({"path": str(path), "sha256": digest, "size": path.stat().st_size})
        outputs.append({"name": name, "index": index, "record": filename,
                        "record_sha256": sha(record), "pointer_paths": pointers,
                        "installed_streams": sources})
    manifest = {"build": "24735202", "exe": "1.3.770.210", "bundle": str(SOURCE),
                "bundle_sha256": EXPECTED_BUNDLE_SHA256, "decoded_chunks": chunks,
                "ownership_check": "bundle absent from RainbowFlame and Vortex manifests; stock hash unverified",
                "resources": outputs}
    (OUT / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"decoded_chunks": chunks, "resources": outputs}, indent=2))


if __name__ == "__main__":
    main()
