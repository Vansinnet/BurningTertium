"""Replace only the owned red-flame material with the procedural-fire pixel program (size kept).

Rollback order: restore this fire trial first, then the large-flame size trial, then the candle trial."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

from local_red_trial import game_closed, replace_exact, record_state

BASE = Path(__file__).resolve().parents[1] / "analysis"
TARGET = Path(r"D:\Steam\steamapps\common\Warhammer 40,000 DARKTIDE\bundle\data\03\03ecd13324afc322")
SOURCE = BASE / "fire-flame-material-24735202/fire_flame.material.candidate"
BEFORE = "d0581de73e4886a486763d7cbaf5e957512b60febfd743b774a3cd0053dc5a35"
AFTER = "10085308e43f3a7b6b053cb821bac5296680b01636f962fe36a0186f7efcf6aa"
OWNER = BASE / "local-large-flame-20260924T185223Z-f5245f0e/manifest.json"


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def check():
    game_closed()
    info = json.loads(OWNER.read_text(encoding="utf-8"))
    if info["status"] != "installed" or info["target"] != str(TARGET) or \
       info["after"] != BEFORE or TARGET.is_symlink() or sha(TARGET) != BEFORE:
        raise ValueError("Installed flame stream is not the verified owned baseline")
    if sha(SOURCE) != AFTER:
        raise ValueError("Fire candidate differs from expected SHA-256")


def install():
    check()
    folder = BASE / ("local-fire-flame-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") +
                     uuid.uuid4().hex[:8])
    folder.mkdir()
    backup = folder / "large_flame.previous"
    backup.write_bytes(TARGET.read_bytes())
    if sha(backup) != BEFORE:
        raise ValueError("Previous large-flame material backup mismatch")
    info = {"status": "prepared", "target": str(TARGET), "before": BEFORE, "after": AFTER,
            "backup": backup.name, "parent_trial": str(OWNER),
            "rollback_order": "Restore this fire trial before the large-flame size trial and the candle trial"}
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
    if path.name != "manifest.json" or folder.parent != BASE.resolve() or \
       not folder.name.startswith("local-fire-flame-"):
        raise ValueError("Unowned fire-trial manifest")
    info = json.loads(path.read_text(encoding="utf-8"))
    if (info["target"], info["before"], info["after"], info["backup"]) != \
       (str(TARGET), BEFORE, AFTER, "large_flame.previous") or TARGET.is_symlink():
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
        print("Read-only fire-trial preflight passed")
    elif args.install:
        print(json.dumps({"installed_manifest": str(install())}, indent=2))
    else:
        game_closed()
        path = args.verify or args.restore
        folder, info, backup = load(path)
        current = sha(TARGET)
        if args.verify:
            if info["status"] != "installed" or current != AFTER:
                raise ValueError("Fire trial is not installed exactly")
            print("Installed fire trial and rollback backup verified")
        else:
            if current not in (BEFORE, AFTER):
                raise ValueError("Installed material changed outside this trial")
            if current == AFTER:
                replace_exact(TARGET, backup, BEFORE)
            info["status"] = "restored"
            record_state(folder, info)
            print("Large red-flame material restored; size trial can now be restored")
