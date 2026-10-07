"""Verify shipped positions against evidence and independent vertical ray intersections."""

import json
import re

from sample_roofs import geometry, ROOT

evidence = json.loads((ROOT / "analysis/roof-placement-refined-24735202.json").read_text())
source = (ROOT / "scripts/mods/BurningTertium/roof_positions.lua").read_text()
points = [tuple(map(float, row)) for row in re.findall(
    r"\{\s*(-?[\d.]+),\s*(-?[\d.]+),\s*(-?[\d.]+)\s*\}", source)]
if len(points) != 180 or len(set(points)) != 180 or evidence["selected"] != 180:
    raise ValueError("Expected 180 unique roof positions")
for point, row in zip(points,evidence["points"]):
    if max(abs(a-b) for a,b in zip(point,row["position"])) > .000006:
        raise ValueError("Runtime position differs from generated roof evidence")
triangles, origin, scale, rotation, vertices = geometry()
errors = []
for i,(x,y,z) in enumerate(points):
    highest = -1e9
    for a,b,c,normal,index in triangles:
        if x < min(a[0],b[0],c[0]) or x > max(a[0],b[0],c[0]) or \
           y < min(a[1],b[1],c[1]) or y > max(a[1],b[1],c[1]):
            continue
        denominator = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        u = ((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/denominator
        v = ((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/denominator
        w = 1-u-v
        if min(u,v,w) >= -1e-8:
            highest = max(highest,u*a[2]+v*b[2]+w*c[2])
    if abs(highest-z) > .001:
        errors.append(dict(index=i+1,position=(x,y,z),top=highest))
if errors:
    raise ValueError("Roof position not on topmost surface: " + json.dumps(errors))
print(json.dumps({"positions":len(points),"highest_detail_triangles":66704,
                  "all_on_topmost_surface_within_m":.001,
                  "height_range":[min(p[2] for p in points),max(p[2] for p in points)]},indent=2))
