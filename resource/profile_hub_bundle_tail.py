"""Read-only bounded chunk capacity check before adding a hub-local particle."""

import hashlib
import json
from pathlib import Path
import struct

from extract_holo_materials import SOURCE, EXPECTED_BUNDLE_SHA256


with SOURCE.open("rb") as handle:
    if hashlib.file_digest(handle, "sha256").hexdigest() != EXPECTED_BUNDLE_SHA256:
        raise ValueError("Hub source changed")
    handle.seek(8)
    count, = struct.unpack("<I", handle.read(4))
    handle.seek(268 + count * 20)
    chunks, = struct.unpack("<I", handle.read(4))
    if (count, chunks) != (4376, 540):
        raise ValueError("Hub chunk/index count changed")
    sizes = struct.unpack("<" + "I" * chunks, handle.read(4 * chunks))
    handle.seek((-handle.tell()) % 16, 1)
    logical, reserved = struct.unpack("<II", handle.read(8))
    if reserved or not 0 < logical <= chunks * 0x80000:
        raise ValueError("Hub logical size")
print(json.dumps({"source_sha256": EXPECTED_BUNDLE_SHA256,
                  "resources": count, "chunks": chunks, "logical_bytes": logical,
                  "final_chunk_used": logical - (chunks - 1) * 0x80000,
                  "final_chunk_free": chunks * 0x80000 - logical,
                  "final_compressed_bytes": sizes[-1]}, indent=2))
