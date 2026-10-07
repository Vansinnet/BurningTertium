"""Offline sixfold billboard-geometry trial for the isolated red candle material."""

import hashlib
import json
from pathlib import Path
import struct

from author_grid_shader import BoundedDxc, dump, parts, typed_module
from author_grid_material import device_frames
from inspect_hologram import murmur64
from inspect_hologram_shaders import shader_programs

BASE = Path(__file__).resolve().parents[1] / "analysis"
VERTICES = BASE / "candle-vertex-24735202"
SOURCE = BASE / "red-candle-material-24735202/candle_flame_red.material.candidate"
SOURCE_SHA = "8069dc045f4ecc46b0355c0e03cf314103dabdcde09f0a442b8c9cc8926f335f"
OUT = BASE / "large-red-flame-24735202"
TARGETS = {
    "7dea7622bcc3c550db95db3599fa9a3469807dc0cc3a9d9e032962bf7ecc347b":
        ((62, 20, 9), (63, 21, 10)),
    "b2e1514a28f17a0b361a396ed80a05b8770b5ac126105d6e83c36c28f31dc6fd":
        ((57, 15, 4), (58, 16, 5)),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def enlarge(module, anchors):
    altered = module
    for axis, (target, corner, size) in zip(("width", "height"), anchors):
        original = f"  %{target} = fmul fast float %{corner}, %{size}"
        if altered.count(original + "\n") != 1:
            raise ValueError("Billboard geometry anchor changed")
        replacement = (f"  %bt.{axis} = fmul float %{size}, 6.000000e+00\n"
                       f"  %{target} = fmul fast float %{corner}, %bt.{axis}")
        altered = altered.replace(original + "\n", replacement + "\n")
    return altered


def repack(source, replacements):
    version, mo, ms, so, ss, tail, ts = struct.unpack_from("<7I", source)
    if (version, mo, ms, so, ts) != (61, 28, 316, 344, 4) or tail != so + ss:
        raise ValueError("Unexpected red material envelope")
    shader = source[so:tail]
    header = struct.unpack_from("<12I", shader)
    start, size = header[10:12]
    defaults = header[5]
    if header[0] != 43 or start != 3432 or defaults != (start + size + 3) & ~3:
        raise ValueError("Unexpected candle shader device layout")
    default_count, = struct.unpack_from("<I", shader, defaults + 4)
    if shader[defaults:defaults + 4] != bytes(4) or default_count != 6:
        raise ValueError("Unexpected shader defaults")
    default_length = 8 + 12 * default_count
    for i in range(default_count):
        _, width, offset = struct.unpack_from("<III", shader, defaults + 8 + 12 * i)
        if width != 1 or offset != default_length:
            raise ValueError("Unexpected default field")
        default_length += 4
    if any(shader[defaults + default_length:]) or any(shader[start + size:defaults]):
        raise ValueError("Unknown padding")
    frames = device_frames(shader, start, size, expected_count=4)
    pieces = []
    previous = start
    seen = set()
    for frame in frames:
        pieces.append(shader[previous:frame["envelope"]])
        payload = replacements.get(frame["sha256"])
        if payload is None:
            pieces.append(shader[frame["envelope"]:frame["end"]])
        else:
            seen.add(frame["sha256"])
            encoded = b"\x8c\x06" + (len(payload) - 1).to_bytes(3, "big") + payload
            metadata = bytearray(shader[frame["finish"]:frame["end"]])
            struct.pack_into("<IQ", metadata, 4, len(payload), murmur64(encoded))
            pieces.extend((struct.pack("<II", 1, len(encoded)), encoded, metadata))
        previous = frame["end"]
    pieces.append(shader[previous:start + size])
    if seen != set(replacements):
        raise ValueError("Vertex replacement not present")
    device = b"".join(pieces)
    next_default = (start + len(device) + 3) & ~3
    prefix = bytearray(shader[:start])
    struct.pack_into("<I", prefix, 20, next_default)
    struct.pack_into("<I", prefix, 44, len(device))
    result_shader = (bytes(prefix) + device + bytes(next_default - start - len(device)) +
                     shader[defaults:defaults + default_length])
    result_shader += bytes((-len(result_shader)) % 16)
    wrapper = bytearray(source[:mo])
    struct.pack_into("<II", wrapper, 16, len(result_shader), so + len(result_shader))
    result = bytes(wrapper) + source[mo:so] + result_shader + source[tail:]
    if not replacements and result != source:
        raise ValueError("No-op material roundtrip failed")
    return result


def main():
    if OUT.exists():
        raise ValueError("Research output exists")
    source = SOURCE.read_bytes()
    if sha(source) != SOURCE_SHA:
        raise ValueError("Red material drift")
    before = shader_programs(source)
    if {sha(data) for stage, data in before if stage == 1} != set(TARGETS):
        raise ValueError("Vertex identity mismatch")
    if repack(source, {}) != source:
        raise ValueError("No-op mismatch")
    compiler = BoundedDxc()
    OUT.mkdir()
    replacements = {}
    records = []
    for digest, anchors in TARGETS.items():
        path = VERTICES / (digest[:12] + ".dxbc")
        binary = path.read_bytes()
        if sha(binary) != digest:
            raise ValueError("Pinned vertex input changed")
        original_parts = parts(binary)
        stat = OUT / (digest[:12] + ".stat")
        stat.write_bytes(original_parts["STAT"])
        module = typed_module(dump(path), dump(stat), "vs_main")
        for label, candidate in (("noop", module), ("large", enlarge(module, anchors))):
            assembled, warning = compiler.operation(candidate.encode(), assemble=True)
            if warning:
                raise ValueError(warning)
            signed, warning = compiler.operation(assembled, assemble=False)
            if warning or signed[4:20] == bytes(16):
                raise ValueError("Unsigned or invalid vertex result")
            new_parts = parts(signed)
            if any(new_parts[tag] != original_parts[tag] for tag in ("SFI0", "ISG1", "OSG1", "PSV0")):
                raise ValueError("Vertex interface changed")
            output = OUT / (digest[:12] + "." + label + ".dxbc")
            output.write_bytes(signed)
            if label == "large":
                text = dump(output)
                if "%bt.width" not in text or "%bt.height" not in text:
                    raise ValueError("Geometry transform missing from signed vertex")
                replacements[digest] = signed
                records.append({"source_sha256": digest, "output_sha256": sha(signed)})
    result = repack(source, replacements)
    after = shader_programs(result)
    if len(before) != len(after):
        raise ValueError("Program count changed")
    for (stage, old), (new_stage, new) in zip(before, after):
        if stage != new_stage or new != replacements.get(sha(old), old):
            raise ValueError("Material readback changed an unintended shader")
    filename = "large_red_flame.material.candidate"
    (OUT / filename).write_bytes(result)
    report = {"build": "24735202", "status": "offline geometry trial; visibility/culling not game-tested",
              "source_sha256": SOURCE_SHA, "candidate": filename, "candidate_sha256": sha(result),
              "bytes": len(result), "billboard_geometry_factor": 6,
              "vertex_programs": records, "pixel_programs_byte_identical": True,
              "noop_material_byte_identical": True}
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
