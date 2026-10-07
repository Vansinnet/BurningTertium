"""Snapshot release-preparation inputs without touching installed game files."""

import hashlib
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


mod = Path(__file__).resolve().parents[1]
workspace = mod.parents[2]
backup = workspace / "backups" / f"BurningTertium-direct-release-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
if not backup.parent.is_dir():
    raise RuntimeError(f"Expected backup parent missing: {backup.parent}")
tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=mod).decode().strip("\0").split("\0")
extras = [
    "bin/asset-redirect.dll", "direct-layout.json", "info.json", "installer/release-layout.legacy.json",
    "release-manifest.template.json", "resource/build_redirect_payload.py",
    "scripts/mods/BurningTertium/asset_redirect.lua", "scripts/mods/BurningTertium/redirects.lua",
]
extras += [str(path.relative_to(mod)).replace("\\", "/") for path in (mod / "payload/redirect").iterdir() if path.is_file()]
paths = {f"mods/active/BurningTertium/{path}": mod / path for path in tracked + extras}
paths["tools/release-mod.ps1"] = workspace / "tools/release-mod.ps1"
paths["tools/tests/release-mod-fixtures.ps1"] = workspace / "tools/tests/release-mod-fixtures.ps1"
for relative, source in sorted(paths.items()):
    target = backup / "files" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_file():
        shutil.copy2(source, target)
    elif relative.startswith("mods/active/BurningTertium/"):
        target.write_bytes(subprocess.check_output(["git", "show", "HEAD:" + relative.removeprefix("mods/active/BurningTertium/")], cwd=mod))
    else:
        raise RuntimeError(f"Missing source: {source}")

lines = []
for relative in sorted(paths):
    data = (backup / "files" / relative).read_bytes()
    lines.append(f"{hashlib.sha256(data).hexdigest()}  files/{relative}")
(backup / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii")
(backup / "ROLLBACK.txt").write_text(
    "This snapshot predates the direct-install GitHub cleanup. All file paths under files/ are relative to the workspace root.\n"
    "Restore individual files from files/ after verifying SHA256SUMS. Removed tracked files also remain in Git history\n"
    "at 613df31. The installed Darktide game was not touched. Do not publish this backup.\n",
    encoding="utf-8",
)
print(f"Backup: {backup} ({len(lines)} files); SHA256SUMS and ROLLBACK.txt written")
