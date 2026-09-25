"""Build the hub city `hologram` material with the red-mirrored pixel program in frames 1 and 9."""
import hashlib, json, struct, sys
from pathlib import Path
import material_repack as M

INSTALLED_RED_BASE = "4ceb5cf6f7326d14019578326d02d7c354cd56c9ae6b65321521e0a1e2dcc003"
STOCK = "e0d63444385473b9b4e299318cd3fdc85e2188f9df9da06ab2224a41654cb616"
TARGET = "1d465925213ce322ec75a7e1bff56aa66e7c66f03a27c6caa408bdd41e28c64f"
sha = M.sha


def run(base_path, stock_path, shader_dir, out_dir):
    base, stock = Path(base_path).read_bytes(), Path(stock_path).read_bytes()
    if sha(base) != INSTALLED_RED_BASE or sha(stock) != STOCK:
        raise ValueError("input drift")
    rep = json.loads((Path(shader_dir) / "report.json").read_text())
    red = (Path(shader_dir) / "1d465925213c.red.dxbc").read_bytes()
    if sha(red) != rep["outputs"]["red"]["sha256"] or rep["source_sha256"] != TARGET:
        raise ValueError("shader drift")
    # Only the four vector3 bytes at 232..255 may differ between stock and installed base.
    diff = [i for i in range(len(stock)) if stock[i] != base[i]]
    if len(base) != len(stock) or not diff or min(diff) < 232 or max(diff) > 255:
        raise ValueError("base is not stock plus color parameters")
    same, frames0 = M.author(base, {})
    assert same == base
    cand, frames1 = M.author(base, {TARGET: red})
    if frames0 != frames1:
        raise ValueError("frame traversal changed")
    hits = [i for i, f in enumerate(frames0) if f["sha256"] == TARGET]
    if hits != [1, 9]:
        raise ValueError("unexpected target frames %r" % hits)
    v, mo, ms, so, ss, tail, ts = struct.unpack_from("<7I", cand)
    sh = cand[so:tail]; h = struct.unpack_from("<12I", sh)
    after = M.device_frames(sh, h[10], h[11])
    for i, (a, b) in enumerate(zip(frames0, after)):
        want = sha(red) if i in hits else a["sha256"]
        if b["sha256"] != want:
            raise ValueError("readback frame %d" % i)
    if cand[:232][28:] != base[:232][28:] or cand[232:256] != base[232:256]:
        raise ValueError("material parameter block changed")
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=False)
    (out / "hologram.material.candidate").write_bytes(cand)
    report = {"build": "24735202", "status": "OFFLINE MATERIAL; no game acceptance",
              "base": "installed red-parameter trial", "base_sha256": INSTALLED_RED_BASE,
              "stock_sha256": STOCK, "candidate_sha256": sha(cand), "candidate_bytes": len(cand),
              "replaced_frames": hits, "pixel_replacement": {TARGET: sha(red)},
              "no_op_identity": True, "other_frames_unchanged": True,
              "color_parameters_unchanged_from_base": True}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


BASE = Path(__file__).resolve().parents[1] / "analysis"

if __name__ == "__main__":
    print(json.dumps(run(BASE / "red-material-trial-24735202/hologram.material.candidate",
                         BASE / "local-red-trial-20260923T203209Z-d11ff686/hologram.original",
                         BASE / "red-holo-main-shader-24735202",
                         BASE / "red-holo-main-material-24735202"), indent=2))
