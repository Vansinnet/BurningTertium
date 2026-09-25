"""Offline red-output experiment for the two pinned grid color pixel programs."""

import ctypes as C
import hashlib
import importlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[4]
BASE = Path(__file__).resolve().parents[1] / "analysis"
INPUT = BASE / "hologram-shaders-24735202"
OUT = BASE / "red-grid-shaders-24735202"
TARGETS = ("7c5f430226fe", "903327e46fdd")
sys.path.insert(0, str(ROOT / "docs/analysis-flame-huecycle-20260918-n1"))
sys.path.insert(0, str(ROOT / "docs/analysis-flame-shader43-20260918-j1"))
dxc_api = importlib.import_module("dxc_api")
codec = importlib.import_module("decode")


def sha(data):
    return hashlib.sha256(data).hexdigest()


class BoundedDxc(dxc_api.Dxc):
    def blob(self, data):
        if not 0 < len(data) <= 900_000:
            raise ValueError("Grid shader module exceeds offline bound")
        utils = self.create("6245d6af-66e0-48fd-80b4-4d271796748c",
                            "4605c4cb-2019-492a-ada4-65f20bb7d67f")
        blob = dxc_api.P()
        try:
            memory = C.create_string_buffer(data)
            dxc_api.check(dxc_api.method(utils, 6, dxc_api.H, dxc_api.P, dxc_api.U, dxc_api.U,
                                         C.POINTER(dxc_api.P))(utils, memory, len(data), 0, C.byref(blob)))
            return blob
        finally:
            dxc_api.release(utils)


def parts(binary):
    return {row["tag"]: binary[row["offset"] + 8:row["offset"] + 8 + row["size"]]
            for row in codec.dxbc(binary)}


def dump(path):
    result = subprocess.run([str(dxc_api.TOOL / "dxc.exe"), "-dumpbin", str(path)],
                            capture_output=True, timeout=30, check=True)
    if result.stderr or not 0 < len(result.stdout) <= 900_000:
        raise ValueError("Unexpected DXC disassembly")
    return result.stdout.decode().replace("\r\n", "\n")


def typed_module(original, stat, entrypoint="ps_main"):
    if entrypoint not in ("ps_main", "vs_main"):
        raise ValueError("Unsupported shader entrypoint")
    body = re.search(r"^define void @" + entrypoint + r"\(\) \{\n.*?^\}", original, re.M | re.S)
    if not body:
        raise ValueError("Missing stock pixel function")
    module = stat[stat.index("target datalayout"):]
    if module.count("declare void @" + entrypoint + "()") != 1 or module.count("!2 = !{i32 0, i32 0}") != 1:
        raise ValueError("Unsupported STAT module framing")
    module = module.replace("!2 = !{i32 0, i32 0}", "!2 = !{i32 1, i32 7}")
    counter = re.search(r"^!dx.counters = !\{(!\d+)\}$", module, re.M)
    if not counter:
        raise ValueError("Missing STAT counter metadata")
    module = re.sub(r"^!dx.counters = .*\n", "", module, flags=re.M)
    module = re.sub(r"^" + re.escape(counter[1]) + r" = .*\n", "", module, flags=re.M)
    executable = body[0]
    refs = set(re.findall(r"!(\d+)", executable))
    if refs:
        next_id = 1 + max(map(int, re.findall(r"^!(\d+) =", module, re.M)))
        mapping = {key: str(next_id + i) for i, key in enumerate(sorted(refs, key=int))}
        extra_id = next_id + len(mapping)
        for key, newid in mapping.items():
            hint = re.search(r"^!" + key + r" = distinct !\{!" + key +
                             r', !"dx.controlflow.hints", i32 ([12])\}$', original, re.M)
            if not hint:
                original_definition = re.search(r"^!" + key + r" = .*", original, re.M)
                loop = re.fullmatch(r"!" + key + r" = distinct !\{!" + key + r", !(\d+)\}",
                                    original_definition[0]) if original_definition else None
                if not loop or not re.search(r'^!' + loop[1] + r' = !\{!"llvm.loop.unroll.disable"\}$',
                                              original, re.M):
                    raise ValueError("Unsupported control-flow metadata " + key + ": " +
                                     (original_definition[0] if original_definition else "missing"))
                module += f'\n!{newid} = distinct !{{!{newid}, !{extra_id}}}\n'
                module += f'!{extra_id} = !{{!"llvm.loop.unroll.disable"}}\n'
                extra_id += 1
            else:
                module += f'\n!{newid} = distinct !{{!{newid}, !"dx.controlflow.hints", i32 {hint[1]}}}\n'
        executable = re.sub(r"!(\d+)", lambda m: "!" + mapping[m[1]], executable)
    return module.replace("declare void @" + entrypoint + "()", executable)


def recolor(module):
    body = re.search(r"^define void @ps_main\(\) \{\n.*?^\}", module, re.M | re.S)
    if not body:
        raise ValueError("Missing pixel function in typed module")
    pattern = r"^  call void @dx.op.storeOutput.f32\(i32 5, i32 0, i32 0, i8 ([0123]), float ([^)]+)\)"
    outputs = list(re.finditer(pattern, body[0], re.M))
    if len(outputs) != 4 or [int(o[1]) for o in outputs] != [0, 1, 2, 3]:
        raise ValueError("Grid color-output signature changed")
    r, g, b = (outputs[i][2] for i in range(3))
    code = (f"  %bt.maxrg = call float @dx.op.binary.f32(i32 35, float {r}, float {g})\n"
            f"  %bt.red = call float @dx.op.binary.f32(i32 35, float %bt.maxrg, float {b})\n"
            "  %bt.green = fmul float %bt.red, 0x3FA99999A0000000\n"
            "  %bt.blue = fmul float %bt.red, 0x3F947AE140000000\n")
    altered = body[0][:outputs[0].start()] + code + body[0][outputs[0].start():]
    for channel, value in enumerate(("%bt.red", "%bt.green", "%bt.blue")):
        old = outputs[channel][0]
        new = old.rsplit("float ", 1)[0] + "float " + value + ")"
        if altered.count(old) != 1:
            raise ValueError("Grid output replacement is ambiguous")
        altered = altered.replace(old, new)
    if altered.count(outputs[3][0]) != 1:
        raise ValueError("Grid alpha output changed")
    result = module[:body.start()] + altered + module[body.end():]
    if "declare float @dx.op.binary.f32(" not in result:
        result += "\ndeclare float @dx.op.binary.f32(i32, float, float) #0\n"
    return result


def build():
    if (OUT / "report.json").exists():
        raise ValueError("Output already exists")
    witness = json.loads((INPUT / "provenance.json").read_text())
    pinned = set(next(row for row in witness["sources"] if row["material"] == "hologram_grid")
                 ["unique_pixel_sha256"])
    compiler = BoundedDxc()
    payload = []
    for stem in TARGETS:
        source = INPUT / (stem + ".dxbc")
        binary = source.read_bytes()
        if sha(binary) not in pinned:
            raise ValueError("Pixel source not in verified grid material")
        chunks = parts(binary)
        if not all(key in chunks for key in ("STAT", "DXIL", "SFI0", "ISG1", "OSG1", "PSV0")):
            raise ValueError("Pixel signature chunks changed")
        payload.append((stem, binary, chunks))
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    for stem, binary, chunks in payload:
        stat_path = OUT / (stem + ".stat")
        stat_path.write_bytes(chunks["STAT"])
        original = dump(INPUT / (stem + ".dxbc"))
        stat = dump(stat_path)
        noop = typed_module(original, stat)
        outputs = {}
        for kind, module in (("noop", noop), ("red", recolor(noop))):
            encoded, warnings = compiler.operation(module.encode(), assemble=True)
            if warnings:
                raise ValueError("DXC assembly warning: " + warnings)
            signed, warnings = compiler.operation(encoded, assemble=False)
            if warnings or signed[4:20] == bytes(16):
                raise ValueError("DXC validation failed: " + warnings)
            candidate_parts = parts(signed)
            if any(chunks[key] != candidate_parts[key] for key in ("SFI0", "ISG1", "OSG1", "PSV0")):
                raise ValueError("Grid shader signature changed")
            output = OUT / (stem + "." + kind + ".dxbc")
            output.write_bytes(signed)
            reflection = dump(output)
            if kind == "red" and ("%bt.red" not in reflection or "%bt.green" not in reflection):
                raise ValueError("Red color transform not found in signed program")
            outputs[kind] = {"sha256": sha(signed), "bytes": len(signed)}
        report.append({"source_sha256": sha(binary), "source": stem, "outputs": outputs,
                       "alpha_preserved": True, "signature_chunks_unchanged": True})
    (OUT / "report.json").write_text(json.dumps({"build": "24735202",
                                                "status": "offline DXC experiment; not a material or game result",
                                                "programs": report}, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    build()
