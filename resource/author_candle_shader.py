"""Build an offline, red scanlined candle flame pixel shader without touching stock."""

import hashlib
import json
from pathlib import Path
import re

from author_grid_shader import BoundedDxc, dump, parts, typed_module


BASE = Path(__file__).resolve().parents[1] / "analysis"
INPUT = BASE / "candle-shaders-24735202"
OUT = BASE / "red-candle-shader-24735202"
SOURCE_SHA = "21e48952b7d5adaf8b9648d520ee1698092d994713ee786f7524674d5e29ee76"
STEM = SOURCE_SHA[:12]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def red_holographic_flame(module):
    body = re.search(r"^define void @ps_main\(\) \{\n.*?^\}", module, re.M | re.S)
    if not body:
        raise ValueError("Candle color function missing")
    expected = [
        "  call void @dx.op.storeOutput.f32(i32 5, i32 0, i32 0, i8 0, float %205)",
        "  call void @dx.op.storeOutput.f32(i32 5, i32 0, i32 0, i8 1, float %208)",
        "  call void @dx.op.storeOutput.f32(i32 5, i32 0, i32 0, i8 2, float %211)",
        "  call void @dx.op.storeOutput.f32(i32 5, i32 0, i32 0, i8 3, float 0.000000e+00)",
    ]
    if any(body[0].count(line) != 1 for line in expected) or \
       body[0].count("@dx.op.storeOutput.f32(") != 4 or \
       body[0].count("  %77 = extractvalue %dx.types.CBufRet.f32 %76, 0") != 1:
        raise ValueError("Unexpected stock candle output/time contract")
    # Stock time and flame UVs animate subtle horizontal scanlines inside the
    # existing alpha/shape; this does not add a mesh or alter the particle graph.
    code = ("  %bt.maxrg = call float @dx.op.binary.f32(i32 35, float %205, float %208)\n"
            "  %bt.value = call float @dx.op.binary.f32(i32 35, float %bt.maxrg, float %211)\n"
            "  %bt.uv = fmul float %8, 6.400000e+01\n"
            "  %bt.time = fmul float %77, 1.200000e+01\n"
            "  %bt.phase = fadd float %bt.uv, %bt.time\n"
            "  %bt.wave = call float @dx.op.unary.f32(i32 13, float %bt.phase)\n"
            "  %bt.scan = fmul float %bt.wave, 0x3FC99999A0000000\n"
            "  %bt.gain = fadd float 0x3FE6666660000000, %bt.scan\n"
            "  %bt.red = fmul float %bt.value, %bt.gain\n"
            "  %bt.green = fmul float %bt.red, 0x3F999999A0000000\n"
            "  %bt.blue = fmul float %bt.red, 0x3F847AE140000000\n")
    # 0.2, 0.7, 0.025 and 0.01 are the float32-exact literals above.
    altered = body[0].replace(expected[0], code + expected[0].replace("float %205)", "float %bt.red)"))
    altered = altered.replace(expected[1], expected[1].replace("float %208)", "float %bt.green)"))
    altered = altered.replace(expected[2], expected[2].replace("float %211)", "float %bt.blue)"))
    if altered.count(expected[3]) != 1 or altered.count("%bt.red)") != 1:
        raise ValueError("Candle alpha or RGB replacement failed")
    result = module[:body.start()] + altered + module[body.end():]
    if "declare float @dx.op.binary.f32(" not in result:
        result += "\ndeclare float @dx.op.binary.f32(i32, float, float) #0\n"
    return result


def main():
    if OUT.exists():
        raise ValueError("Candidate output already exists")
    info = json.loads((INPUT / "provenance.json").read_text())
    if not any(row["sha256"] == SOURCE_SHA and row["has_color_target"] for row in info["unique_pixel"]):
        raise ValueError("No pinned candle color source")
    source = (INPUT / (STEM + ".dxbc")).read_bytes()
    if sha(source) != SOURCE_SHA:
        raise ValueError("Candle source shader drift")
    chunks = parts(source)
    if not all(k in chunks for k in ("STAT", "DXIL", "SFI0", "ISG1", "OSG1", "PSV0")):
        raise ValueError("Missing shader signature chunks")
    compiler = BoundedDxc()
    OUT.mkdir(parents=True)
    stat_path = OUT / (STEM + ".stat")
    stat_path.write_bytes(chunks["STAT"])
    stock_module = typed_module(dump(INPUT / (STEM + ".dxbc")), dump(stat_path))
    results = {}
    for kind, module in (("noop", stock_module), ("red_holographic", red_holographic_flame(stock_module))):
        assembled, warning = compiler.operation(module.encode(), assemble=True)
        if warning:
            raise ValueError("DXC assembly warning: " + warning)
        signed, warning = compiler.operation(assembled, assemble=False)
        if warning or signed[4:20] == bytes(16):
            raise ValueError("DXC signed validation failed: " + warning)
        produced = parts(signed)
        if any(chunks[tag] != produced[tag] for tag in ("SFI0", "ISG1", "OSG1", "PSV0")):
            raise ValueError("Candle shader signature changed")
        filename = STEM + "." + kind + ".dxbc"
        output = OUT / filename
        output.write_bytes(signed)
        text = dump(output)
        if kind == "red_holographic" and ("%bt.red" not in text or "%bt.scan" not in text):
            raise ValueError("Signed flame program omitted red/scanline transform")
        results[kind] = {"file": filename, "sha256": sha(signed), "bytes": len(signed)}
    report = {"build": "24735202", "status": "offline DXC candidate; not yet an effect/game result",
              "stock_shader_sha256": SOURCE_SHA, "outputs": results,
              "preserved_alpha_and_signature": True}
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
