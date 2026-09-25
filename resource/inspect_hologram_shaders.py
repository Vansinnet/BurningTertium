"""Decode only unique pixel programs of the pinned city and grid materials."""

import hashlib
import argparse
import importlib
import json
from pathlib import Path
import struct
import subprocess
import sys

from inspect_hologram import murmur64


ROOT = Path(__file__).resolve().parents[4]
INPUT = Path(__file__).resolve().parents[1] / "analysis" / "stock-hub-hologram-24735202"
OUT_DIR = Path(__file__).resolve().parents[1] / "analysis"
sys.path.insert(0, str(ROOT / "docs/analysis-flame-shader43-20260918-j1"))
codec = importlib.import_module("decode")
DXC = Path(r"C:\Users\junge\AppData\Local\Temp\opencode\flame-shader43-20260918-j1-dxc\dxc.exe")
DXC_SHA = "980a3a4c6e5c88f5737dde321e548860021d58fa2349790d4e572805cb298293"
EXPECTED = {"hologram": "e0d63444385473b9b4e299318cd3fdc85e2188f9df9da06ab2224a41654cb616",
            "hologram_grid": "c49cba30643a8c863c2818df51bbf5f761f7dc0cd32c4912b3d51d037e655db4",
            "hologram_side": "28a94fa9b2a988d8dd93925c40e4687091b6e766f57d1c283eab9fddbaa03a03",
            "hologram_bottom": "078ed294f4bab50fa984a035d9c94da4e5521da858c148cc52316f5fcfe448e8"}


def shader_programs(data):
    _, mo, ms, so, ss, tail, ts = struct.unpack_from("<7I", data)
    if so != mo + ms or so + ss > len(data):
        raise ValueError("Material section bounds")
    shader = data[so:so + ss]
    head = struct.unpack_from("<12I", shader)
    start, size = head[10:12]
    stop = start + size
    if head[0] != 43 or not 48 <= start < stop <= head[5] <= len(shader):
        raise ValueError("Shader device bounds")
    found = []
    position = start
    while (at := shader.find(b"\x8c\x06", position, stop)) != -1:
        position = at + 2
        if at < start + 8 or at + 5 > stop:
            continue
        envelope, length = struct.unpack_from("<II", shader, at - 8)
        end = at + length
        if envelope != 1 or not at + 8 <= end <= stop - 16:
            continue
        frame = shader[at:end]
        if int.from_bytes(frame[2:5], "big") + 1 != len(frame) - 5:
            continue
        kind, decoded_size, key = struct.unpack_from("<IIQ", shader, end)
        if kind != 5 or not 32 <= decoded_size <= 262144 or murmur64(frame) != key:
            continue
        program = codec.decompress(frame, decoded_size)
        chunks = codec.dxbc(program)
        stages = [struct.unpack_from("<I", program, chunk["offset"] + 8)[0] >> 16
                  for chunk in chunks if chunk["tag"] == "DXIL"]
        if len(stages) != 1:
            raise ValueError("DXIL program stage")
        found.append((stages[0], program))
        position = end
    if not found or len(found) > 128:
        raise ValueError("Unexpected hologram shader frame count")
    return found


def main(vertex, bottom):
    out = OUT_DIR / ("hologram-vertex-24735202" if vertex else
                     "hologram-bottom-pixels-24735202" if bottom else "hologram-shaders-24735202")
    if out.exists():
        raise ValueError("Research output already exists")
    with DXC.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != DXC_SHA:
            raise ValueError("DXC provenance mismatch")
    manifest = json.loads((INPUT / "provenance.json").read_text())
    red_trial = json.loads((OUT_DIR / "red-material-trial-24735202/report.json").read_text()) if bottom else None
    pixels = {}
    report = []
    for item in manifest["resources"]:
        label = item["name"].rsplit("/", 1)[-1]
        if label not in EXPECTED or (not vertex and label not in
                                      (("hologram_bottom", "hologram_side") if bottom else
                                       ("hologram", "hologram_grid"))):
            continue
        stream = item["installed_streams"][0]
        if stream["sha256"] != EXPECTED[label]:
            raise ValueError("Pinned source changed")
        if bottom and red_trial is not None:
            trial = next(row for row in red_trial["materials"] if row["name"].endswith("/" + label))
            if trial["source_sha256"] != stream["sha256"] or not red_trial["material_shader_programs_unchanged"]:
                raise ValueError("Bottom shader does not have pinned source provenance")
            data = (OUT_DIR / "red-material-trial-24735202" / trial["output"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != trial["output_sha256"]:
                raise ValueError("Local bottom candidate drift")
        else:
            data = Path(stream["path"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != stream["sha256"]:
                raise ValueError("Source file changed since extraction")
        programs = shader_programs(data)
        unique = {}
        for stage, program in programs:
            if stage == (1 if vertex else 0):
                key = hashlib.sha256(program).hexdigest()
                unique[key] = program
                pixels.setdefault(key, (label, program))
        report.append({"material": label, "programs": len(programs),
                       "unique_program_sha256": sorted(unique)})
    if len(report) != (4 if vertex else 2) or not 0 < len(pixels) <= 64:
        raise ValueError("Unexpected pixel shader inventory")
    out.mkdir(parents=True)
    for digest, (label, binary) in pixels.items():
        binary_path = out / (digest[:12] + ".dxbc")
        binary_path.write_bytes(binary)
        result = subprocess.run([str(DXC), "-dumpbin", str(binary_path)], capture_output=True,
                                timeout=25, check=True)
        if not 0 < len(result.stdout) < 2_000_000:
            raise ValueError("Unexpected DXC disassembly size")
        (out / (digest[:12] + ".ll.txt")).write_bytes(result.stdout)
    (out / "provenance.json").write_text(json.dumps({"build": "24735202", "dxc_sha256": DXC_SHA,
                                                       "sources": report}, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--vertex", action="store_true")
    cli.add_argument("--bottom", action="store_true")
    args = cli.parse_args()
    main(args.vertex, args.bottom)
