"""Prepare a standalone mod folder from pinned local candidates and Polychromatic's Asset Redirect v2."""

import argparse
import hashlib
import json
from pathlib import Path


MOD = Path(__file__).resolve().parents[1]
MATERIALS = (
    ("red-holo-main-material-24735202/hologram.material.candidate", "bacd9b3be2a4c57f.btmat", "5d1fcc93ee8e9e951ab874ddd1298751cb6c157b528090652cfdfcd3d0850250"),
    ("red-material-trial-24735202/hologram_side.material.candidate", "97b5490a85966a77.btmat", "6541de8e29cda29a996d7580020468df6360794187017f824c9418b20cd8df21"),
    ("red-material-trial-24735202/hologram_bottom.material.candidate", "51f7e0e66641669b.btmat", "3250e754ac19c8f8a8b24c4194e13e1c9eb607d86254d1a933423d1935e83351"),
    ("red-grid-material-24735202/hologram_grid.material.candidate", "59c4260bff372016.btmat", "eed51d396ea8f0a13c151d303b79e4f4ccc6dab82051a2172c23deaad84ae4d7"),
)
LIBRARY_BLOB = "0e0e788c7ae9f523a1a163e711b2e1a86a016cfc"
DLL_BLOB = "0267e09bc60ad50218aafd0680eb1839e49b4c44"


def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--polychromatic", type=Path, required=True, help="Path to the extracted Polychromatic mod folder")
    args = parser.parse_args()
    other = args.polychromatic
    sources = [
        (MOD / "analysis" / source, MOD / "payload" / "redirect" / name, expected, "sha256")
        for source, name, expected in MATERIALS
    ]
    sources += [
        (other / "scripts/mods/Polychromatic/asset_redirect.lua",
         MOD / "scripts/mods/BurningTertium/asset_redirect.lua", LIBRARY_BLOB, "git-blob"),
        (other / "bin/asset-redirect.dll", MOD / "bin/asset-redirect.dll", DLL_BLOB, "git-blob"),
    ]
    verified = []
    for source, destination, expected, method in sources:
        data = source.read_bytes()
        actual = git_blob(data) if method == "git-blob" else hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise ValueError(f"Unexpected {method} for {source}: {actual} (expected {expected})")
        if destination.exists() and destination.read_bytes() != data:
            raise ValueError(f"Existing output differs; refusing to overwrite {destination}")
        verified.append((destination, data))

    for destination, data in verified:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_bytes(data)
        print(f"Verified {destination.relative_to(MOD)} ({len(data)} bytes)")

    layout = json.loads((MOD / "direct-layout.json").read_text(encoding="utf-8"))
    files = layout["files"]
    if layout["modFolder"] != MOD.name or len(files) != len(set(files)):
        raise ValueError("Invalid standalone mod layout")
    for relative in files:
        path = MOD / relative
        if Path(relative).is_absolute() or ".." in Path(relative).parts or not path.is_file():
            raise ValueError(f"Missing or unsafe standalone mod file: {relative}")
    release = json.loads((MOD / "release-layout.json").read_text(encoding="utf-8"))
    entries = release["package"]["payload"]
    if release["profile"] != "direct" or set(files) != {entry["source"] for entry in entries} or len(files) != len(entries):
        raise ValueError("Release payload does not match standalone mod layout")
    if any(entry["destination"] != f"{MOD.name}/{entry['source']}" for entry in entries):
        raise ValueError("Release payload has an unexpected installation path")
    print(f"Standalone layout verified: {len(files)} files")


if __name__ == "__main__":
    main()
