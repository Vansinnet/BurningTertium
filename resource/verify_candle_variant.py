"""Independent readback of the two hub candidate records and original bytes."""

import hashlib
import json
from pathlib import Path
import struct

from extract_hub_level import decoder
from inspect_hologram import murmur64
from inspect_hologram_shaders import shader_programs


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
SOURCE = Path(r"D:\Steam\steamapps\common\Warhammer 40,000 DARKTIDE\bundle\8aaa27ad87976cf4")
BASELINE_SHA = "f9ff268a1af54914215aacb88f36643a01cd96840ac1cf769f4e4a3cd3c3ced2"


def sha(value):
    return hashlib.sha256(value).hexdigest()


def envelope(data):
    count, = struct.unpack_from("<I", data, 8)
    if count not in (4376, 4378):
        raise ValueError("Unexpected record count")
    index = list(struct.iter_unpack("<QQI", data[268:268 + 20 * count]))
    cursor = 268 + 20 * count
    chunks, = struct.unpack_from("<I", data, cursor)
    if chunks != 540:
        raise ValueError("Unexpected chunk count")
    cursor += 4
    sizes = struct.unpack_from("<" + "I" * chunks, data, cursor)
    cursor += 4 * chunks
    cursor += (-cursor) % 16
    logical, reserved = struct.unpack_from("<II", data, cursor)
    cursor += 8
    if reserved or not 0 < logical <= chunks * 0x80000:
        raise ValueError("Unexpected logical extent")
    blocks = []
    for size in sizes:
        actual, = struct.unpack_from("<I", data, cursor)
        cursor += 4
        cursor += (-cursor) % 16
        if actual != size or size > 0x80000:
            raise ValueError("Inline chunk length")
        blocks.append(data[cursor:cursor + size])
        cursor += size
    if cursor != len(data) or any(len(block) != size for block, size in zip(blocks, sizes)):
        raise ValueError("Trailing or truncated physical bytes")
    return index, logical, blocks


def main():
    stock = SOURCE.read_bytes()
    noop_info = json.loads((ANALYSIS / "candle-noop-bundle-24735202/report.json").read_text())
    variant_info = json.loads((ANALYSIS / "candle-variant-bundle-24735202/report.json").read_text())
    noop = (ANALYSIS / "candle-noop-bundle-24735202" / noop_info["filename"]).read_bytes()
    variant = (ANALYSIS / "candle-variant-bundle-24735202" / variant_info["bundle_name"]).read_bytes()
    if (sha(stock), sha(noop), sha(variant)) != \
       (BASELINE_SHA, noop_info["candidate_sha256"], variant_info["candidate_sha256"]):
        raise ValueError("Physical file identity drift")
    a, original_length, old_blocks = envelope(stock)
    b, noop_length, noop_blocks = envelope(noop)
    c, variant_length, variant_blocks = envelope(variant)
    if a != b or a != c[:4376] or original_length != noop_length or \
       old_blocks[:-1] != noop_blocks[:-1] or old_blocks[:-1] != variant_blocks[:-1]:
        raise ValueError("Original registration or chunk changed")
    last_stock = decoder()(old_blocks[-1])
    old_used = original_length - 539 * 0x80000
    new_used = variant_length - 539 * 0x80000
    if noop_blocks[-1] != last_stock or len(variant_blocks[-1]) != 0x80000 or \
       variant_blocks[-1][:old_used] != last_stock[:old_used] or \
       any(variant_blocks[-1][new_used:]):
        raise ValueError("Stock logical bytes or final padding changed")
    registered = c[4376:]
    material_identity = (murmur64("material"), murmur64(variant_info["added_material"]), 4)
    effect_identity = (murmur64("particles"), murmur64(variant_info["added_effect"]), 0)
    if registered != [material_identity, effect_identity]:
        raise ValueError("Unexpected appended resource identities")
    material = variant_blocks[-1][old_used:old_used + 68]
    particle = variant_blocks[-1][old_used + 68:new_used]
    original_material = (ANALYSIS / "stock-hub-candle-material-24735202/candle.material.record").read_bytes()
    original_particle = (ANALYSIS / "stock-hub-candle-24735202/candle_flame_01.particles.record").read_bytes()
    if sha(material) != variant_info["material_record_sha256"] or \
       sha(particle) != variant_info["particle_record_sha256"] or \
       len(particle) != len(original_particle):
        raise ValueError("Inserted record size/hash mismatch")
    if material[:8] != original_material[:8] or material[16:38] != original_material[16:38] or \
       material[38:62] != variant_info["material_pointer"].encode() or \
       material[62:] != bytes(6):
        raise ValueError("Added material registration has unsupported form")
    old_material_hash = struct.unpack_from("<Q", original_material, 8)[0]
    old_particle_hash = struct.unpack_from("<Q", original_particle, 8)[0]
    restored = bytearray(particle)
    struct.pack_into("<Q", restored, 8, old_particle_hash)
    old_key = struct.pack("<Q", old_material_hash)
    new_key = struct.pack("<Q", material_identity[1])
    new_at = restored.find(new_key, 38)
    if new_at < 38 or restored.find(new_key, new_at + 1) >= 0:
        raise ValueError("New particle material reference not unique")
    restored[new_at:new_at + 8] = old_key
    if restored != original_particle:
        raise ValueError("Authored flame changed more than name and one material reference")
    stream = Path(variant_info["material_stream_candidate"]).read_bytes()
    if sha(stream) != variant_info["material_stream_sha256"]:
        raise ValueError("Authored material stream drift")
    stock_material_info = json.loads((ANALYSIS / "stock-hub-candle-material-24735202/provenance.json").read_text())
    old_stream = Path(stock_material_info["stream"]).read_bytes()
    if sha(old_stream) != stock_material_info["stream_sha256"]:
        raise ValueError("Original material stream drift")
    old_programs = shader_programs(old_stream)
    new_programs = shader_programs(stream)
    shader_report = json.loads((ANALYSIS / "red-candle-shader-24735202/report.json").read_text())
    before, after = shader_report["stock_shader_sha256"], shader_report["outputs"]["red_holographic"]["sha256"]
    if len(old_programs) != len(new_programs) or sum(
            sha(a[1]) == before and sha(b[1]) == after for a, b in zip(old_programs, new_programs)) != 1 or \
       any(a != b for a, b in zip(old_programs, new_programs) if sha(a[1]) != before):
        raise ValueError("Untargeted flame shader program changed")
    print(json.dumps({"original_records_preserved": len(a), "chunks_byte_identical": 539,
                      "no_op_logical_byte_identical": True,
                      "added_material_and_particle": [variant_info["added_material"], variant_info["added_effect"]],
                      "particle_body_only_one_material_reference_changed": True,
                      "material_pixel_program_replacements": 1, "untargeted_programs_unchanged": True}, indent=2))


if __name__ == "__main__":
    main()
