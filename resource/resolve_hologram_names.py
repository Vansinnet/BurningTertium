"""Resolve only hub-hologram asset identities against a public hash dictionary."""

import hashlib
import argparse
import json
from pathlib import Path
import struct
import urllib.request

from inspect_hologram import GAME, murmur64


SOURCE = GAME / "bundle/8aaa27ad87976cf4"
SHA256 = "f9ff268a1af54914215aacb88f36643a01cd96840ac1cf769f4e4a3cd3c3ced2"
URL = ("https://gitlab.com/qasikfwn/bitsquid-blender-tools/-/raw/dev/"
       "bitsquid/murmur/dictionaries/dictionary_hashcat_dt.txt")
OUT_DIR = Path(__file__).resolve().parents[1] / "analysis"
TEXTURE_HASHES = {int(value, 16) for value in (
    "3a50d224cea90d1f", "3ca8b8e35d2261b6", "b8d2e25c4491370c")}


def main(mode):
    out = OUT_DIR / ("dictionary-hub-flames-24735202.json" if mode == "hub-flames" else
                     "dictionary-fx-24735202.json" if mode == "fx" else
                     "dictionary-textures-24735202.json" if mode == "textures"
                     else "dictionary-hologram-24735202.json")
    if out.exists():
        raise ValueError("Do not overwrite dictionary research")
    with SOURCE.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != SHA256:
            raise ValueError("Hub bundle identity changed")
        handle.seek(8)
        count, = struct.unpack("<I", handle.read(4))
        if count != 4376:
            raise ValueError("Unexpected hub index")
        handle.seek(268)
        index = list(struct.iter_unpack("<QQI", handle.read(count * 20)))
    lookup = {}
    for i, (kind, name, mode) in enumerate(index):
        lookup.setdefault(name, []).append({"index": i, "type_hash": f"{kind:016x}", "mode": mode})
    interesting = ("hologram", "mission_board", "mission_table", "map_table", "tactical_table")
    digest = hashlib.sha256()
    hits = []
    textures = []
    effects = []
    hub_flames = []
    variables = []
    lines = 0
    with urllib.request.urlopen(URL, timeout=35) as source:
        for line in source:
            digest.update(line)
            lines += 1
            if len(line) > 4096:
                raise ValueError("Unexpected dictionary entry length")
            value = line.strip().decode("utf-8", errors="replace")
            if not value:
                continue
            name_hash = murmur64(value)
            if (name_hash >> 32) == 0xCB577B8F:
                variables.append(value)
            matched = lookup.get(name_hash)
            if matched and any(word in value.lower() for word in interesting):
                hits.append({"name": value, "name_hash": f"{name_hash:016x}",
                             "registrations": matched})
            if name_hash in TEXTURE_HASHES:
                textures.append({"name": value, "name_hash": f"{name_hash:016x}",
                                 "hub_registration": matched})
            if value.startswith("content/fx/particles/") and ("hologram" in value or
                                                               "holo_" in value):
                effects.append({"name": value, "name_hash": f"{name_hash:016x}",
                                "hub_registration": matched})
            if matched and value.startswith("content/fx/particles/") and any(
                    word in value for word in ("fire", "flame", "torch", "burn")) and any(
                    row["type_hash"] == f"{murmur64('particles'):016x}" for row in matched):
                hub_flames.append({"name": value, "name_hash": f"{name_hash:016x}",
                                   "hub_registration": matched})
            if len(hits) > 128 or len(textures) > 16 or len(effects) > 128 or len(hub_flames) > 128 or len(variables) > 16 or lines > 2_000_000:
                raise ValueError("Unbounded matching dictionary")
    result = {"url": URL, "dictionary_sha256": digest.hexdigest(), "entries": lines,
              "hub_bundle_sha256": SHA256, "verified_hub_matches": hits,
              "texture_name_matches": textures,
              "holographic_effect_name_leads": effects,
              "hub_flame_effects": hub_flames,
              "bottom_parameter_name_candidates": variables,
              "status": "Public name hypotheses verified only by hub bundle hash identity"}
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--textures", action="store_true")
    cli.add_argument("--fx", action="store_true")
    cli.add_argument("--hub-flames", action="store_true")
    args = cli.parse_args()
    main("hub-flames" if args.hub_flames else "fx" if args.fx else
         "textures" if args.textures else "hologram")
