"""Independent readback of red-holo-main-material-24735202 against the stock hologram material."""
import hashlib, json, re, struct, tempfile
from pathlib import Path
import material_repack as M
import dxc_linux as D
from author_holo_main_shader import EDITS, STOCK_SHA

BASE = Path(__file__).resolve().parents[1] / "analysis"
CAND = BASE / "red-holo-main-material-24735202/hologram.material.candidate"
STOCK = BASE / "local-red-trial-20260923T203209Z-d11ff686/hologram.original"
EXPECTED = "5d1fcc93ee8e9e951ab874ddd1298751cb6c157b528090652cfdfcd3d0850250"


def payloads(data):
    v, mo, ms, so, ss, tail, ts = struct.unpack_from("<7I", data)
    shader = data[so:tail]
    head = struct.unpack_from("<12I", shader)
    out = []
    for f in M.device_frames(shader, head[10], head[11]):
        fr = shader[f["begin"]:f["finish"]]
        out.append(fr[5:] if len(fr) - 5 == f["decoded_size"] else M.codec.decompress(fr, f["decoded_size"]))
    return out, data[mo:so], shader[head[5]:], data[tail:]


def body(dxbc):
    with tempfile.NamedTemporaryFile(suffix=".dxbc") as t:
        t.write(dxbc); t.flush()
        text = D.dump(t.name)
    return re.search(r"^define void @ps_main\(\) \{\n.*?^\}", text, re.M | re.S)[0].splitlines()


def main():
    cand, stock = CAND.read_bytes(), STOCK.read_bytes()
    assert hashlib.sha256(cand).hexdigest() == EXPECTED
    cp, cparams, cdef, ctail = payloads(cand)
    sp, sparams, sdef, stail = payloads(stock)
    changed = [i for i, (a, b) in enumerate(zip(sp, cp)) if a != b]
    assert changed == [1, 9] and len(cp) == len(sp) == 16
    assert all(hashlib.sha256(sp[i]).hexdigest() == STOCK_SHA for i in changed)
    assert cp[1] == cp[9]
    # Parameter block: only base_color (232) and material_variable_046f8451 (244) differ from stock.
    pdiff = sorted({(28 + i - 232) // 12 for i in range(len(sparams)) if sparams[i] != cparams[i]})
    vals = [struct.unpack_from("<3f", cand, off) for off in (232, 244)]
    assert pdiff == [0, 1], pdiff
    assert cdef.rstrip(b"\0") == sdef.rstrip(b"\0") and ctail == stail
    a, b = body(sp[1]), body(cp[1])
    norm = lambda line: re.sub(r"!\d+$", "!<md>", line.strip())  # typed_module renumbers control-flow hint ids
    diff = [(norm(x), norm(y)) for x, y in zip(a, b) if norm(x) != norm(y)]
    assert len(a) == len(b) and diff == list(EDITS), diff
    print(json.dumps({"candidate_sha256": EXPECTED, "changed_frames": changed,
                      "program_body_diff_vs_stock": len(diff), "shader_defaults_and_tail_unchanged": True,
                      "base_color": vals[0], "material_variable_046f8451": vals[1]}, indent=2))


if __name__ == "__main__":
    main()
