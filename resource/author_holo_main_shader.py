"""Red-channel mirror of the hub city's hardcoded green constants in pixel program 1d465925213c.

Stock `hologram` pixel program (frames 1 and 9 of the material) contains two
hardcoded green terms that no material variable controls:
  * bottom gradient: lerp((0.1, 0.4, 0.1), scan * base_color, saturate((CUSTOM0.z*11)^0.3))
  * fake light:      rgb *= (0.16, 0.72, 0.32) * max(dot(N, L), 0) + (0.08, 0.36, 0.16)
This swaps only the red and green operands of those eight instructions.
Blue, alpha, scanline, fog and every other instruction stay byte-identical in text.
"""
import hashlib, json, sys
from pathlib import Path
import shared as S

STEM = "1d465925213c"
STOCK_SHA = "1d465925213ce322ec75a7e1bff56aa66e7c66f03a27c6caa408bdd41e28c64f"
F = {"0.1": "0x3FB99999A0000000", "-0.1": "0xBFB99999A0000000", "0.4": "0x3FD99999A0000000",
     "-0.4": "0xBFD99999A0000000", "0.16": "0x3FC47AE160000000", "0.72": "0x3FE70A3D60000000",
     "0.08": "0x3FB47AE160000000", "0.36": "0x3FD70A3D60000000"}
EDITS = [  # (stock instruction, replacement) — R and G operands swapped
    ("%167 = fadd fast float %159, " + F["-0.1"], "%167 = fadd fast float %159, " + F["-0.4"]),
    ("%168 = fadd fast float %160, " + F["-0.4"], "%168 = fadd fast float %160, " + F["-0.1"]),
    ("%173 = fadd fast float %170, " + F["0.1"], "%173 = fadd fast float %170, " + F["0.4"]),
    ("%174 = fadd fast float %171, " + F["0.4"], "%174 = fadd fast float %171, " + F["0.1"]),
    ("%230 = fmul fast float %229, " + F["0.16"], "%230 = fmul fast float %229, " + F["0.72"]),
    ("%231 = fmul fast float %229, " + F["0.72"], "%231 = fmul fast float %229, " + F["0.16"]),
    ("%233 = fadd fast float %230, " + F["0.08"], "%233 = fadd fast float %230, " + F["0.36"]),
    ("%234 = fadd fast float %231, " + F["0.36"], "%234 = fadd fast float %231, " + F["0.08"]),
]
UNCHANGED_BLUE = ["%169 = fadd fast float %161, " + F["-0.1"], "%175 = fadd fast float %172, " + F["0.1"],
                  "%232 = fmul fast float %229, 0x3FD47AE160000000", "%235 = fadd fast float %232, " + F["0.16"]]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def parts(b):
    return {r["tag"]: b[r["offset"] + 8:r["offset"] + 8 + r["size"]] for r in S.dxbc(b)}


def recolor(module):
    for line in UNCHANGED_BLUE:
        if module.count("  " + line + "\n") != 1:
            raise ValueError("Blue-channel anchor changed: " + line)
    for old, new in EDITS:
        if module.count("  " + old + "\n") != 1:
            raise ValueError("Stock instruction not found exactly once: " + old)
        module = module.replace("  " + old + "\n", "  " + new + "\n")
    return module


def build(source_dxbc, out_dir, dxc, dump):
    binary = Path(source_dxbc).read_bytes()
    if sha(binary) != STOCK_SHA:
        raise ValueError("Unexpected stock program")
    chunks = parts(binary)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    (out / (STEM + ".stat")).write_bytes(chunks["STAT"])
    noop = S.typed_module(dump(source_dxbc), dump(out / (STEM + ".stat")))
    results = {}
    for kind, module in (("noop", noop), ("red", recolor(noop))):
        encoded, warn = dxc.operation(module.encode(), assemble=True)
        if warn:
            raise ValueError("assembly warning " + warn)
        signed, warn = dxc.operation(encoded, assemble=False)
        if warn or signed[4:20] == bytes(16):
            raise ValueError("validation failed " + warn)
        cand = parts(signed)
        if any(chunks[k] != cand[k] for k in ("SFI0", "ISG1", "OSG1", "PSV0")):
            raise ValueError("signature chunks changed")
        path = out / (STEM + "." + kind + ".dxbc")
        path.write_bytes(signed)
        results[kind] = {"sha256": sha(signed), "bytes": len(signed)}
    # Readback: the only disassembly differences are the eight intended instructions.
    a = [l for l in dump(out / (STEM + ".noop.dxbc")).splitlines()]
    b = [l for l in dump(out / (STEM + ".red.dxbc")).splitlines()]
    if len(a) != len(b):
        raise ValueError("instruction count changed")
    diff = [(x.strip(), y.strip()) for x, y in zip(a, b) if x != y and not x.startswith("; shader hash")]
    expected = [(o, n) for o, n in EDITS]
    if diff != expected:
        raise ValueError("unexpected readback diff: " + json.dumps(diff, indent=1))
    report = {"build": "24735202", "status": "offline DXC program; no game acceptance",
              "source_sha256": STOCK_SHA, "outputs": results,
              "edits": [{"old": o, "new": n} for o, n in EDITS],
              "signature_chunks_unchanged": True, "alpha_scanline_fog_unchanged": True}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


BASE = Path(__file__).resolve().parents[1] / "analysis"
SOURCE = BASE / "hologram-shaders-24735202" / (STEM + ".dxbc")
OUT = BASE / "red-holo-main-shader-24735202"

if __name__ == "__main__":
    import dxc_linux as D
    print(json.dumps(build(SOURCE, OUT, D.Dxc(), D.dump), indent=2))
