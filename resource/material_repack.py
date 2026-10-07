"""Adapted from resource/author_grid_material.py: metadata_end and author() verbatim except
the pinned (group, start) layout and the frame inventory, which uses Linux pyooz instead of
the Windows Oodle DLL (decoded frames are verified by their pinned SHA-256)."""
import hashlib, struct, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from inspect_hologram import murmur64
import ooz
import shared as S

LAYOUT = (120, 6484)
EXPECTED_FRAMES = 16


def sha(data):
    return hashlib.sha256(data).hexdigest()


class codec:
    @staticmethod
    def decompress(frame, size):
        out = bytes(ooz.decompress(frame, size))
        if len(out) != size:
            raise ValueError("Kraken decoded length mismatch")
        return out
    dxbc = staticmethod(S.dxbc)


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



def device_frames(shader, start, length, expected_count=EXPECTED_FRAMES):
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


def default_block(shader, offset):
    """u32 0, count, count*(hash, type, value offset relative to block), values; relocatable."""
    zero, count = struct.unpack_from("<II", shader, offset)
    if zero != 0 or count > 64:
        raise ValueError("Unexpected shader default header")
    table = 8 + 12 * count
    sizes = {1: 4, 2: 8, 3: 12, 4: 16}
    end = table
    cursor = table
    for i in range(count):
        _, kind, rel = struct.unpack_from("<III", shader, offset + 8 + 12 * i)
        if kind not in sizes or rel != cursor:
            raise ValueError("Unexpected default entry layout")
        cursor = end = rel + sizes[kind]
    if any(shader[offset + end:]) or len(shader) - (offset + end) >= 16:
        raise ValueError("Unexpected bytes after shader defaults")
    return shader[offset:offset + end]


def author(source, replacements):
    version, mo, ms, so, ss, tail, ts = struct.unpack_from("<7I", source)
    if version != 61 or mo != 28 or so != mo + ms or tail != so + ss or tail + ts != len(source):
        raise ValueError("Material envelope changed")
    shader = source[so:tail]
    head = list(struct.unpack_from("<12I", shader))
    group, group_size, start, device_size = head[8:12]
    old_default = head[5]
    if head[0] != 43 or (group, start) != LAYOUT or not group + group_size <= start or \
       old_default != (start + device_size + 3) & ~3 or len(shader) % 16:
        raise ValueError("Unexpected shader layout")
    if any(shader[start + device_size:old_default]):
        raise ValueError("Unknown pre-default padding")
    defaults = default_block(shader, old_default)
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
                  defaults)
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


