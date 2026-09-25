"""Sample visible upward building surfaces from the pinned highest-detail mesh."""

import hashlib
import json
import math
from pathlib import Path
import struct

from roof_geometry import ROOT, load
from roof_stream import read, PATH


def geometry():
    _, meshes, scene = load()
    raw, streams, _ = read()
    mesh = meshes[1]
    stream = streams[0]
    if mesh["materials"] != [0x9E40CFD9] or mesh["channels"][1] != (0, 17, 0, 1, 0):
        raise ValueError("Highest-detail building material/position channel changed")
    identity = (1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.)
    if any(tuple(tm) != identity for tm in scene["transforms"]):
        raise ValueError("Non-identity mesh-node transform requires tracing")
    vertices = [p[:3] for p in struct.iter_unpack("<4e", stream["streams"][1])]
    indices = [v[0] for v in struct.iter_unpack("<I", stream["indices"])]
    if len(vertices) != 123843 or len(indices) != 200112 or max(indices) >= len(vertices):
        raise ValueError("Vertex/index bounds disagree")
    for axis in range(3):
        low, high = min(p[axis] for p in vertices), max(p[axis] for p in vertices)
        if abs(low - mesh["bounds"][axis]) > .005 or abs(high - mesh["bounds"][axis+3]) > .005:
            raise ValueError("Decoded HALF4 positions disagree with independent mesh bounds")
    world_file = ROOT / "analysis/stock-mourningstar-24735202/mourningstar.level.record"
    world = world_file.read_bytes()
    if hashlib.sha256(world).hexdigest() != "9b89b1ba12ca8baa6750425d606e64bb005030d12a4b047abe4d5d1195d74cd9":
        raise ValueError("Level provenance changed")
    if struct.unpack_from("<Q", world, 584214)[0] != 0x7A28B78397F3E9C1:
        raise ValueError("Hologram placement identity changed")
    position = struct.unpack_from("<3f", world, 584230)
    q = struct.unpack_from("<4f", world, 584242)
    scale = struct.unpack_from("<3f", world, 584258)
    if max(abs(a-b) for a,b in zip(position,(-.0008,-155.5007,101.56))) > .001 or scale != (2.,2.,1.5):
        raise ValueError("Unexpected level placement")
    if abs(sum(v*v for v in q)-1) > .0001:
        raise ValueError("Invalid placement quaternion")
    x,y,z,w = q
    def transform(p):
        a,b,c = (p[i]*scale[i] for i in range(3))
        tx,ty,tz = 2*(y*c-z*b), 2*(z*a-x*c), 2*(x*b-y*a)
        return (position[0]+a+w*tx+y*tz-z*ty,
                position[1]+b+w*ty+z*tx-x*tz,
                position[2]+c+w*tz+x*ty-y*tx)
    vertices = [transform(p) for p in vertices]
    triangles = []
    for i in range(0, len(indices), 3):
        a,b,c = (vertices[indices[i+j]] for j in range(3))
        ux,uy,uz = (b[j]-a[j] for j in range(3))
        vx,vy,vz = (c[j]-a[j] for j in range(3))
        nx,ny,nz = uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx
        length = math.sqrt(nx*nx+ny*ny+nz*nz)
        if abs(nz) > 1e-10 and length > 1e-10:
            triangles.append((a,b,c,abs(nz)/length,i//3))
    return triangles, position, scale, q, vertices


def sample():
    triangles, position, scale, rotation, vertices = geometry()
    bins = {}
    for triangle in triangles:
        a,b,c,normal,index = triangle
        lowx,highx = min(a[0],b[0],c[0]),max(a[0],b[0],c[0])
        lowy,highy = min(a[1],b[1],c[1]),max(a[1],b[1],c[1])
        for ix in range(math.floor(lowx*2), math.floor(highx*2)+1):
            for iy in range(math.floor(lowy*2), math.floor(highy*2)+1):
                bins.setdefault((ix,iy),[]).append(triangle)
    candidates = []
    for ix in range(-20,21):
        for iy in range(-20,21):
            x = position[0]+ix*.27+.037
            y = position[1]+iy*.27+.019
            highest = None
            for a,b,c,normal,index in bins.get((math.floor(x*2),math.floor(y*2)),[]):
                ux,uy = b[0]-a[0],b[1]-a[1]
                vx,vy = c[0]-a[0],c[1]-a[1]
                d = ux*vy-uy*vx
                px,py = x-a[0],y-a[1]
                s,t = (px*vy-py*vx)/d,(ux*py-uy*px)/d
                if s < .001 or t < .001 or s+t > .999:
                    continue
                z = a[2]+s*(b[2]-a[2])+t*(c[2]-a[2])
                if highest is None or z > highest[2]:
                    highest = (x,y,z,normal,index,s,t)
            if highest and highest[3] >= .8 and highest[2] > position[2]+.2:
                candidates.append(highest)
    if len(candidates) < 180:
        raise ValueError(f"Insufficient verified roof candidates: {len(candidates)}")
    # Farthest-point selection spreads coverage in XY and across tower heights.
    selected = [max(candidates,key=lambda p:p[2])]
    remaining = [p for p in candidates if p != selected[0]]
    def distance(a,b):
        return (a[0]-b[0])**2+(a[1]-b[1])**2+.5*(a[2]-b[2])**2
    distances = [distance(p,selected[0]) for p in remaining]
    while len(selected)<180:
        best = max(range(len(remaining)),key=lambda i:distances[i])
        point = remaining.pop(best)
        distances.pop(best)
        selected.append(point)
        distances = [min(d,distance(p,point)) for p,d in zip(remaining,distances)]
    refined = []
    for point in selected:
        x,y = point[:2]
        highest = point
        for a,b,c,normal,index in bins.get((math.floor(x*2),math.floor(y*2)),[]):
            ux,uy = b[0]-a[0],b[1]-a[1]
            vx,vy = c[0]-a[0],c[1]-a[1]
            d = ux*vy-uy*vx
            px,py = x-a[0],y-a[1]
            s,t = (px*vy-py*vx)/d,(ux*py-uy*px)/d
            if min(s,t,1-s-t) < -1e-8:
                continue
            z = a[2]+s*(b[2]-a[2])+t*(c[2]-a[2])
            if z>highest[2]:
                highest = (x,y,z,normal,index,s,t)
        if highest[3] < .8:
            raise ValueError("Refined roof sample landed on steep surface")
        refined.append(highest)
    selected = refined
    return selected, dict(unit_sha256=hashlib.sha256((ROOT / "analysis/stock-hub-hologram-24735202/mission_table_hologram.unit.record").read_bytes()).hexdigest(),
                          stream=str(PATH), stream_sha256="68d82d0d753c52d27089a4277f541b22e4a95d1fbc55141f9937032bba6e644b",
                          mesh_index=1, placement=position,scale=scale,rotation=rotation,
                          candidates=len(candidates), selected=len(selected))


if __name__ == "__main__":
    selected,report = sample()
    report = {**report, "points": [{"position": p[:3], "upward_fraction": p[3], "triangle":p[4],
                        "barycentric":p[5:]} for p in selected]}
    out = ROOT / "analysis/roof-placement-refined-24735202.json"
    if out.exists():
        raise ValueError("Roof evidence output exists")
    out.write_text(json.dumps(report,indent=2)+"\n")
    print("-- 180 highest-detail roof samples. World-space positions; no runtime mesh scan.")
    print("return {")
    for point in selected:
        print("    { %.5f, %.5f, %.5f }," % point[:3])
    print("}")
