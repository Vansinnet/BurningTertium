"""Two-stage, hash-pinned local candle-bundle acceptance trial with rollback."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
GAME = Path(r"D:\Steam\steamapps\common\Warhammer 40,000 DARKTIDE")
STEAM = Path(r"D:\Steam\steamapps\appmanifest_1361210.acf")
BUNDLE = GAME / "bundle/8aaa27ad87976cf4"
NOOP = ANALYSIS / "candle-noop-bundle-24735202/8aaa27ad87976cf4.noop.bundle"
CANDIDATE = ANALYSIS / "candle-variant-bundle-24735202/8aaa27ad87976cf4.bundle.candidate"
STREAM = ANALYSIS / "red-candle-material-24735202/candle_flame_red.material.candidate"
ADDITION = GAME / "bundle/data/03/03ecd13324afc322"
BUILD = "24735202"
ORIGINAL_SHA = "f9ff268a1af54914215aacb88f36643a01cd96840ac1cf769f4e4a3cd3c3ced2"
NOOP_SHA = "82a19eea254e8e8c534d10446de8627cc15d3cf099bc78dfd5818c306f7ffddd"
CANDIDATE_SHA = "23b3d1832fcb4b487227ddb2a236d8e4595985cac9cf30de95fc3a59c8918fb9"
STREAM_SHA = "8069dc045f4ecc46b0355c0e03cf314103dabdcde09f0a442b8c9cc8926f335f"
PREFIX = "local-candle-trial-"


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def game_closed():
    result = subprocess.run(["tasklist.exe", "/FI", "IMAGENAME eq Darktide.exe", "/FO", "CSV", "/NH"],
                            capture_output=True, text=True, timeout=10, check=True)
    if any(row and row[0].lower() == "darktide.exe" for row in csv.reader(io.StringIO(result.stdout))):
        raise ValueError("Darktide must be closed before changing resource files")


def base_check():
    game_closed()
    if '"buildid"\t\t"' + BUILD + '"' not in STEAM.read_text(encoding="utf-8"):
        raise ValueError("Unsupported Darktide build")
    for path, digest in ((NOOP, NOOP_SHA), (CANDIDATE, CANDIDATE_SHA), (STREAM, STREAM_SHA)):
        if sha(path) != digest:
            raise ValueError("Offline candidate differs from pinned SHA-256: " + str(path))
    managed = json.loads((ROOT.parent / "RainbowFlame/payload/manifest.json").read_text())
    vortex = json.loads((GAME / "vortex.deployment.json").read_text())
    occupied = {item["target"].lower() for item in managed["files"]} | \
               {item["relPath"].replace("\\", "/").lower() for item in vortex["files"]}
    for path in (BUNDLE, ADDITION):
        if path.relative_to(GAME).as_posix().lower() in occupied or path.is_symlink():
            raise ValueError("Another mod manages the target: " + str(path))
    if not BUNDLE.is_file() or ADDITION.exists() or sha(BUNDLE) != ORIGINAL_SHA:
        raise ValueError("Installed stock hub bundle or free material stream changed")


def replace_exact(target, source, expected):
    if target == ADDITION and target.exists():
        raise ValueError("New material stream path already occupied")
    temp = target.with_name(target.name + ".burningtertium-" + uuid.uuid4().hex + ".tmp")
    try:
        with source.open("rb") as input_file, temp.open("xb") as output_file:
            shutil.copyfileobj(input_file, output_file)
            output_file.flush()
            os.fsync(output_file.fileno())
        if sha(temp) != expected:
            raise ValueError("Staged resource differs from expected SHA-256")
        if target == ADDITION and target.exists():
            raise ValueError("Another writer created the new material stream")
        os.replace(temp, target)
        if sha(target) != expected:
            raise ValueError("Installed resource differs from expected SHA-256")
    finally:
        if temp.exists():
            temp.unlink()


def save_manifest(folder, manifest):
    temp = folder / ("manifest." + uuid.uuid4().hex + ".tmp")
    temp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, folder / "manifest.json")


def owned_manifest(path):
    folder = path.resolve().parent
    if folder.parent != ANALYSIS.resolve() or not folder.name.startswith(PREFIX) or path.name != "manifest.json":
        raise ValueError("Not an owned candle trial manifest")
    info = json.loads(path.read_text(encoding="utf-8"))
    if (info["build"], info["game_bundle"], info["added_stream"], info["original_sha256"],
        info["noop_sha256"], info["candidate_sha256"], info["stream_sha256"]) != \
       (BUILD, str(BUNDLE), str(ADDITION), ORIGINAL_SHA, NOOP_SHA, CANDIDATE_SHA, STREAM_SHA):
        raise ValueError("Candle trial manifest scope differs")
    return folder, info


def install_noop():
    base_check()
    folder = ANALYSIS / (PREFIX + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") +
                         uuid.uuid4().hex[:8])
    if folder.exists() or not ANALYSIS.is_dir():
        raise ValueError("Backup destination unavailable")
    folder.mkdir()
    backup = folder / "8aaa27ad87976cf4.original"
    shutil.copy2(BUNDLE, backup)
    if sha(backup) != ORIGINAL_SHA:
        raise ValueError("Original hub bundle backup differs")
    info = {"build": BUILD, "status": "prepared", "game_bundle": str(BUNDLE),
            "added_stream": str(ADDITION), "backup": backup.name,
            "stream_parent_preexisting": ADDITION.parent.is_dir(),
            "original_sha256": ORIGINAL_SHA, "noop_sha256": NOOP_SHA,
            "candidate_sha256": CANDIDATE_SHA, "stream_sha256": STREAM_SHA,
            "purpose": "stock-content physical no-op first; authored red effect only after game acceptance"}
    save_manifest(folder, info)
    try:
        replace_exact(BUNDLE, NOOP, NOOP_SHA)
        info["status"] = "noop_installed"
        save_manifest(folder, info)
    except BaseException:
        restore(folder / "manifest.json")
        raise
    return folder


def promote(path):
    game_closed()
    folder, info = owned_manifest(path)
    if '"buildid"\t\t"' + BUILD + '"' not in STEAM.read_text(encoding="utf-8") or \
       sha(NOOP) != NOOP_SHA or sha(CANDIDATE) != CANDIDATE_SHA or sha(STREAM) != STREAM_SHA:
        raise ValueError("Build or authored resource changed since physical no-op test")
    if info["status"] != "noop_installed" or sha(folder / info["backup"]) != ORIGINAL_SHA or \
       sha(BUNDLE) != NOOP_SHA or ADDITION.exists():
        raise ValueError("Physical no-op trial is not at its verified baseline")
    ADDITION.parent.mkdir(parents=True, exist_ok=True)
    try:
        replace_exact(ADDITION, STREAM, STREAM_SHA)
        replace_exact(BUNDLE, CANDIDATE, CANDIDATE_SHA)
        info["status"] = "variant_installed"
        save_manifest(folder, info)
    except BaseException:
        restore(path)
        raise


def verify(path):
    game_closed()
    folder, info = owned_manifest(path)
    if sha(folder / info["backup"]) != ORIGINAL_SHA:
        raise ValueError("Stock backup differs")
    if info["status"] == "noop_installed":
        if sha(BUNDLE) != NOOP_SHA or ADDITION.exists():
            raise ValueError("No-op trial state differs")
    elif info["status"] == "variant_installed":
        if sha(BUNDLE) != CANDIDATE_SHA or sha(ADDITION) != STREAM_SHA:
            raise ValueError("Authored trial state differs")
    else:
        raise ValueError("Nothing installed for this manifest")
    return info["status"]


def restore(path):
    game_closed()
    folder, info = owned_manifest(path)
    backup = folder / info["backup"]
    if sha(backup) != ORIGINAL_SHA:
        raise ValueError("Original hub bundle backup differs")
    current = sha(BUNDLE)
    if current not in (ORIGINAL_SHA, NOOP_SHA, CANDIDATE_SHA):
        raise ValueError("Hub bundle changed since owned trial; refusing rollback")
    if ADDITION.exists() and (ADDITION.is_symlink() or sha(ADDITION) != STREAM_SHA):
        raise ValueError("Authored stream changed since trial; refusing removal")
    if current != ORIGINAL_SHA:
        replace_exact(BUNDLE, backup, ORIGINAL_SHA)
    if ADDITION.exists():
        ADDITION.unlink()
    if not info["stream_parent_preexisting"] and ADDITION.parent.is_dir():
        ADDITION.parent.rmdir()
    info["status"] = "restored"
    save_manifest(folder, info)
    if sha(BUNDLE) != ORIGINAL_SHA or ADDITION.exists():
        raise ValueError("Rollback did not restore exact original state")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    group = cli.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--install-noop", action="store_true")
    group.add_argument("--promote", type=Path, metavar="MANIFEST")
    group.add_argument("--verify", type=Path, metavar="MANIFEST")
    group.add_argument("--restore", type=Path, metavar="MANIFEST")
    args = cli.parse_args()
    if args.check:
        base_check()
        print(json.dumps({"status": "stock hub and offline candidates pass read-only preflight",
                          "stock_sha256": ORIGINAL_SHA, "new_stream_absent": True}, indent=2))
    elif args.install_noop:
        print(json.dumps({"status": "physical no-op installed", "backup": str(install_noop())}, indent=2))
    elif args.promote:
        promote(args.promote)
        print(json.dumps({"status": "authored flame variant installed"}, indent=2))
    elif args.verify:
        print(json.dumps({"status": verify(args.verify), "backup": str(args.verify.parent)}, indent=2))
    else:
        restore(args.restore)
        print(json.dumps({"status": "stock hub bundle restored; owned stream removed"}, indent=2))
