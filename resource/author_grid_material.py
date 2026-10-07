"""Repack only the two verified grid color programs into an offline material trial."""

import hashlib
import importlib
import json
from pathlib import Path
import struct
import sys

from inspect_hologram import murmur64


ROOT = Path(__file__).resolve().parents[4]
BASE = Path(__file__).resolve().parents[1] / "analysis"
INPUT = BASE / "stock-hub-hologram-24735202"
SHADERS = BASE / "red-grid-shaders-24735202"
OUT = BASE / "red-grid-material-24735202"
EXPECTED_SOURCE = "c49cba30643a8c863c2818df51bbf5f761f7dc0cd32c4912b3d51d037e655db4"
sys.path.insert(0, str(ROOT / "docs/analysis-flame-shader43-20260918-j1"))
codec = importlib.import_module("decode")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def metadata_end(shader, start, device_end):
    if start + 16 > device_end or struct.unpack_from("<I", shader, start)[0] != 5:
        raise ValueError("Unexpected shader program metadata")
    cursor = start + 16
    for width in (6, 0, 0, 7, 7, 7, 7, 4, 3, 3):
        count, = struct.unpack_from("<I", shader, cursor)
        if count > 512 or (width == 0 and count) or cursor + 4 + count * width * 4 > device_end:
            raise ValueError("Unexpected shader metadata table")
        cursor += 4 + count * width * 4
    return cursor


def device_frames(shader, start, length, expected_count=28):
    stop = start + length
    cursor = start
    frames = []
    while (begin := shader.find(b"\x8c\x06", cursor, stop)) != -1:
        cursor = begin + 2
        if begin < start + 8 or begin + 5 > stop:
            continue
        envelope, encoded = struct.unpack_from("<II", shader, begin - 8)
        finish = begin + encoded
        if envelope != 1 or not begin + 8 <= finish <= stop - 16:
            continue
        frame = shader[begin:finish]
        if int.from_bytes(frame[2:5], "big") + 1 != len(frame) - 5:
            continue
        kind, decoded_size, key = struct.unpack_from("<IIQ", shader, finish)
        if kind != 5 or not 32 <= decoded_size <= 262144 or murmur64(frame) != key:
            continue
        end = metadata_end(shader, finish, stop)
        payload = frame[5:] if len(frame) - 5 == decoded_size else codec.decompress(frame, decoded_size)
        codec.dxbc(payload)
        frames.append({"envelope": begin - 8, "begin": begin, "finish": finish,
                       "end": end, "sha256": sha(payload), "decoded_size": decoded_size})
        cursor = end
    if len(frames) != expected_count or len({frame["begin"] for frame in frames}) != expected_count:
        raise ValueError("Unexpected shader frame inventory")
    return frames


def author(source, replacements):
    version, mo, ms, so, ss, tail, ts = struct.unpack_from("<7I", source)
    if version != 61 or mo != 28 or so != mo + ms or tail != so + ss or tail + ts != len(source):
        raise ValueError("Grid material envelope changed")
    shader = source[so:tail]
    head = list(struct.unpack_from("<12I", shader))
    group, group_size, start, device_size = head[8:12]
    old_default = head[5]
    if head[0] != 43 or group != 188 or start != 9440 or not group + group_size <= start or \
       old_default != (start + device_size + 3) & ~3 or len(shader) % 16:
        raise ValueError("Unexpected grid shader layout")
    if any(shader[start + device_size:old_default]):
        raise ValueError("Unknown pre-default padding")
    if shader[old_default:old_default + 8] != bytes(8) or any(shader[old_default + 8:]):
        raise ValueError("Unexpected shader default entries")
    frames = device_frames(shader, start, device_size)
    expected = set(replacements)
    found = set()
    pieces = []
    previous = start
    for frame in frames:
        begin, finish, end = frame["begin"], frame["finish"], frame["end"]
        pieces.append(shader[previous:frame["envelope"]])
        candidate = replacements.get(frame["sha256"])
        if candidate is None:
            pieces.append(shader[frame["envelope"]:end])
        else:
            found.add(frame["sha256"])
            if candidate[:4] != b"DXBC" or not 32 <= len(candidate) <= 262143:
                raise ValueError("Unexpected grid replacement program")
            # The verified stock quantum envelope also supports a stored (uncompressed) frame.
            encoded = b"\x8c\x06" + (len(candidate) - 1).to_bytes(3, "big") + candidate
            metadata = bytearray(shader[finish:end])
            struct.pack_into("<IQ", metadata, 4, len(candidate), murmur64(encoded))
            pieces.extend((struct.pack("<II", 1, len(encoded)), encoded, bytes(metadata)))
        previous = end
    pieces.append(shader[previous:start + device_size])
    if found != expected:
        raise ValueError("Some intended grid shaders are absent")
    device = b"".join(pieces)
    next_default = (start + len(device) + 3) & ~3
    prefix = bytearray(shader[:start])
    struct.pack_into("<I", prefix, 20, next_default)
    struct.pack_into("<I", prefix, 44, len(device))
    new_shader = (bytes(prefix) + device + bytes(next_default - start - len(device)) +
                  shader[old_default:old_default + 8])
    new_shader += bytes((-len(new_shader)) % 16)
    wrapper = bytearray(source[:mo])
    struct.pack_into("<II", wrapper, 16, len(new_shader), so + len(new_shader))
    result = bytes(wrapper) + source[mo:so] + new_shader + source[tail:]
    if not replacements and result != source:
        raise ValueError("Whole-material no-op rebuild did not reproduce source bytes")
    if replacements:
        readback = device_frames(new_shader, start, len(device))
        for digest, payload in replacements.items():
            new_digest = sha(payload)
            if not any(row["sha256"] == new_digest for row in readback):
                raise ValueError("New grid program not found after repack")
        if source[mo:so] != result[mo:so] or source[tail:] != result[so + len(new_shader):]:
            raise ValueError("Non-grid material or tail bytes changed")
    return result, frames


def main():
    if OUT.exists():
        raise ValueError("Output already exists")
    stock = json.loads((INPUT / "provenance.json").read_text())
    grid = next(row for row in stock["resources"] if row["name"].endswith("/hologram_grid"))
    stream = grid["installed_streams"][0]
    source = Path(stream["path"]).read_bytes()
    if stream["sha256"] != EXPECTED_SOURCE or sha(source) != EXPECTED_SOURCE:
        raise ValueError("Grid stock-candidate bytes changed")
    shader_report = json.loads((SHADERS / "report.json").read_text())
    replacements = {}
    for row in shader_report["programs"]:
        candidate = (SHADERS / (row["source"] + ".red.dxbc")).read_bytes()
        if sha(candidate) != row["outputs"]["red"]["sha256"]:
            raise ValueError("Red pixel program drift")
        replacements[row["source_sha256"]] = candidate
    if len(replacements) != 2:
        raise ValueError("Expected two isolated grid shader replacements")
    _, original_frames = author(source, {})
    candidate, new_frames = author(source, replacements)
    if original_frames != new_frames:
        raise ValueError("Original shader frame traversal changed between passes")
    OUT.mkdir(parents=True)
    (OUT / "hologram_grid.material.candidate").write_bytes(candidate)
    report = {"build": "24735202", "status": "OFFLINE MATERIAL; no game acceptance or grid appearance proven",
              "source": stream["path"], "source_sha256": EXPECTED_SOURCE,
              "candidate_sha256": sha(candidate), "candidate_bytes": len(candidate),
              "no_op_identity": True, "pixel_replacements": sorted(replacements),
              "stock_program_count": len(original_frames)}
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
