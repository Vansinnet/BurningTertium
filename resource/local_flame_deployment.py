"""Deploy only BurningTertium runtime files for a local reversible flame test."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import uuid


MOD = Path(__file__).resolve().parents[1]
ANALYSIS = MOD / "analysis"
GAME = Path(r"D:\Steam\steamapps\common\Warhammer 40,000 DARKTIDE")
GAME_MODS = GAME / "mods"
TARGET = GAME_MODS / "BurningTertium"
LOAD_ORDER = GAME_MODS / "mod_load_order.txt"
PREFIX = "local-flame-deployment-"
LEGACY_FILES = (
    "BurningTertium.mod",
    "scripts/mods/BurningTertium/BurningTertium.lua",
    "scripts/mods/BurningTertium/BurningTertium_data.lua",
    "scripts/mods/BurningTertium/BurningTertium_localization.lua",
)
FILES = LEGACY_FILES + ("scripts/mods/BurningTertium/roof_positions.lua",)


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def game_closed():
    result = subprocess.run(["tasklist.exe", "/FI", "IMAGENAME eq Darktide.exe", "/FO", "CSV", "/NH"],
                            capture_output=True, text=True, timeout=10, check=True)
    if any(row and row[0].lower() == "darktide.exe" for row in csv.reader(io.StringIO(result.stdout))):
        raise ValueError("Darktide must be closed before deployment or rollback")


def source_rows():
    game_closed()
    if TARGET.exists() or not GAME_MODS.is_dir() or LOAD_ORDER.is_symlink() or not LOAD_ORDER.is_file():
        raise ValueError("Unexpected installed target or mod load order")
    before = LOAD_ORDER.read_bytes()
    lines = before.decode("utf-8-sig").splitlines()
    if "BurningTertium" in lines or len(before) > 128 * 1024:
        raise ValueError("BurningTertium already in mod load order")
    rows = []
    for relative in FILES:
        source = MOD / relative
        if source.is_symlink() or not source.is_file():
            raise ValueError("Runtime source missing or symlinked: " + relative)
        rows.append({"relative": relative, "source_sha256": sha(source), "bytes": source.stat().st_size})
    return rows, before


def put_order(data):
    temporary = LOAD_ORDER.with_name("mod_load_order.burningtertium-" + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, LOAD_ORDER)
    finally:
        if temporary.exists():
            temporary.unlink()


def record_state(folder, manifest):
    temporary = folder / ("manifest." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, folder / "manifest.json")


def install():
    rows, order = source_rows()
    suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    folder = ANALYSIS / (PREFIX + suffix)
    if folder.exists() or not ANALYSIS.is_dir():
        raise ValueError("Backup directory unavailable")
    folder.mkdir()
    backup = folder / "mod_load_order.original"
    backup.write_bytes(order)
    if sha(backup) != hashlib.sha256(order).hexdigest():
        raise ValueError("Mod load order backup mismatch")
    addition = (b"" if order.endswith(b"\n") else b"\n") + b"BurningTertium\n"
    candidate = order + addition
    manifest = {"status": "copy_in_progress", "purpose": "local flame-effect test only",
                "folder": str(TARGET), "load_order_original_sha256": sha(backup),
                "load_order_installed_sha256": hashlib.sha256(candidate).hexdigest(),
                "files": rows}
    record_state(folder, manifest)
    try:
        TARGET.mkdir()
        for row in rows:
            source = MOD / row["relative"]
            destination = TARGET / row["relative"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            if sha(destination) != row["source_sha256"]:
                raise ValueError("Installed Lua or manifest differs: " + row["relative"])
        put_order(candidate)
        if sha(LOAD_ORDER) != manifest["load_order_installed_sha256"]:
            raise ValueError("Installed load order changed")
        manifest["status"] = "installed"
        record_state(folder, manifest)
    except BaseException:
        restore(folder / "manifest.json")
        raise
    return folder


def restore(path):
    game_closed()
    folder = path.resolve().parent
    if folder.parent != ANALYSIS.resolve() or not folder.name.startswith(PREFIX) or path.name != "manifest.json":
        raise ValueError("Unknown deployment manifest")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    owned_files = {row["relative"] for row in manifest["files"]}
    if manifest["folder"] != str(TARGET) or owned_files not in (set(LEGACY_FILES), set(FILES)):
        raise ValueError("Deployment manifest differs from owned file list")
    backup = folder / "mod_load_order.original"
    if sha(backup) != manifest["load_order_original_sha256"]:
        raise ValueError("Original load order backup drift")
    current_order = sha(LOAD_ORDER)
    if current_order not in (manifest["load_order_original_sha256"],
                             manifest["load_order_installed_sha256"]):
        raise ValueError("Mod load order changed outside this trial; refusing rollback")
    if TARGET.exists():
        actual = {path.relative_to(TARGET).as_posix() for path in TARGET.rglob("*") if path.is_file()}
        if actual - owned_files or any(path.is_symlink() for path in TARGET.rglob("*")):
            raise ValueError("Unknown or symlinked file in deployed mod folder; refusing removal")
        for row in manifest["files"]:
            deployed = TARGET / row["relative"]
            if deployed.is_file() and sha(deployed) != row["source_sha256"]:
                raise ValueError("Deployed mod file changed outside this trial")
    if current_order != manifest["load_order_original_sha256"]:
        put_order(backup.read_bytes())
    if TARGET.exists():
        for row in manifest["files"]:
            deployed = TARGET / row["relative"]
            if deployed.is_file():
                deployed.unlink()
        for directory in sorted((p for p in TARGET.rglob("*") if p.is_dir()),
                                key=lambda p: len(p.parts), reverse=True):
            directory.rmdir()
        TARGET.rmdir()
    manifest["status"] = "restored"
    record_state(folder, manifest)
    if sha(LOAD_ORDER) != manifest["load_order_original_sha256"]:
        raise ValueError("Original load order was not restored")


def verify(path):
    game_closed()
    folder = path.resolve().parent
    if folder.parent != ANALYSIS.resolve() or not folder.name.startswith(PREFIX) or path.name != "manifest.json":
        raise ValueError("Unknown verification manifest")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest["status"] != "installed" or sha(LOAD_ORDER) != manifest["load_order_installed_sha256"]:
        raise ValueError("Mod load order is not the installed trial")
    owned_files = {row["relative"] for row in manifest["files"]}
    if owned_files not in (set(LEGACY_FILES), set(FILES)) or manifest["folder"] != str(TARGET):
        raise ValueError("Unexpected installed manifest scope")
    if {p.relative_to(TARGET).as_posix() for p in TARGET.rglob("*") if p.is_file()} != owned_files:
        raise ValueError("Installed mod has unexpected files")
    for row in manifest["files"]:
        if sha(TARGET / row["relative"]) != row["source_sha256"]:
            raise ValueError("Deployed file differs: " + row["relative"])
    if sha(folder / "mod_load_order.original") != manifest["load_order_original_sha256"]:
        raise ValueError("Mod load order backup changed")
    return len(manifest["files"])


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    group = cli.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--install", action="store_true")
    group.add_argument("--verify", type=Path, metavar="MANIFEST")
    group.add_argument("--restore", type=Path, metavar="MANIFEST")
    args = cli.parse_args()
    if args.check:
        sources, order = source_rows()
        print(json.dumps({"status": "read-only preflight passed", "files": sources,
                          "load_order_original_sha256": hashlib.sha256(order).hexdigest()}, indent=2))
    elif args.install:
        print(json.dumps({"status": "local flame trial deployed", "backup": str(install())}, indent=2))
    elif args.verify:
        print(json.dumps({"status": "deployment and backup verified", "files": verify(args.verify)}, indent=2))
    else:
        restore(args.restore)
        print(json.dumps({"status": "deployed mod and load order restored"}, indent=2))
