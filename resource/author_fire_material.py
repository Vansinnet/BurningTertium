"""Put the procedural-fire pixel program into the owned, installed large red-flame material."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import material_repack as M

BASE_SHA = "d0581de73e4886a486763d7cbaf5e957512b60febfd743b774a3cd0053dc5a35"   # installed large flame
OLD_PIXEL = "751a24ec168f5455321c371faf2e79c8cfa6ddc999ef70a17f6383341ffefce0"  # red_holographic
M.LAYOUT = (100, 3432)
M.device_frames.__defaults__ = (4,)
sha = M.sha


def run(base_path, shader_dir, out_dir):
    base = Path(base_path).read_bytes()
    if sha(base) != BASE_SHA:
        raise ValueError("base drift")
    rep = json.loads((Path(shader_dir) / "report.json").read_text())
    fire = (Path(shader_dir) / "21e48952b7d5.fire.dxbc").read_bytes()
    if sha(fire) != rep["outputs"]["fire"]["sha256"]:
        raise ValueError("shader drift")
    same, f0 = M.author(base, {})
    if same != base:
        raise ValueError("no-op rebuild differs")
    cand, f1 = M.author(base, {OLD_PIXEL: fire})
    if f0 != f1 or [f["sha256"] for f in f0].count(OLD_PIXEL) != 1:
        raise ValueError("unexpected frame inventory")
    import struct
    v, mo, ms, so, ss, tail, ts = struct.unpack_from("<7I", cand)
    sh = cand[so:tail]; hd = struct.unpack_from("<12I", sh)
    after = [f["sha256"] for f in M.device_frames(sh, hd[10], hd[11])]
    want = [sha(fire) if f["sha256"] == OLD_PIXEL else f["sha256"] for f in f0]
    if after != want or cand[mo:so] != base[mo:so]:
        raise ValueError("readback mismatch")
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=False)
    (out / "fire_flame.material.candidate").write_bytes(cand)
    report = {"build": "24735202", "status": "OFFLINE MATERIAL; no game acceptance",
              "base_sha256": BASE_SHA, "replaced_pixel": {OLD_PIXEL: sha(fire)},
              "candidate_sha256": sha(cand), "candidate_bytes": len(cand),
              "frames_after": after, "large_vertex_programs_unchanged": True,
              "material_parameters_unchanged": True, "no_op_identity": True}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    base = Path(__file__).resolve().parents[1] / "analysis"
    print(json.dumps(run(base / "large-red-flame-24735202/large_red_flame.material.candidate", base / "fire-flame-shader-24735202", base / "fire-flame-material-24735202"), indent=2))
