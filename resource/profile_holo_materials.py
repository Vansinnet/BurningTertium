"""Read only the four pinned installed hub-hologram material streams and exports."""

import hashlib
import importlib
import json
from pathlib import Path
import sys

from inspect_hologram import murmur64


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1] / "analysis" / "stock-hub-hologram-24735202"
sys.path.insert(0, str(ROOT / "docs" / "analysis-flame-target-20260917-a1"))
parser = importlib.import_module("parse_materials")
report = json.loads((OUT / "provenance.json").read_text())
managed = json.loads((ROOT / "mods/active/RainbowFlame/payload/manifest.json").read_text())
managed_paths = {row["target"].lower() for row in managed["files"]}
vortex = json.loads((Path(r"D:\Steam\steamapps\common\Warhammer 40,000 DARKTIDE") /
                     "vortex.deployment.json").read_text())
deployed_paths = {row["relPath"].replace("\\", "/").lower() for row in vortex["files"]}
materials = []
all_hashes = set()
for item in report["resources"]:
    if not item["record"].endswith(".material.record"):
        continue
    if len(item["installed_streams"]) != 1:
        raise ValueError("Unexpected material stream count")
    pinned = item["installed_streams"][0]
    relative = "bundle/" + item["pointer_paths"][0]
    if relative.lower() in managed_paths or relative.lower() in deployed_paths:
        raise ValueError("Installed material stream is managed by a mod")
    data = Path(pinned["path"]).read_bytes()
    if len(data) != pinned["size"] or hashlib.sha256(data).hexdigest() != pinned["sha256"]:
        raise ValueError("Installed material drift")
    parsed = parser.parse(data)
    all_hashes.update(var["name_hash"] for var in parsed["variables"])
    materials.append((item["name"], pinned["sha256"], parsed))
if len(materials) != 4:
    raise ValueError("Expected four hub hologram materials")

names = {key: [] for key in all_hashes}
for candidate in ("color", "tint_color", "emissive_color", "light_color",
                  "emissive_color_intensity", "color_filter", "base_color",
                  "material_variable_046f8451", "material_variable_973657dd",
                  "material_variable", "flicker_enabled", "scanline_distance_fade_disabled"):
    key = f"{murmur64(candidate) >> 32:08x}"
    if key in names:
        names[key].append(candidate)
dictionary = ROOT / "docs/analysis-flame-target-20260917-a1/parser-reference/bitsquid/murmur/dictionaries/dictionary_hashcat_dt_short.txt"
if dictionary.is_file():
    for name in dictionary.read_text(encoding="utf-8").splitlines():
        key = f"{murmur64(name) >> 32:08x}"
        if key in names:
            names[key].append(name)
print(json.dumps([{"name": name, "sha256": digest, "version": model["version"],
                   "parents": model["parent_hashes"], "textures": model["textures"],
                   "shader_bytes": model["shader_size"],
                   "variables": [{**value, "matching_names": names[value["name_hash"]]}
                                 for value in model["variables"]]}
                  for name, digest, model in materials], indent=2))
