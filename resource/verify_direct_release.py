"""Check the final direct-install archive against its source manifest and allowlist."""

import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZipFile


mod = Path(__file__).resolve().parents[1]
archive = Path(sys.argv[1]).resolve()
layout = json.loads((mod / "release-layout.json").read_text(encoding="utf-8"))
expected = {entry["destination"]: entry["source"] for category in layout["package"].values() for entry in category}
assert len(expected) == sum(map(len, layout["package"].values()))
source_lines = (archive.parent / "BurningTertium.source.sha256").read_text(encoding="ascii").splitlines()
sources = {path: digest.lower() for digest, path in (line.split("  ", 1) for line in source_lines)}
assert set(sources) == {f"BurningTertium/{source}" for source in expected.values()} | {"BurningTertium/release-layout.json"}
with ZipFile(archive) as z:
    names = z.namelist()
    assert len(names) == len(expected) and set(names) == set(expected)
    for name, source in expected.items():
        assert name.startswith("BurningTertium/") and "\\" not in name and ".." not in Path(name).parts
        payload = z.read(name)
        checksum = hashlib.sha256(payload).hexdigest()
        assert checksum == sources[f"BurningTertium/{source}"], name
        assert checksum == hashlib.sha256((mod / source).read_bytes()).hexdigest(), name

hash_line = (archive.parent / "BurningTertium.zip.sha256").read_text(encoding="ascii").strip()
digest, filename = hash_line.split("  ", 1)
assert filename == archive.name and digest.lower() == hashlib.sha256(archive.read_bytes()).hexdigest()
assert json.loads((mod / "info.json").read_text(encoding="utf-8"))["version"] == "1.1.1"
print(f"Verified {len(names)} archive entries against source manifest; ZIP SHA-256 {digest}")
