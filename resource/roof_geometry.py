"""Read the pinned hologram's mesh geometry for offline roof placement.

Structural lead: stingray_reverse_engineering hexpats/dt_unit.hexpat and
includes/stingray_shared.hexpat. Accepted fields are checked against target
counts, bounds, material hashes and indexed vertex extents below.
"""

import hashlib
import json
import math
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "analysis/stock-hub-hologram-24735202/mission_table_hologram.unit.record"
SHA = "e8278669c76a6d192865fbed5a31663bd7fb82ce776e52912887d7e8a1bf6383"


class Cursor:
    def __init__(self, data):
        self.data = data
        self.at = 0

    def take(self, size):
        if size < 0 or self.at + size > len(self.data):
            raise ValueError(f"Geometry bounds at {self.at}, need {size}")
        out = self.data[self.at:self.at + size]
        self.at += size
        return out

    def unpack(self, fmt):
        return struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))

    def count(self, maximum=1000000):
        value, = self.unpack("I")
        if value > maximum:
            raise ValueError(f"Unexpected count {value} at {self.at - 4}")
        return value

    def blob(self):
        return self.take(self.count(16000000))


def load():
    raw = UNIT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA:
        raise ValueError("Hologram unit provenance changed")
    body_size = struct.unpack_from("<I", raw, 29)[0]
    c = Cursor(raw[38:38 + body_size])
    version, = c.unpack("I")
    meshes = []
    for i in range(c.count(128)):
        start = c.at
        mesh_version, = c.unpack("I")
        if mesh_version != 1:
            raise ValueError(f"Unknown mesh version {mesh_version} at {start}")
        streams = []
        for _ in range(c.count(16)):
            blob = c.blob()
            validity, stream_type, count, stride = c.unpack("4I")
            if validity > 2 or stream_type > 1 or stride > 256 or count > 1000000:
                raise ValueError("Unexpected vertex stream descriptor")
            if blob and len(blob) != count * stride:
                raise ValueError("Vertex stream bytes disagree with count/stride")
            streams.append(dict(data=blob, count=count, stride=stride))
        channels = [c.unpack("4IB") for _ in range(c.count(32))]
        validity, stream_type, index_format, index_count = c.unpack("4I")
        indices = c.blob()
        if index_format not in (0, 1) or len(indices) not in (0, index_count * (2 if index_format == 0 else 4)):
            raise ValueError("Unexpected index stream extent")
        batches = [c.unpack("4I") for _ in range(c.count(128))]
        bounds = c.unpack("10f")
        if not all(math.isfinite(f) for f in bounds):
            raise ValueError("Non-finite mesh bounds")
        materials = [c.unpack("I")[0] for _ in range(c.count(128))]
        extra, = c.unpack("I")
        meshes.append(dict(index=i, start=start, end=c.at, streams=streams,
                           channels=channels, index_format=index_format,
                           index_count=index_count, indices=indices, batches=batches,
                           bounds=bounds, materials=materials, extra=extra))
    skins = c.count(64)
    for _ in range(skins):
        c.take(c.count(1024) * 64)
        c.take(c.count(1024) * 4)
        for _ in range(c.count(1024)):
            c.take(c.count(1024) * 4)
    animation = c.blob()
    for _ in range(c.count(128)):
        c.take(4)
        c.take(c.count(1024) * 4)
    node_count = c.count(128)
    nodes = [c.unpack("15f") for _ in range(node_count)]
    transforms = [c.unpack("16f") for _ in range(node_count)]
    parents = [c.unpack("HH") for _ in range(node_count)]
    names = [c.unpack("I")[0] for _ in range(node_count)]
    c.take(c.count(1024) * 8)
    objects = []
    for _ in range(c.count(128)):
        fields = c.unpack("7I")
        bounds = c.unpack("10f")
        extra, = c.unpack("I")
        objects.append(dict(fields=fields, bounds=bounds, extra=extra))
    scene = dict(nodes=nodes, transforms=transforms, parents=parents, names=names,
                 objects=objects, end=c.at, skins=skins, animation_bytes=len(animation))
    return version, meshes, scene


if __name__ == "__main__":
    version, meshes, scene = load()
    print(json.dumps({"unit_version": version, "geometries": [
        {**{k: m[k] for k in ("index", "start", "end", "channels", "batches", "bounds", "materials", "extra", "index_count")},
         "streams": [{"bytes": len(s["data"]), "count": s["count"], "stride": s["stride"]} for s in m["streams"]]}
        for m in meshes], "scene": scene}, indent=2))
