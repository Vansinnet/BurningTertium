"""Disassemble only color pixel programs of the source-identified hub candle effect."""

import hashlib
import argparse
import json
from pathlib import Path
import subprocess

from inspect_hologram_shaders import DXC, DXC_SHA, shader_programs


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "analysis/stock-hub-candle-material-24735202/provenance.json"
OUT = ROOT / "analysis/candle-shaders-24735202"
EXPECTED = "90ff8d9836fcad0ecddc9785122a399ddb7a8dec1e7b63dc88a940459ec4f998"


def main(vertex=False):
    global OUT
    if vertex:
        OUT = ROOT / "analysis/candle-vertex-24735202"
    if OUT.exists():
        raise ValueError("Candle shader output exists")
    info = json.loads(INPUT.read_text())
    if info["stream_sha256"] != EXPECTED:
        raise ValueError("Pinned candle material differs")
    source = Path(info["stream"]).read_bytes()
    if hashlib.sha256(source).hexdigest() != EXPECTED:
        raise ValueError("Installed candle material differs")
    with DXC.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != DXC_SHA:
            raise ValueError("DXC tool identity changed")
    unique = {}
    programs = shader_programs(source)
    for stage, program in programs:
        if stage == (1 if vertex else 0):
            unique[hashlib.sha256(program).hexdigest()] = program
    if not 0 < len(unique) <= 12:
        raise ValueError("Unexpected candle pixel program count")
    OUT.mkdir(parents=True)
    descriptions = []
    for digest, binary in unique.items():
        stem = digest[:12]
        path = OUT / (stem + ".dxbc")
        path.write_bytes(binary)
        result = subprocess.run([str(DXC), "-dumpbin", str(path)], capture_output=True,
                                timeout=25, check=True)
        if not 0 < len(result.stdout) < 700_000:
            raise ValueError("DXC candle disassembly size")
        (OUT / (stem + ".ll.txt")).write_bytes(result.stdout)
        descriptions.append({"sha256": digest, "bytes": len(binary),
                             "has_color_target": b"SV_Target" in result.stdout,
                             "has_material_buffer": b"c_material_exports" in result.stdout})
    report = {"build": "24735202", "material_source_sha256": EXPECTED,
              "programs": len(programs), "unique_pixel": descriptions}
    (OUT / "provenance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--vertex", action="store_true")
    main(cli.parse_args().vertex)
