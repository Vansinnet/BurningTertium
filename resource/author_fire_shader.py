"""Replace the candle color math in pixel program 21e48952b7d5 with procedural animated fire.

Keeps every stock input load, texture/feedback path and the alpha=0 additive output; only the
RGB values passed to storeOutput change.  The math is fire_model.build(), which the numpy
preview evaluates identically.
"""
import hashlib, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import shared as S
import fire_model
from fire_dsl import emit

STOCK_SHA = "21e48952b7d5adaf8b9648d520ee1698092d994713ee786f7524674d5e29ee76"
STEM = STOCK_SHA[:12]
STORES = ["  call void @dx.op.storeOutput.f32(i32 5, i32 0, i32 0, i8 0, float %205)",
          "  call void @dx.op.storeOutput.f32(i32 5, i32 0, i32 0, i8 1, float %208)",
          "  call void @dx.op.storeOutput.f32(i32 5, i32 0, i32 0, i8 2, float %211)",
          "  call void @dx.op.storeOutput.f32(i32 5, i32 0, i32 0, i8 3, float 0.000000e+00)"]
INPUTS = {"u": "%4", "h": "%5", "c1x": "%7", "c1y": "%8", "alpha": "%9", "time": "%77"}
ANCHORS = ["  %4 = call float @dx.op.loadInput.f32(i32 4, i32 6, i32 0, i8 0, i32 undef)",
           "  %5 = call float @dx.op.loadInput.f32(i32 4, i32 6, i32 0, i8 1, i32 undef)",
           "  %7 = call float @dx.op.loadInput.f32(i32 4, i32 4, i32 0, i8 0, i32 undef)",
           "  %8 = call float @dx.op.loadInput.f32(i32 4, i32 4, i32 0, i8 1, i32 undef)",
           "  %9 = call float @dx.op.loadInput.f32(i32 4, i32 3, i32 0, i8 3, i32 undef)",
           "  %77 = extractvalue %dx.types.CBufRet.f32 %76, 0",
           "  %76 = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle %3, i32 90)"]


def sha(b): return hashlib.sha256(b).hexdigest()
def parts(b): return {r["tag"]: b[r["offset"] + 8:r["offset"] + 8 + r["size"]] for r in S.dxbc(b)}


def fire(module):
    body = re.search(r"^define void @ps_main\(\) \{\n.*?^\}", module, re.M | re.S)
    text = re.sub(r"(?m)^(  [^;\n]*?\S)  +; [A-Za-z]+\(.*$", r"\1", body[0])  # drop DXC op comments
    for line in STORES + ANCHORS:
        if text.count(line + "\n") != 1:
            raise ValueError("stock contract changed: " + line)
    if text.count("@dx.op.storeOutput.f32(") != 4:
        raise ValueError("unexpected outputs")
    lines, out = emit(fire_model.build(), INPUTS)
    new = text.replace(STORES[0] + "\n", "\n".join(lines) + "\n" + STORES[0].replace("%205)", out["r"] + ")") + "\n")
    new = new.replace(STORES[1] + "\n", STORES[1].replace("%208)", out["g"] + ")") + "\n")
    new = new.replace(STORES[2] + "\n", STORES[2].replace("%211)", out["b"] + ")") + "\n")
    result = module[:body.start()] + new + module[body.end():]
    if "@dx.op.binary.f32(i32" in new and "declare float @dx.op.binary.f32(" not in result:
        result += "\ndeclare float @dx.op.binary.f32(i32, float, float) #0\n"
    return result, len(lines)


def build(source, out_dir, dxc, dump):
    binary = Path(source).read_bytes()
    if sha(binary) != STOCK_SHA:
        raise ValueError("stock drift")
    chunks = parts(binary)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=False)
    (out / (STEM + ".stat")).write_bytes(chunks["STAT"])
    noop = S.typed_module(dump(source), dump(out / (STEM + ".stat")))
    fired, count = fire(noop)
    (out / (STEM + ".fire.ll")).write_text(fired)
    res = {}
    for kind, module in (("noop", noop), ("fire", fired)):
        enc, w = dxc.operation(module.encode(), assemble=True)
        if w: raise ValueError("assembly warning " + w)
        signed, w = dxc.operation(enc, assemble=False)
        if w or signed[4:20] == bytes(16): raise ValueError("validation " + w)
        cp = parts(signed)
        changed = [k for k in ("SFI0", "ISG1", "OSG1", "PSV0") if chunks[k] != cp[k]]
        if changed: raise ValueError("signature chunks changed: %r" % changed)
        (out / (STEM + "." + kind + ".dxbc")).write_bytes(signed)
        res[kind] = {"sha256": sha(signed), "bytes": len(signed)}
    report = {"build": "24735202", "status": "offline DXC program; no game acceptance",
              "stock_sha256": STOCK_SHA, "outputs": res, "added_instructions": count,
              "alpha_output_unchanged": True, "signature_chunks_unchanged": True}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    import dxc_linux as D
    base = Path(__file__).resolve().parents[1] / "analysis"
    print(json.dumps(build(base / "candle-shaders-24735202/21e48952b7d5.dxbc", base / "fire-flame-shader-24735202", D.Dxc(), D.dump), indent=2))
