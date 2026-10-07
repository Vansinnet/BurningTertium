"""Replace only the owned red-flame material for a reversible geometry-size trial."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

from local_red_trial import game_closed, replace_exact, record_state

BASE = Path(__file__).resolve().parents[1] / "analysis"
TARGET = Path(r"D:\Steam\steamapps\common\Warhammer 40,000 DARKTIDE\bundle\data\03\03ecd13324afc322")
SOURCE = BASE / "large-red-flame-24735202/large_red_flame.material.candidate"
BEFORE = "8069dc045f4ecc46b0355c0e03cf314103dabdcde09f0a442b8c9cc8926f335f"
AFTER = "d0581de73e4886a486763d7cbaf5e957512b60febfd743b774a3cd0053dc5a35"
OWNER = BASE / "local-candle-trial-20260924T173238Z-68d33205/manifest.json"


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def check():
    game_closed()
    info = json.loads(OWNER.read_text(encoding="utf-8"))
    if info["status"] != "variant_installed" or info["added_stream"] != str(TARGET) or \
       info["stream_sha256"] != BEFORE or TARGET.is_symlink() or sha(TARGET) != BEFORE:
        raise ValueError("Installed flame stream is not the verified owned baseline")
    if sha(SOURCE) != AFTER:
        raise ValueError("Geometry candidate differs from expected SHA-256")


def install():
    check()
    folder = BASE / ("local-large-flame-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") +
                     uuid.uuid4().hex[:8])
    folder.mkdir()
    backup = folder / "red_flame.previous"
    backup.write_bytes(TARGET.read_bytes())
    if sha(backup) != BEFORE:
        raise ValueError("Previous red material backup mismatch")
    info = {"status": "prepared", "target": str(TARGET), "before": BEFORE, "after": AFTER,
            "backup": backup.name, "parent_trial": str(OWNER),
            "rollback_order": "Restore this size trial before restoring the parent candle trial"}
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
       not folder.name.startswith("local-large-flame-"):
        raise ValueError("Unowned size-trial manifest")
    info = json.loads(path.read_text(encoding="utf-8"))
    if (info["target"], info["before"], info["after"], info["backup"]) != \
       (str(TARGET), BEFORE, AFTER, "red_flame.previous") or TARGET.is_symlink():
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
        print("Read-only size-trial preflight passed")
    elif args.install:
        print(json.dumps({"installed_manifest": str(install())}, indent=2))
    else:
        game_closed()
        path = args.verify or args.restore
        folder, info, backup = load(path)
        current = sha(TARGET)
        if args.verify:
            if info["status"] != "installed" or current != AFTER:
                raise ValueError("Size trial is not installed exactly")
            print("Installed size trial and rollback backup verified")
        else:
            if current not in (BEFORE, AFTER):
                raise ValueError("Installed material changed outside this trial")
            if current == AFTER:
                replace_exact(TARGET, backup, BEFORE)
            info["status"] = "restored"
            record_state(folder, info)
            print("Previous red flame material restored; parent trial can now be restored")
