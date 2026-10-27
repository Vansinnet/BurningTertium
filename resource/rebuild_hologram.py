"""Rebuild the four red hologram materials from the installed game's stock files.

Run this after every Darktide update that `reforge verify` reports as changed:

    python mods/active/BurningTertium/resource/rebuild_hologram.py

It reads the stock material streams named in reforge.json, applies the same edits as the
1.2.0 payload and writes payload/redirect/<hash>.btmat, then pins the new stock hashes with
`reforge add`. Nothing is pinned to one game build; the targets are found by structure:

* `hologram_side`, `hologram_bottom`, `hologram`: red `base_color` (and the city's second
  colour) in the material's variable block.
* `hologram` frames 1 and 9 (the city pixel program): the hardcoded green bottom gradient and
  fake light swap their red and green operands (RESEARCH.md, red-mirrored pixel program).
* `hologram_grid` frames 1/13 and 3/15 (the two grid colour pixel programs): the colour output
  becomes the brightest channel in red with a little green and blue.

Every step checks its anchors and stops on anything unexpected (a new material version, a
moved pass slot, a changed instruction pattern); that is the point to read RESEARCH.md again.

Tools: the game's Oodle library (through tools/reforge/cli/bundle8.py) and Microsoft's DXC in
tools/dxc/bin/x64 (dxcompiler.dll and dxc.exe; override with BT_DXC). Windows only.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parent
WORKSPACE = MOD.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(WORKSPACE / "tools/reforge/cli"))
import bundle8  # noqa: E402
import shared as S  # noqa: E402
from inspect_hologram import murmur64  # noqa: E402

GAME = Path(r"D:\Steam\steamapps\common\Warhammer 40,000 DARKTIDE")
DXC = Path(os.environ.get("BT_DXC", WORKSPACE / "tools/dxc/bin/x64"))
KNOWN_VERSIONS = {61, 62}
SHADER_VERSION = 43
VECTOR3 = 2

# Mirrors the hub city's two hardcoded green terms (bottom gradient and fake light): each
# (op, R, G, B) triple is three consecutive instructions; R and G constants swap.
F = {"0.1": "0x3FB99999A0000000", "-0.1": "0xBFB99999A0000000", "0.4": "0x3FD99999A0000000",
     "-0.4": "0xBFD99999A0000000", "0.16": "0x3FC47AE160000000", "0.72": "0x3FE70A3D60000000",
     "0.32": "0x3FD47AE160000000", "0.08": "0x3FB47AE160000000", "0.36": "0x3FD70A3D60000000"}
GREEN_TRIPLES = (("fadd", "-0.1", "-0.4", "-0.1"), ("fadd", "0.1", "0.4", "0.1"),
                 ("fmul", "0.16", "0.72", "0.32"), ("fadd", "0.08", "0.36", "0.16"))

MATERIALS = (
    {"name": "hologram_bottom", "stock": "bundle/data/51/51f7e0e66641669b",
     "colors": {"base_color": (0.4, 0.02, 0.008)}, "shaders": {}},
    {"name": "hologram_side", "stock": "bundle/data/97/97b5490a85966a77",
     "colors": {"base_color": (0.7, 0.035, 0.014)}, "shaders": {}},
    {"name": "hologram", "stock": "bundle/data/ba/bacd9b3be2a4c57f",
     "colors": {"base_color": (0.15, 0.0075, 0.003), "material_variable_046f8451": (0.3, 0.015, 0.006)},
     "shaders": {(1, 9): "mirror_green"}},
    {"name": "hologram_grid", "stock": "bundle/data/59/59c4260bff372016",
     "colors": {}, "shaders": {(1, 13): "red_output", (3, 15): "red_output"}},
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Fail(Exception):
    pass


def need(condition, message):
    if not condition:
        raise Fail(message)


# ---- DXC (COM through ctypes; one calling convention on x64) ----

P, H, U = C.c_void_p, C.c_int32, C.c_uint32


def _method(obj, slot, result, *types):
    table = C.cast(obj, C.POINTER(C.POINTER(P))).contents
    return C.CFUNCTYPE(result, P, *types)(table[slot])


def _release(obj):
    if obj:
        _method(obj, 2, U)(obj)


def _check(hr):
    if hr < 0:
        raise Fail(f"DXC HRESULT 0x{hr & 0xffffffff:08x}")


def _blob_bytes(blob):
    if not blob:
        return b""
    size = _method(blob, 4, C.c_size_t)(blob)
    need(size <= 2_000_000, "DXC blob too large")
    return C.string_at(_method(blob, 3, P)(blob), size)


class Dxc:
    """IDxcAssembler and IDxcValidator from dxcompiler.dll (the validator signs the container)."""

    def __init__(self, folder=DXC):
        need((folder / "dxcompiler.dll").is_file() and (folder / "dxc.exe").is_file(),
             f"DXC not found in {folder} (set BT_DXC)")
        os.add_dll_directory(str(folder))
        self.folder = folder
        self.lib = C.CDLL(str(folder / "dxcompiler.dll"))
        self.version = subprocess.run([str(folder / "dxc.exe"), "--version"], capture_output=True,
                                      timeout=30).stdout.decode().strip()

    def _create(self, clsid, iid):
        fn = self.lib.DxcCreateInstance
        fn.argtypes, fn.restype = [P, P, C.POINTER(P)], H
        c, i = (C.create_string_buffer(uuid.UUID(x).bytes_le) for x in (clsid, iid))
        obj = P()
        _check(fn(c, i, C.byref(obj)))
        need(obj, "DXC returned no object")
        return obj

    def _blob(self, data):
        need(0 < len(data) <= 900_000, "DXC input out of bounds")
        utils = self._create("6245d6af-66e0-48fd-80b4-4d271796748c", "4605c4cb-2019-492a-ada4-65f20bb7d67f")
        blob = P()
        try:
            self._memory = C.create_string_buffer(data)
            _check(_method(utils, 6, H, P, U, U, C.POINTER(P))(utils, self._memory, len(data), 0, C.byref(blob)))
            return blob
        finally:
            _release(utils)

    def _operation(self, data, assemble):
        blob, obj, res, out, err = self._blob(data), P(), P(), P(), P()
        try:
            if assemble:
                obj = self._create("d728db68-f903-4f80-94cd-dccf76ec7151", "091f7a26-1c1f-4948-904b-e6e3a8a771d5")
                _check(_method(obj, 3, H, P, C.POINTER(P))(obj, blob, C.byref(res)))
            else:
                obj = self._create("8ca3e215-f728-4cf3-8cdd-88af917587a1", "a6e82bd2-1fd7-4826-9811-2857e797f49a")
                _check(_method(obj, 3, H, P, U, C.POINTER(P))(obj, blob, 0, C.byref(res)))
            status = H()
            _check(_method(res, 3, H, C.POINTER(H))(res, C.byref(status)))
            _check(_method(res, 5, H, C.POINTER(P))(res, C.byref(err)))
            message = _blob_bytes(err).decode("utf-8", "replace").rstrip("\0")
            need(status.value >= 0, f"DXC operation failed: {message}")
            _check(_method(res, 4, H, C.POINTER(P))(res, C.byref(out)))
            return _blob_bytes(out), message
        finally:
            for item in (err, out, res, obj, blob):
                _release(item)

    def compile(self, module):
        """LLVM IR text -> validated, signed DXBC container."""
        encoded, warning = self._operation(module.encode(), assemble=True)
        need(not warning, "DXC assembly warning: " + warning)
        signed, warning = self._operation(encoded, assemble=False)
        need(not warning and signed[4:20] != bytes(16), "DXC validation failed: " + warning)
        return signed

    def dump(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "program.bin"
            path.write_bytes(data)
            result = subprocess.run([str(self.folder / "dxc.exe"), "-dumpbin", str(path)],
                                    capture_output=True, timeout=60)
        need(result.returncode == 0 and not result.stderr and 0 < len(result.stdout) <= 2_000_000,
             "DXC disassembly failed: " + result.stderr.decode("utf-8", "replace"))
        return result.stdout.decode().replace("\r\n", "\n")


# ---- Material envelope, variables and shader frames ----

def envelope(data):
    version, mo, ms, so, ss, tail, ts = struct.unpack_from("<7I", data)
    need(version in KNOWN_VERSIONS, f"material version {version} is new; check the format before adding it")
    need(mo == 28 and so == mo + ms and tail == so + ss and tail + ts == len(data), "material envelope changed")
    return mo, ms, so, ss, tail


def variables(data):
    """{name hash: (type, absolute value offset)} from the material block's variable table."""
    mo, ms, _, _, _ = envelope(data)
    block = data[mo:mo + ms]
    cursor = 20
    for width in (4, 12, 8, 20):  # u32, (u32, u64), (u32, u32), 5 x u32 variable descriptors
        count, = struct.unpack_from("<I", block, cursor)
        need(count <= 256 and cursor + 4 + count * width <= len(block), "material table out of bounds")
        if width == 20:
            rows = [struct.unpack_from("<5I", block, cursor + 4 + 20 * i) for i in range(count)]
        cursor += 4 + count * width
    size, = struct.unpack_from("<I", block, cursor)
    values = cursor + 4
    need(values + size <= len(block), "material values out of bounds")
    table = {}
    for kind, zero, key, offset, zero2 in rows:
        need(zero == 0 and zero2 == 0 and offset < size, "unexpected variable descriptor")
        table[key] = (kind, mo + values + offset)
    return table


def recolor_variables(data, colors):
    table = variables(data)
    result = bytearray(data)
    edits = []
    for name, color in colors.items():
        key = murmur64(name) >> 32
        need(key in table and table[key][0] == VECTOR3, f"material variable {name} is gone or not a vector3")
        at = table[key][1]
        original = struct.unpack_from("<3f", data, at)
        struct.pack_into("<3f", result, at, *color)
        edits.append({"variable": name, "offset": at, "stock": original,
                      "red": struct.unpack_from("<3f", result, at)})
    restored = bytearray(result)
    for row in edits:
        restored[row["offset"]:row["offset"] + 12] = data[row["offset"]:row["offset"] + 12]
    need(restored == data, "colour edit changed bytes outside its variables")
    return bytes(result), edits


def metadata_end(shader, start, device_end):
    need(start + 16 <= device_end and struct.unpack_from("<I", shader, start)[0] == 5,
         "unexpected shader program metadata")
    cursor = start + 16
    for width in (6, 0, 0, 7, 7, 7, 7, 4, 3, 3):
        count, = struct.unpack_from("<I", shader, cursor)
        need(count <= 512 and not (width == 0 and count) and cursor + 4 + count * width * 4 <= device_end,
             "unexpected shader metadata table")
        cursor += 4 + count * width * 4
    return cursor


def device_frames(shader, start, length, oodle):
    stop, cursor, frames = start + length, start, []
    while (begin := shader.find(b"\x8c\x06", cursor, stop)) != -1:
        cursor = begin + 2
        if begin < start + 8 or begin + 5 > stop:
            continue
        envelope_tag, encoded = struct.unpack_from("<II", shader, begin - 8)
        finish = begin + encoded
        if envelope_tag != 1 or not begin + 8 <= finish <= stop - 16:
            continue
        frame = shader[begin:finish]
        if int.from_bytes(frame[2:5], "big") + 1 != len(frame) - 5:
            continue
        kind, decoded_size, key = struct.unpack_from("<IIQ", shader, finish)
        if kind != 5 or not 32 <= decoded_size <= 262144 or murmur64(frame) != key:
            continue
        end = metadata_end(shader, finish, stop)
        payload = frame[5:] if len(frame) - 5 == decoded_size else oodle.decompress(frame, decoded_size)
        need(len(payload) == decoded_size, "Kraken decoded length mismatch")
        S.dxbc(payload)
        frames.append({"envelope": begin - 8, "begin": begin, "finish": finish, "end": end,
                       "payload": payload, "sha256": sha(payload)})
        cursor = end
    need(frames and len({f["begin"] for f in frames}) == len(frames), "no shader frames found")
    return frames


def shader_layout(data, oodle):
    _, _, so, _, tail = envelope(data)
    shader = data[so:tail]
    head = struct.unpack_from("<12I", shader)
    group, group_size, start, device_size = head[8:12]
    need(head[0] == SHADER_VERSION and group + group_size <= start and
         head[5] == (start + device_size + 3) & ~3 and len(shader) % 16 == 0, "unexpected shader layout")
    need(not any(shader[start + device_size:head[5]]), "unknown pre-default padding")
    return shader, start, device_size, head[5], device_frames(shader, start, device_size, oodle)


def default_block(shader, offset):
    zero, count = struct.unpack_from("<II", shader, offset)
    need(zero == 0 and count <= 64, "unexpected shader default header")
    sizes, cursor = {1: 4, 2: 8, 3: 12, 4: 16}, 8 + 12 * count
    end = cursor
    for i in range(count):
        _, kind, rel = struct.unpack_from("<III", shader, offset + 8 + 12 * i)
        need(kind in sizes and rel == cursor, "unexpected default entry layout")
        cursor = end = rel + sizes[kind]
    need(not any(shader[offset + end:]) and len(shader) - (offset + end) < 16, "bytes after shader defaults")
    return shader[offset:offset + end]


def replace_frames(data, replacements, oodle):
    """Swap whole shader programs, keyed by stock program SHA-256; stored (uncompressed) frames."""
    mo, ms, so, ss, tail = envelope(data)
    shader, start, device_size, old_default, frames = shader_layout(data, oodle)
    defaults = default_block(shader, old_default)
    pieces, previous, found = [], start, set()
    for frame in frames:
        pieces.append(shader[previous:frame["envelope"]])
        candidate = replacements.get(frame["sha256"])
        if candidate is None:
            pieces.append(shader[frame["envelope"]:frame["end"]])
        else:
            found.add(frame["sha256"])
            need(candidate[:4] == b"DXBC" and 32 <= len(candidate) <= 262143, "unexpected replacement program")
            encoded = b"\x8c\x06" + (len(candidate) - 1).to_bytes(3, "big") + candidate
            metadata = bytearray(shader[frame["finish"]:frame["end"]])
            struct.pack_into("<IQ", metadata, 4, len(candidate), murmur64(encoded))
            pieces.extend((struct.pack("<II", 1, len(encoded)), encoded, bytes(metadata)))
        previous = frame["end"]
    pieces.append(shader[previous:start + device_size])
    need(found == set(replacements), "an intended program is absent")
    device = b"".join(pieces)
    next_default = (start + len(device) + 3) & ~3
    prefix = bytearray(shader[:start])
    struct.pack_into("<I", prefix, 20, next_default)
    struct.pack_into("<I", prefix, 44, len(device))
    new_shader = bytes(prefix) + device + bytes(next_default - start - len(device)) + defaults
    new_shader += bytes((-len(new_shader)) % 16)
    wrapper = bytearray(data[:mo])
    struct.pack_into("<II", wrapper, 16, len(new_shader), so + len(new_shader))
    result = bytes(wrapper) + data[mo:so] + new_shader + data[tail:]
    if not replacements:
        need(result == data, "no-op repack did not reproduce the material")
    return result


# ---- Shader edits ----

def mirror_green(module, _noop):
    body = re.search(r"^define void @ps_main\(\) \{\n.*?^\}", module, re.M | re.S)
    need(body, "city pixel function missing")
    lines = body[0].split("\n")
    pattern = re.compile(r"^  (%\d+) = (fadd|fmul) fast float (%\d+), (0x[0-9A-F]{16})$")
    edits = []
    for op, r, g, b in GREEN_TRIPLES:
        want = (F[r], F[g], F[b])
        hits = []
        for i in range(len(lines) - 2):
            rows = [pattern.match(line) for line in lines[i:i + 3]]
            if all(rows) and all(m[2] == op for m in rows) and tuple(m[4] for m in rows) == want:
                hits.append(i)
        need(len(hits) == 1, f"green term {op} ({r}, {g}, {b}) found {len(hits)} times, expected once")
        i = hits[0]
        red, green = lines[i], lines[i + 1]
        lines[i] = red[:-18] + F[g]
        lines[i + 1] = green[:-18] + F[r]
        edits += [(red.strip(), lines[i].strip()), (green.strip(), lines[i + 1].strip())]
    return module[:body.start()] + "\n".join(lines) + module[body.end():], edits


def red_output(module, _noop):
    body = re.search(r"^define void @ps_main\(\) \{\n.*?^\}", module, re.M | re.S)
    need(body, "grid pixel function missing")
    pattern = r"^  call void @dx.op.storeOutput.f32\(i32 5, i32 0, i32 0, i8 ([0123]), float ([^)]+)\)"
    outputs = list(re.finditer(pattern, body[0], re.M))
    need(len(outputs) == 4 and [int(o[1]) for o in outputs] == [0, 1, 2, 3], "grid colour outputs changed")
    r, g, b = (outputs[i][2] for i in range(3))
    code = (f"  %bt.maxrg = call float @dx.op.binary.f32(i32 35, float {r}, float {g})\n"
            f"  %bt.red = call float @dx.op.binary.f32(i32 35, float %bt.maxrg, float {b})\n"
            "  %bt.green = fmul float %bt.red, 0x3FA99999A0000000\n"
            "  %bt.blue = fmul float %bt.red, 0x3F947AE140000000\n")
    altered = body[0][:outputs[0].start()] + code + body[0][outputs[0].start():]
    for channel, value in enumerate(("%bt.red", "%bt.green", "%bt.blue")):
        old = outputs[channel][0]
        need(altered.count(old) == 1, "grid output replacement is ambiguous")
        altered = altered.replace(old, old.rsplit("float ", 1)[0] + "float " + value + ")")
    need(altered.count(outputs[3][0]) == 1, "grid alpha output changed")
    result = module[:body.start()] + altered + module[body.end():]
    if "declare float @dx.op.binary.f32(" not in result:
        result += "\ndeclare float @dx.op.binary.f32(i32, float, float) #0\n"
    return result, "max(r, g, b) -> (1, 0.05, 0.02) x"


EDITS = {"mirror_green": mirror_green, "red_output": red_output}


def parts(binary):
    return {row["tag"]: binary[row["offset"] + 8:row["offset"] + 8 + row["size"]] for row in S.dxbc(binary)}


def body_lines(text):
    body = re.search(r"^define void @[a-z_]+\(\) \{\n.*?^\}", text, re.M | re.S)
    need(body, "disassembly has no entry function")
    # typed_module renumbers metadata nodes; their references are not program behaviour.
    return [re.sub(r"!\d+", "!N", line) for line in body[0].split("\n")]


def edit_program(stock, edit, dxc):
    chunks = parts(stock)
    need(all(k in chunks for k in ("STAT", "DXIL", "SFI0", "ISG1", "OSG1", "PSV0")), "program chunks changed")
    original = dxc.dump(stock)
    need("define void @ps_main()" in original, "target is not a pixel program")
    noop = S.typed_module(original, dxc.dump(chunks["STAT"]))
    modified, detail = EDITS[edit](noop, noop)
    built = {}
    for kind, module in (("noop", noop), ("edited", modified)):
        signed = dxc.compile(module)
        candidate = parts(signed)
        need(all(chunks[k] == candidate[k] for k in ("SFI0", "ISG1", "OSG1", "PSV0")), "program signature changed")
        built[kind] = signed
    # The no-op rebuild must disassemble to the stock function; the edit may differ only as intended.
    stock_body = body_lines(original)
    noop_body = body_lines(dxc.dump(built["noop"]))
    need(stock_body == noop_body, "no-op rebuild does not reproduce the stock function")
    edited_body = body_lines(dxc.dump(built["edited"]))
    if edit == "mirror_green":
        diff = [(a.strip(), b.strip()) for a, b in zip(noop_body, edited_body) if a != b]
        need(len(noop_body) == len(edited_body) and diff == detail, "unexpected readback difference")
    else:
        need(any("%bt.red" in line for line in edited_body), "red transform missing after readback")
    return built["edited"], {"stock_sha256": sha(stock), "edit": edit, "detail": detail,
                             "noop_sha256": sha(built["noop"]), "edited_sha256": sha(built["edited"]),
                             "edited_bytes": len(built["edited"])}


# ---- One material ----

def build(spec, stock, oodle, dxc):
    report = {"material": spec["name"], "stock": spec["stock"], "stock_sha256": sha(stock),
              "version": struct.unpack_from("<I", stock)[0]}
    data, report["colors"] = recolor_variables(stock, spec["colors"])
    _, _, _, _, frames = shader_layout(data, oodle)
    replacements, programs = {}, []
    for slots, edit in spec["shaders"].items():
        need(max(slots) < len(frames), f"pass slots {slots} missing ({len(frames)} frames)")
        source = {frames[i]["sha256"] for i in slots}
        need(len(source) == 1, f"pass slots {slots} no longer share one program")
        digest = source.pop()
        need(digest not in replacements, f"pass slots {slots} share a program with another target")
        program, row = edit_program(frames[slots[0]]["payload"], edit, dxc)
        replacements[digest] = program
        programs.append(row | {"slots": list(slots)})
    result = replace_frames(data, replacements, oodle) if replacements else data
    if replacements:
        readback = shader_layout(result, oodle)[4]
        need(len(readback) == len(frames), "frame count changed")
        for i, (old, new) in enumerate(zip(frames, readback)):
            expected = sha(replacements[old["sha256"]]) if old["sha256"] in replacements else old["sha256"]
            need(new["sha256"] == expected, f"frame {i} read back wrong")
        _, ms, so, _, _ = envelope(data)
        need(result[28:28 + ms] == data[28:28 + ms], "material block changed by the shader repack")
    report["programs"] = programs
    report["output_sha256"] = sha(result)
    report["output_bytes"] = len(result)
    return result, report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game", type=Path, default=GAME)
    parser.add_argument("--stock", type=Path, help="folder of stock streams named like the game's (e.g. an "
                        "older build's originals) instead of the game folder; nothing is pinned")
    parser.add_argument("--out", type=Path, help="write the materials here instead of payload/redirect")
    args = parser.parse_args()
    oodle = bundle8.Oodle(args.game / "binaries/oo2core_9_win64.dll")
    dxc = Dxc()
    redirects = {r["stock"]: r for r in json.loads((MOD / "reforge.json").read_text(encoding="utf-8"))["redirects"]}
    need(set(redirects) == {m["stock"] for m in MATERIALS}, "reforge.json redirects differ from this script")
    outputs, reports = [], []
    for spec in MATERIALS:
        source = (args.stock / spec["stock"].rsplit("/", 1)[1]) if args.stock else args.game / spec["stock"]
        result, report = build(spec, source.read_bytes(), oodle, dxc)
        outputs.append((spec, result))
        reports.append(report)
        print(f"{spec['name']}: stock {report['stock_sha256'][:12]} v{report['version']} -> "
              f"{report['output_sha256'][:12]} ({len(report['colors'])} colours, {len(report['programs'])} programs)")
    out = args.out or MOD
    for spec, result in outputs:
        path = (args.out / Path(redirects[spec["stock"]]["file"]).name) if args.out else \
            MOD / redirects[spec["stock"]]["file"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(result)
    summary = {"dxc": dxc.version, "game": str(args.game), "stock_folder": str(args.stock) if args.stock else None,
               "materials": reports}
    folder = MOD / "analysis" / ("rebuild-" + sha("".join(r["stock_sha256"] for r in reports).encode())[:12])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "report.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"report: {folder / 'report.json'}")
    if not args.stock and not args.out:
        reforge = WORKSPACE / "tools/reforge/reforge.cmd"
        for spec in MATERIALS:
            subprocess.run([str(reforge), "add", str(MOD), spec["stock"], "--file", redirects[spec["stock"]]["file"],
                            "--game", str(args.game)], check=True)
    else:
        print(f"materials written to {out}; reforge.json not changed")


if __name__ == "__main__":
    try:
        main()
    except Fail as exc:
        sys.exit(f"rebuild_hologram: {exc}")
