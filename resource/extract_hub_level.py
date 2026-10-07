"""Extract only the identified hub level record from its installed bundle."""

import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import re
import struct

from inspect_hologram import GAME, MAGICS, murmur64


ROOT = Path(__file__).resolve().parents[4]
NAME = "content/levels/hub/hub_ship/mourningstar/world"
SOURCE = GAME / "bundle" / f"{murmur64('content/levels/hub/hub_ship/missions/hub_ship'):016x}"
EXPECTED_BUNDLE_SHA256 = "f9ff268a1af54914215aacb88f36643a01cd96840ac1cf769f4e4a3cd3c3ced2"
OODLE_SHA256 = "8595a4795f1e0c7f548598f3e2aa528b6be5456c6d934c665182eaecb04156c0"
CHUNK = 0x80000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def decoder():
    path = GAME / "binaries/oo2core_9_win64.dll"
    if sha(path.read_bytes()) != OODLE_SHA256:
        raise ValueError("Oodle decoder is not the pinned game version")
    dll = ctypes.CDLL(str(path))
    memory = dll.OodleLZDecoder_MemorySizeNeeded
    memory.argtypes, memory.restype = [ctypes.c_int32, ctypes.c_int64], ctypes.c_uint64
    size = memory(-1, -1)
    if not 0 < size <= 16 * 1024 * 1024:
        raise ValueError("Decoder scratch size")
    scratch = ctypes.create_string_buffer(size)
    decompress = dll.OodleLZ_Decompress
    decompress.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_uint64,
                           ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                           ctypes.c_uint64, ctypes.c_void_p, ctypes.c_void_p,
                           ctypes.c_void_p, ctypes.c_uint64, ctypes.c_int]
    decompress.restype = ctypes.c_uint64

    def unpack(block):
        if len(block) == CHUNK:
            return block
        source = ctypes.create_string_buffer(block)
        output = ctypes.create_string_buffer(CHUNK)
        actual = decompress(source, len(block), output, CHUNK, 1, 0, 3,
                            None, 0, None, None, scratch, size, 3)
        if actual != CHUNK:
            raise ValueError("Unexpected decoded chunk length")
        return output.raw

    return unpack


def check_ownership():
    relative = "bundle/" + SOURCE.name
    manifest = json.loads((ROOT / "mods/active/RainbowFlame/payload/manifest.json").read_text())
    vortex = json.loads((GAME / "vortex.deployment.json").read_text())
    if relative.lower() in {row["target"].lower() for row in manifest["files"]}:
        raise ValueError("RainbowFlame owns the bundle")
    if relative.lower() in {row["relPath"].replace("\\", "/").lower()
                            for row in vortex["files"]}:
        raise ValueError("Vortex manages the bundle")


def record(data, wanted, name_target):
    cursor = 0
    for identity in wanted:
        start = cursor
        if cursor + 24 > len(data):
            raise ValueError("Incomplete record")
        kind, name, count, reserved = struct.unpack_from("<QQII", data, cursor)
        if (kind, name) != identity[:2] or reserved or not 1 <= count <= 64:
            raise ValueError("Index/record mismatch")
        cursor += 24
        for _ in range(count):
            if cursor + 14 > len(data):
                raise ValueError("Incomplete record")
            _, first, length, second, tail = struct.unpack_from("<IBIBI", data, cursor)
            if first not in (0, 1) or second != 1:
                raise ValueError("Unexpected variant flags")
            cursor += 14 + length + tail
            if cursor > len(data):
                raise ValueError("Incomplete record")
        if name == murmur64(name_target) and kind == murmur64("level"):
            return data[start:cursor], cursor
    raise ValueError("Level identity absent")


def main(which):
    if which == "root":
        name = "content/levels/hub/hub_ship/missions/hub_ship"
        index_target = 35
        out = Path(__file__).resolve().parents[1] / "analysis" / "stock-hub-24735202"
        filename = "hub_ship.level.record"
    else:
        name = NAME
        index_target = 30
        out = Path(__file__).resolve().parents[1] / "analysis" / "stock-mourningstar-24735202"
        filename = "mourningstar.level.record"
    if out.exists():
        raise ValueError("Research output already exists")
    check_ownership()
    if sha(SOURCE.read_bytes()) != EXPECTED_BUNDLE_SHA256:
        raise ValueError("Installed hub bundle changed since index inspection")
    unpack = decoder()
    with SOURCE.open("rb") as handle:
        header = handle.read(12)
        if header[:8] not in MAGICS:
            raise ValueError("Unexpected bundle version")
        count, = struct.unpack_from("<I", header, 8)
        if count != 4376:
            raise ValueError("Unexpected resource count")
        handle.seek(268)
        index = list(struct.iter_unpack("<QQI", handle.read(count * 20)))
        if len(index) != count or index[index_target][:2] != (murmur64("level"), murmur64(name)):
            raise ValueError("Hub level identity moved")
        chunks, = struct.unpack("<I", handle.read(4))
        if not 0 < chunks <= 1024:
            raise ValueError("Chunk count")
        sizes = struct.unpack("<" + "I" * chunks, handle.read(4 * chunks))
        if any(not 0 < n <= CHUNK for n in sizes):
            raise ValueError("Chunk sizes")
        handle.seek((-handle.tell()) % 16, 1)
        length, reserved = struct.unpack("<II", handle.read(8))
        if reserved or not 0 < length <= chunks * CHUNK:
            raise ValueError("Logical length")
        prefix = bytearray()
        extracted = None
        end = 0
        used = 0
        for size in sizes:
            actual, = struct.unpack("<I", handle.read(4))
            handle.seek((-handle.tell()) % 16, 1)
            if actual != size:
                raise ValueError("Inline size mismatch")
            block = handle.read(size)
            if len(block) != size:
                raise ValueError("Short chunk")
            prefix.extend(unpack(block))
            used += 1
            if len(prefix) > 64 * 1024 * 1024:
                raise ValueError("Hub level exceeds bounded extraction")
            try:
                extracted, end = record(prefix, index[:index_target + 1], name)
            except ValueError as error:
                if str(error) != "Incomplete record":
                    raise
            if extracted is not None:
                break
        if extracted is None:
            raise ValueError("Level record not present in bounded prefix")
    hits = []
    for term in (b"hologram", b"mission_table", b"mission_board"):
        offsets = [match.start() for match in re.finditer(term, extracted, re.IGNORECASE)]
        hits.append({"term": term.decode(), "count": len(offsets),
                     "samples": [extracted[max(0, p - 55):p + 110].decode("ascii", "backslashreplace")
                                 for p in offsets[:8]]})
    out.mkdir(parents=True)
    (out / filename).write_bytes(extracted)
    report = {"build": "24735202", "exe": "1.3.770.210", "bundle": str(SOURCE),
              "bundle_sha256": EXPECTED_BUNDLE_SHA256,
              "ownership_check": "not listed by RainbowFlame or Vortex; independent Steam stock hash unavailable",
              "extraction": "read-only first records; bundle not modified",
              "resource_index": index_target, "chunk_prefix_count": used,
              "resource_bytes": len(extracted), "resource_sha256": sha(extracted),
              "record_end": end, "hits": hits}
    (out / "provenance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("chunk_prefix_count", "resource_bytes", "resource_sha256", "hits")}, indent=2))


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--level", choices=("root", "world"), default="world")
    main(cli.parse_args().level)
