"""Offline two-record candle variant in the hub bundle; never edits installed game files."""

import hashlib
import json
from pathlib import Path
import struct

from extract_hub_level import decoder
from inspect_hologram import GAME, MAGICS, murmur64


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/candle-variant-bundle-24735202"
GAME_SOURCE = GAME / "bundle/8aaa27ad87976cf4"
SOURCE_SHA = "f9ff268a1af54914215aacb88f36643a01cd96840ac1cf769f4e4a3cd3c3ced2"
PARTICLE = ROOT / "analysis/stock-hub-candle-24735202/candle_flame_01.particles.record"
PARTICLE_SHA = "9a611b01bdd84a3834b541672daf498a590186452224cca424396b0f7f21e2a4"
STOCK_MATERIAL = ROOT / "analysis/stock-hub-candle-material-24735202/candle.material.record"
STOCK_MATERIAL_SHA = "24b7dfd1d1fd14fddb4235847be03c7b1ffb5e4221a63dcd8d77c55ac6ea2cdb"
NEW_STREAM = ROOT / "analysis/red-candle-material-24735202/candle_flame_red.material.candidate"
NEW_STREAM_SHA = "8069dc045f4ecc46b0355c0e03cf314103dabdcde09f0a442b8c9cc8926f335f"
EFFECT = "content/fx/particles/burning_tertium/hologram_flame_red"
MATERIAL = "content/environment/artsets/imperial/hub/burning_tertium/candle_hologram_red"
OLD_MATERIAL_HASH = 0xBEA498CE22B86BF9
CHUNK = 0x80000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_bundle(data):
    if not 100_000_000 <= len(data) <= 160_000_000 or data[:8] not in MAGICS:
        raise ValueError("Unexpected hub bundle format/size")
    count, = struct.unpack_from("<I", data, 8)
    if count not in (4376, 4378):
        raise ValueError("Unexpected hub resource count")
    start = 268
    index = list(struct.iter_unpack("<QQI", data[start:start + count * 20]))
    if len(index) != count:
        raise ValueError("Incomplete hub bundle index")
    at = start + 20 * count
    chunks, = struct.unpack_from("<I", data, at)
    at += 4
    if chunks != 540:
        raise ValueError("Unexpected original hub chunk count")
    sizes = list(struct.unpack_from("<" + "I" * chunks, data, at))
    if any(not 0 < size <= CHUNK for size in sizes):
        raise ValueError("Unexpected original chunk lengths")
    at += 4 * chunks
    table_padding = data[at:at + (-at) % 16]
    at += len(table_padding)
    logical_length, zero = struct.unpack_from("<II", data, at)
    at += 8
    if zero or not (chunks - 1) * CHUNK < logical_length <= chunks * CHUNK:
        raise ValueError("Original logical extent")
    decoder_function = decoder()
    blocks = []
    padding = []
    decoded = []
    for size in sizes:
        current, = struct.unpack_from("<I", data, at)
        at += 4
        pad = data[at:at + (-at) % 16]
        at += len(pad)
        block = data[at:at + current]
        at += current
        if current != size or len(block) != current:
            raise ValueError("Inline chunk size mismatch")
        padding.append(pad)
        blocks.append(block)
        decoded.append(decoder_function(block))
    if at != len(data):
        raise ValueError("Extra physical bundle bytes")
    all_bytes = b"".join(decoded)
    if len(all_bytes) != chunks * CHUNK or any(all_bytes[logical_length:]):
        raise ValueError("Nonzero or incomplete original final padding")
    return {"magic": data[:8], "opaque_header": data[12:268], "index": index, "blocks": blocks,
            "table_padding": table_padding, "chunk_padding": padding,
            "logical": all_bytes[:logical_length], "length": logical_length}


def walk_records(logical, index):
    cursor = 0
    for number, (expected_kind, expected_name, _) in enumerate(index):
        if cursor + 24 > len(logical):
            raise ValueError("Truncated resource header")
        kind, name, count, reserved = struct.unpack_from("<QQII", logical, cursor)
        if (kind, name) != (expected_kind, expected_name) or reserved or not 1 <= count <= 64:
            raise ValueError("Logical index/record mismatch: " + str(number))
        cursor += 24
        descriptors = []
        for _ in range(count):
            if cursor + 14 > len(logical):
                raise ValueError("Truncated resource descriptor")
            _, first, body_size, second, tail_size = struct.unpack_from("<IBIBI", logical, cursor)
            if first not in (0, 1) or second != 1:
                raise ValueError("Unexpected variant flags")
            cursor += 14
            descriptors.append((body_size, tail_size))
        for body_size, tail_size in descriptors:
            cursor += body_size + tail_size
            if cursor > len(logical):
                raise ValueError("Resource body exceeds logical stream")
    if cursor != len(logical):
        raise ValueError("Unconsumed logical bundle bytes")
    return cursor


def serialize(bundle, index, logical, blocks):
    if len(logical) > len(blocks) * CHUNK or len(index) > 5000:
        raise ValueError("Hub expansion exceeds bounded profile")
    result = bytearray(bundle["magic"])
    result.extend(struct.pack("<I", len(index)))
    result.extend(bundle["opaque_header"])
    result.extend(b"".join(struct.pack("<QQI", *row) for row in index))
    result.extend(struct.pack("<I", len(blocks)))
    result.extend(struct.pack("<" + "I" * len(blocks), *(len(block) for block in blocks)))
    table_pad = (-len(result)) % 16
    previous = bundle["table_padding"]
    if len(previous) != table_pad and any(previous):
        raise ValueError("Unpreservable original index alignment bytes")
    result.extend(previous if len(previous) == table_pad else bytes(table_pad))
    result.extend(struct.pack("<II", len(logical), 0))
    for index_num, block in enumerate(blocks):
        result.extend(struct.pack("<I", len(block)))
        pad_needed = (-len(result)) % 16
        old_pad = bundle["chunk_padding"][index_num]
        if len(old_pad) != pad_needed and any(old_pad):
            raise ValueError("Unpreservable original chunk alignment bytes")
        result.extend(old_pad if len(old_pad) == pad_needed else bytes(pad_needed))
        result.extend(block)
    return bytes(result)


def prepare_new_records(source_index, particle, registration, stream):
    name_hash = murmur64(MATERIAL)
    effect_hash = murmur64(EFFECT)
    material_kind = murmur64("material")
    particle_kind = murmur64("particles")
    existing = {entry[:2] for entry in source_index}
    if (material_kind, name_hash) in existing or (particle_kind, effect_hash) in existing:
        raise ValueError("Authored resource identity collision")
    stream_hash = hashlib.sha256((MATERIAL + "|stock24735202").encode()).hexdigest()[:16]
    pointer = "data/" + stream_hash[:2] + "/" + stream_hash
    if (GAME / "bundle" / pointer).exists() or len(pointer) != 24:
        raise ValueError("New material stream path collision")
    original_kind, original_name, count, reserved = struct.unpack_from("<QQII", registration)
    descriptor = struct.unpack_from("<IBIBI", registration, 24)
    if (original_kind, original_name, count, reserved) != (material_kind, OLD_MATERIAL_HASH, 1, 0) or \
       descriptor != (0, 1, 30, 1, 0):
        raise ValueError("Unrecognized material registration profile")
    new_material = (struct.pack("<QQII", material_kind, name_hash, 1, 0) + registration[24:38] +
                    pointer.encode() + bytes(30 - len(pointer)))
    if len(new_material) != len(registration):
        raise ValueError("New material pointer does not fit existing resource body")
    particle_kind_old, name_old, variants, zero = struct.unpack_from("<QQII", particle)
    if (particle_kind_old, variants, zero) != (particle_kind, 1, 0) or \
       name_old != murmur64("content/fx/particles/environment/candle_flame_01"):
        raise ValueError("Unrecognized candle particle identity")
    body = particle[38:]
    if struct.unpack_from("<I", body)[0] != 102 or struct.unpack_from("<II", body, 36) != (0, 1):
        raise ValueError("Unsupported candle particle body")
    words = struct.unpack_from("<144I", body, 44)
    visualizer = 44 + words[140]
    if struct.unpack_from("<I", body, visualizer)[0] != 0:
        raise ValueError("Candle cloud is not a billboard")
    before = bytearray(body)
    if struct.unpack_from("<Q", before, visualizer + 12)[0] != OLD_MATERIAL_HASH or \
       before.count(struct.pack("<Q", OLD_MATERIAL_HASH)) != 1:
        raise ValueError("Original material reference is not unique")
    struct.pack_into("<Q", before, visualizer + 12, name_hash)
    new_particle = struct.pack("<QQII", particle_kind, effect_hash, 1, 0) + particle[24:38] + bytes(before)
    if len(new_particle) != len(particle) or len(stream) < 1000:
        raise ValueError("Unrecognized authored particle/material length")
    return new_material, new_particle, pointer


def main():
    if OUT.exists():
        raise ValueError("Candidate output exists")
    source = GAME_SOURCE.read_bytes()
    particle = PARTICLE.read_bytes()
    old_material = STOCK_MATERIAL.read_bytes()
    stream = NEW_STREAM.read_bytes()
    if (sha(source), sha(particle), sha(old_material), sha(stream)) != \
       (SOURCE_SHA, PARTICLE_SHA, STOCK_MATERIAL_SHA, NEW_STREAM_SHA):
        raise ValueError("Original or authored source SHA-256 differs")
    bundle = read_bundle(source)
    walk_records(bundle["logical"], bundle["index"])
    if serialize(bundle, bundle["index"], bundle["logical"], bundle["blocks"]) != source:
        raise ValueError("Original physical bundle did not round-trip exactly")
    new_material, new_particle, pointer = prepare_new_records(bundle["index"], particle, old_material, stream)
    appended = new_material + new_particle
    logical = bundle["logical"] + appended
    tail_used = bundle["length"] - (len(bundle["blocks"]) - 1) * CHUNK
    if tail_used + len(appended) > CHUNK:
        raise ValueError("Candidate requires an additional chunk")
    original_last = bundle["blocks"][-1]
    # All prior compressed chunks remain byte-identical; the last one becomes a stored chunk.
    original_last_decoded = decoder()(original_last)
    next_last = original_last_decoded[:tail_used] + appended + bytes(CHUNK - tail_used - len(appended))
    blocks = bundle["blocks"][:-1] + [next_last]
    material_index = (murmur64("material"), murmur64(MATERIAL), 4)
    particle_index = (murmur64("particles"), murmur64(EFFECT), 0)
    index = bundle["index"] + [material_index, particle_index]
    walk_records(logical, index)
    candidate = serialize(bundle, index, logical, blocks)
    if len(candidate) <= len(source) or candidate[:12] == source[:12]:
        raise ValueError("Candidate physical envelope did not change as expected")
    # A fresh reader must consume every original and added record from the serialized bytes.
    decoded = read_bundle(candidate)
    if decoded["index"] != index or decoded["logical"] != logical or \
       decoded["blocks"][:-1] != bundle["blocks"][:-1]:
        raise ValueError("Candidate bundle readback changed unrelated records/chunks")
    walk_records(decoded["logical"], decoded["index"])
    OUT.mkdir(parents=True)
    filename = "8aaa27ad87976cf4.bundle.candidate"
    (OUT / filename).write_bytes(candidate)
    report = {"build": "24735202", "status": "OFFLINE TWO-RESOURCE CANDIDATE; not installed or game-tested",
              "source_sha256": SOURCE_SHA, "candidate_sha256": sha(candidate),
              "candidate_bytes": len(candidate), "bundle_name": filename,
              "original_records_unchanged": 4376, "compressed_chunks_unchanged": 539,
              "no_op_physical_identity": True, "added_material": MATERIAL,
              "added_effect": EFFECT, "material_pointer": pointer,
              "material_stream_candidate": str(NEW_STREAM), "material_stream_sha256": NEW_STREAM_SHA,
              "material_record_sha256": sha(new_material), "particle_record_sha256": sha(new_particle)}
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
