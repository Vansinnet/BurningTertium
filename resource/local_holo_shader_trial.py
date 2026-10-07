"""Replace only the hub city `hologram` material with the red-mirrored pixel-program candidate.

Layer on top of local-red-trial-20260923T203209Z-d11ff686 (which owns the stock backup).
Rollback order: restore THIS trial first, then (if wanted) the four-material red trial.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

from local_red_trial import game_closed, replace_exact, record_state, require_build

BASE = Path(__file__).resolve().parents[1] / "analysis"
TARGET = Path(r"D:\Steam\steamapps\common\Warhammer 40,000 DARKTIDE\bundle\data\ba\bacd9b3be2a4c57f")
SOURCE = BASE / "red-holo-main-material-24735202/hologram.material.candidate"
BEFORE = "4ceb5cf6f7326d14019578326d02d7c354cd56c9ae6b65321521e0a1e2dcc003"
AFTER = "5d1fcc93ee8e9e951ab874ddd1298751cb6c157b528090652cfdfcd3d0850250"
OWNER = BASE / "local-red-trial-20260923T203209Z-d11ff686/manifest.json"
PREFIX = "local-holo-shader-"


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def check():
    game_closed()
    require_build()
    info = json.loads(OWNER.read_text(encoding="utf-8"))
    row = next(r for r in info["files"] if r["label"] == "hologram")
    if info["status"] != "installed" or row["target"] != str(TARGET) or row["candidate_sha256"] != BEFORE:
        raise ValueError("Parent red-parameter trial is not the installed baseline")
    if TARGET.is_symlink() or sha(TARGET) != BEFORE:
        raise ValueError("Installed hologram material is not the verified red-parameter baseline")
    if sha(SOURCE) != AFTER:
        raise ValueError("Shader candidate differs from expected SHA-256")


def install():
    check()
    folder = BASE / (PREFIX + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
    folder.mkdir()
    backup = folder / "hologram.previous"
    backup.write_bytes(TARGET.read_bytes())
    if sha(backup) != BEFORE:
        raise ValueError("Previous hologram material backup mismatch")
    info = {"status": "prepared", "target": str(TARGET), "before": BEFORE, "after": AFTER,
            "backup": backup.name, "parent_trial": str(OWNER),
            "rollback_order": "Restore this shader trial before restoring the parent four-material red trial"}
    record_state(folder, info)
    try:
        replace_exact(TARGET, SOURCE, AFTER)
        info["status"] = "installed"
        record_state(folder, info)
    except BaseException:
        if sha(TARGET) == AFTER:
            replace_exact(TARGET, backup, BEFORE)
        raise
    return folder / "manifest.json"


def load(path):
    folder = path.resolve().parent
    if path.name != "manifest.json" or folder.parent != BASE.resolve() or not folder.name.startswith(PREFIX):
        raise ValueError("Unowned shader-trial manifest")
    info = json.loads(path.read_text(encoding="utf-8"))
    if (info["target"], info["before"], info["after"], info["backup"]) != \
       (str(TARGET), BEFORE, AFTER, "hologram.previous") or TARGET.is_symlink():
        raise ValueError("Trial scope differs")
    backup = folder / info["backup"]
    if sha(backup) != BEFORE:
        raise ValueError("Rollback input differs")
    return folder, info, backup


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    group = cli.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--install", action="store_true")
    group.add_argument("--verify", type=Path)
    group.add_argument("--restore", type=Path)
    args = cli.parse_args()
    if args.check:
        check()
        print("Read-only shader-trial preflight passed")
    elif args.install:
        print(json.dumps({"installed_manifest": str(install())}, indent=2))
    else:
        game_closed()
        folder, info, backup = load(args.verify or args.restore)
        current = sha(TARGET)
        if args.verify:
            if info["status"] != "installed" or current != AFTER:
                raise ValueError("Shader trial is not installed exactly")
            print("Installed shader trial and rollback backup verified")
        else:
            if current not in (BEFORE, AFTER):
                raise ValueError("Installed material changed outside this trial")
            if current == AFTER:
                replace_exact(TARGET, backup, BEFORE)
            info["status"] = "restored"
            record_state(folder, info)
            print("Red-parameter hologram material restored; parent trial can now be restored")
