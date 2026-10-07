"""Inspect only the hologram unit's exact external mesh stream."""

import hashlib
import json
from pathlib import Path

from roof_geometry import Cursor, load, ROOT

GAME = Path(r"D:\Steam\steamapps\common\Warhammer 40,000 DARKTIDE")
PATH = GAME / "bundle/data/0e/0ec28850be53166b.stream"


def read():
    workspace = ROOT.parents[2]
    managed = json.loads((workspace / "mods/active/RainbowFlame/payload/manifest.json").read_text())
    vortex = json.loads((GAME / "vortex.deployment.json").read_text())
    relative = PATH.relative_to(GAME).as_posix().lower()
    if relative in {r["target"].lower() for r in managed["files"]} or relative in {
            r["relPath"].replace("\\", "/").lower() for r in vortex["files"]} or PATH.is_symlink():
        raise ValueError("Hologram stream is mod-managed")
    data = PATH.read_bytes()
    if not 0 < len(data) < 20000000:
        raise ValueError("Unexpected mesh stream extent")
    c = Cursor(data)
    if hashlib.sha256(data).hexdigest() != "68d82d0d753c52d27089a4277f541b22e4a95d1fbc55141f9937032bba6e644b":
        raise ValueError("Identified stock-candidate stream has changed")
    version, meshes, scene = load()
    result = []
    for index in (1, 2):
        begin = c.at
        tag, = c.unpack("I")
        if tag != len(meshes[index]["streams"]):
            raise ValueError("Stream count differs from unit geometry")
        streams = [c.blob() for _ in meshes[index]["streams"]]
        indices = c.blob()
        for actual, descriptor in zip(streams, meshes[index]["streams"]):
            if len(actual) != descriptor["count"] * descriptor["stride"]:
                raise ValueError("External vertex data disagrees with unit counts")
        if len(indices) != meshes[index]["index_count"] * (2 if meshes[index]["index_format"] == 0 else 4):
            raise ValueError("External index count disagrees with unit")
        result.append(dict(index=index, tag=tag, begin=begin, end=c.at,
                           streams=streams, indices=indices))
    if c.at != len(data):
        raise ValueError("Unconsumed external mesh data")
    return data, result, c.at


if __name__ == "__main__":
    data, records, end = read()
    print(json.dumps({"path": str(PATH), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                      "records": [{"index": r["index"], "tag": r["tag"], "begin": r["begin"], "end": r["end"],
                                   "stream_sizes": [len(s) for s in r["streams"]], "index_bytes": len(r["indices"])}
                                  for r in records], "unconsumed": len(data)-end}, indent=2))
