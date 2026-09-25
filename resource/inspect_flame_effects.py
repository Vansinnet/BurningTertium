"""Read-only exact-identity check for installed source-verified persistent flame effects."""

import hashlib
import json
from pathlib import Path
import struct

from inspect_hologram import GAME, MAGICS, murmur64


BUNDLE = GAME / "bundle/30ebeee18093c079"
EFFECTS = (
    "content/fx/particles/enemies/buff_warpfire",
    "content/fx/particles/rainbow_flame/buff_warpfire_red",
    "content/fx/particles/rainbow_flame/buff_warpfire_red_opacity_50",
    "content/fx/particles/rainbow_flame/buff_warpfire_red_opacity_25",
)


def main():
    if not BUNDLE.is_file():
        print(json.dumps({"bundle": str(BUNDLE), "present": False}, indent=2))
        return
    with BUNDLE.open("rb") as handle:
        header = handle.read(12)
        if header[:8] not in MAGICS:
            raise ValueError("Unexpected installed enemy bundle format")
        count, = struct.unpack_from("<I", header, 8)
        if not 0 < count <= 4096:
            raise ValueError("Enemy bundle resource count")
        handle.seek(268)
        indexed = list(struct.iter_unpack("<QQI", handle.read(count * 20)))
        handle.seek(0)
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    targets = {murmur64(effect): effect for effect in EFFECTS}
    matches = [{"name": targets[name], "index": i, "mode": mode}
               for i, (kind, name, mode) in enumerate(indexed)
               if kind == murmur64("particles") and name in targets]
    print(json.dumps({"bundle": str(BUNDLE), "size": BUNDLE.stat().st_size,
                      "sha256": digest, "indexed_resources": count,
                      "matches": matches}, indent=2))


if __name__ == "__main__":
    main()
