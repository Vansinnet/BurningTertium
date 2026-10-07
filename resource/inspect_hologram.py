"""Read-only, exact-name stock bundle index lookup for the Mourningstar hologram."""

import hashlib
import json
from pathlib import Path
import struct


GAME = Path(r"D:\Steam\steamapps\common\Warhammer 40,000 DARKTIDE")
NAMES = (
    "content/levels/hub/hub_ship/missions/hub_ship",
    "content/levels/hub/hub_ship/mourningstar/world",
    "content/levels/ui/mission_board_player_journey/mission_board_player_journey",
    "content/environment/artsets/imperial/hub/mission_table_hologram",
    "content/environment/artsets/imperial/hub/mission_board_table_hologram/hologram",
    "content/environment/artsets/imperial/hub/mission_board_table_hologram/hologram_side",
    "content/environment/artsets/imperial/hub/mission_board_table_hologram/hologram_01",
    "content/environment/artsets/imperial/hub/mission_board_table_hologram/hologram_02",
    "content/environment/artsets/imperial/hub/mission_board_table_hologram/hologram_bottom",
    "content/environment/artsets/imperial/hub/mission_board_table_hologram/hologram_grid",
)
TYPES = ("level", "unit", "material", "lua")
MAGICS = {bytes.fromhex("080000f003000000"), bytes.fromhex("070000f003000000")}


def murmur64(text):
    data = text if isinstance(text, bytes) else text.encode()
    multiplier = 0xC6A4A7935BD1E995
    mask = (1 << 64) - 1
    value = len(data) * multiplier & mask
    end = len(data) // 8 * 8
    for (word,) in struct.iter_unpack("<Q", data[:end]):
        word = word * multiplier & mask
        word ^= word >> 47
        value = (value ^ (word * multiplier & mask)) * multiplier & mask
    if data[end:]:
        value = (value ^ int.from_bytes(data[end:], "little")) * multiplier & mask
    value ^= value >> 47
    value = value * multiplier & mask
    return value ^ (value >> 47)


def inspect(name):
    source = GAME / "bundle" / f"{murmur64(name):016x}"
    if not source.is_file():
        return {"name": name, "bundle": str(source), "present": False}
    with source.open("rb") as handle:
        header = handle.read(12)
        if len(header) != 12 or header[:8] not in MAGICS:
            raise ValueError(f"Unknown bundle profile: {source}")
        count, = struct.unpack_from("<I", header, 8)
        if not 0 < count <= 100_000:
            raise ValueError(f"Unexpected index size: {source}")
        handle.seek(268)
        index = handle.read(20 * count)
        if len(index) != 20 * count:
            raise ValueError(f"Truncated index: {source}")
        chunks_raw = handle.read(4)
        chunks, = struct.unpack("<I", chunks_raw)
        if not 0 < chunks <= 4096:
            raise ValueError(f"Unexpected chunk count: {source}")
        handle.seek(0)
        sha256 = hashlib.file_digest(handle, "sha256").hexdigest()
    name_hash = murmur64(name)
    targets = {murmur64(target): target for target in NAMES}
    kind_hashes = {murmur64(kind): kind for kind in TYPES}
    found = [
        {"index": i, "name": targets.get(resource),
         "type": kind_hashes.get(kind, f"{kind:016x}"), "mode": mode}
        for i, (kind, resource, mode) in enumerate(struct.iter_unpack("<QQI", index))
        if resource in targets
    ]
    return {"name": name, "name_hash": f"{name_hash:016x}",
            "bundle": str(source), "size": source.stat().st_size,
            "sha256": sha256, "resources": count, "chunks": chunks, "matches": found}


if __name__ == "__main__":
    assert murmur64("lua") == 0xA14E8DFA2CD117E2
    assert murmur64("material") == 0xEAC0B497876ADEDF
    print(json.dumps([inspect(name) for name in NAMES], indent=2))
