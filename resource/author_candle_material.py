"""Build a separate red-scanlined candle material stream, retaining stock unchanged."""

import hashlib
import json
from pathlib import Path
import struct

from author_grid_material import device_frames
from inspect_hologram import murmur64


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/red-candle-material-24735202"
SOURCE = ROOT / "analysis/stock-hub-candle-material-24735202/provenance.json"
SHADER = ROOT / "analysis/red-candle-shader-24735202/report.json"
STOCK_SHA = "90ff8d9836fcad0ecddc9785122a399ddb7a8dec1e7b63dc88a940459ec4f998"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def author(source, original_hash, replacement=None):
    version, mo, ms, so, ss, tail, ts = struct.unpack_from("<7I", source)
    if (version, mo, ms, so, ss, tail, ts) != (61, 28, 316, 344, 40736, 41080, 4):
        raise ValueError("Unsupported candle material envelope")
    shader = source[so:so + ss]
    head = struct.unpack_from("<12I", shader)
    start, size, device, device_size = head[8:12]
    default = head[5]
    if head[0] != 43 or (start, size, device, device_size, default) != (100, 3330, 3432, 37200, 40632):
        raise ValueError("Candle shader layout changed")
    if any(shader[device + device_size:default]) or shader[default:default + 4] != bytes(4):
        raise ValueError("Unexpected shader default alignment/header")
    count, = struct.unpack_from("<I", shader, default + 4)
    if count != 6:
        raise ValueError("Candle scalar default count")
    cursor = 8 + 12 * count
    for i in range(count):
        _, width, offset = struct.unpack_from("<III", shader, default + 8 + 12 * i)
        if width != 1 or offset != cursor:
            raise ValueError("Candle default field layout")
        cursor += 4
    if any(shader[default + cursor:]) or len(shader) != (default + cursor + 15) & ~15:
        raise ValueError("Unknown candle default padding")
    frames = device_frames(shader, device, device_size, expected_count=4)
    if sum(frame["sha256"] == original_hash for frame in frames) != 1:
        raise ValueError("Candle color program not uniquely present")
    pieces = []
    last = device
    for frame in frames:
        begin, finish, end = frame["begin"], frame["finish"], frame["end"]
        pieces.append(shader[last:frame["envelope"]])
        if frame["sha256"] == original_hash and replacement is not None:
            if replacement[:4] != b"DXBC" or not 32 <= len(replacement) <= 262143:
                raise ValueError("Unexpected authored pixel program")
            wrapped = b"\x8c\x06" + (len(replacement) - 1).to_bytes(3, "big") + replacement
            metadata = bytearray(shader[finish:end])
            struct.pack_into("<IQ", metadata, 4, len(replacement), murmur64(wrapped))
            pieces.extend((struct.pack("<II", 1, len(wrapped)), wrapped, bytes(metadata)))
        else:
            pieces.append(shader[frame["envelope"]:end])
        last = end
    pieces.append(shader[last:device + device_size])
    result_device = b"".join(pieces)
    next_default = (device + len(result_device) + 3) & ~3
    prefix = bytearray(shader[:device])
    struct.pack_into("<I", prefix, 20, next_default)
    struct.pack_into("<I", prefix, 44, len(result_device))
    new_shader = (bytes(prefix) + result_device + bytes(next_default - device - len(result_device))
                  + shader[default:default + cursor])
    new_shader += bytes((-len(new_shader)) % 16)
    wrapper = bytearray(source[:mo])
    struct.pack_into("<II", wrapper, 16, len(new_shader), so + len(new_shader))
    result = bytes(wrapper) + source[mo:so] + new_shader + source[tail:]
    if replacement is None and result != source:
        raise ValueError("Candle no-op rebuild changed source bytes")
    if replacement is not None:
        after = device_frames(new_shader, device, len(result_device), expected_count=4)
        if [f["sha256"] for f in after] != [sha(replacement) if f["sha256"] == original_hash else
                                               f["sha256"] for f in frames]:
            raise ValueError("Candle shader readback changed unintended programs")
        if source[mo:so] != result[mo:so] or source[tail:] != result[so + len(new_shader):]:
            raise ValueError("Candle template or trailing bytes changed")
    return result


def main():
    if OUT.exists():
        raise ValueError("Material output already exists")
    source_info = json.loads(SOURCE.read_text())
    if source_info["stream_sha256"] != STOCK_SHA:
        raise ValueError("Unpinned stock candle material")
    stock = Path(source_info["stream"]).read_bytes()
    if sha(stock) != STOCK_SHA:
        raise ValueError("Installed candle material changed")
    authored = json.loads(SHADER.read_text())
    pixel = authored["outputs"]["red_holographic"]
    shader_file = SHADER.parent / pixel["file"]
    candidate_shader = shader_file.read_bytes()
    if sha(candidate_shader) != pixel["sha256"]:
        raise ValueError("Signed red flame program drift")
    author(stock, authored["stock_shader_sha256"])
    result = author(stock, authored["stock_shader_sha256"], candidate_shader)
    OUT.mkdir(parents=True)
    (OUT / "candle_flame_red.material.candidate").write_bytes(result)
    record = {"build": "24735202", "status": "offline candle material candidate, engine acceptance untested",
              "source_sha256": STOCK_SHA, "material_sha256": sha(result), "bytes": len(result),
              "red_pixel_sha256": pixel["sha256"], "other_programs_unchanged": True,
              "noop_byte_identical": True, "input_registration_hash": source_info["hash"]}
    (OUT / "report.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
