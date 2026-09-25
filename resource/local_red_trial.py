"""Hash-pinned four-file local color trial, with owned backup and exact rollback."""

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


MOD = Path(__file__).resolve().parents[1]
ANALYSIS = MOD / "analysis"
GAME = Path(r"D:\Steam\steamapps\common\Warhammer 40,000 DARKTIDE")
STEAM = Path(r"D:\Steam\steamapps\appmanifest_1361210.acf")
EXPECTED_BUILD = "24735202"
BACKUP_PREFIX = "local-red-trial-"


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def game_closed():
    result = subprocess.run(["tasklist.exe", "/FI", "IMAGENAME eq Darktide.exe", "/FO", "CSV", "/NH"],
                            capture_output=True, text=True, timeout=10, check=True)
    if any(row and row[0].lower() == "darktide.exe" for row in csv.reader(io.StringIO(result.stdout))):
        raise ValueError("Darktide is running; close it before modifying game files")


def require_build():
    text = STEAM.read_text(encoding="utf-8")
    if '"buildid"\t\t"' + EXPECTED_BUILD + '"' not in text:
        raise ValueError("Unsupported Steam build")


def rows():
    red_dir = ANALYSIS / "red-material-trial-24735202"
    grid_dir = ANALYSIS / "red-grid-material-24735202"
    red = json.loads((red_dir / "report.json").read_text())
    grid = json.loads((grid_dir / "report.json").read_text())
    if red["build"] != EXPECTED_BUILD or grid["build"] != EXPECTED_BUILD:
        raise ValueError("Trial does not target this build")
    result = []
    for record in red["materials"]:
        result.append(dict(label=record["name"].rsplit("/", 1)[-1],
                           target=Path(record["source"]), original=record["source_sha256"],
                           candidate=red_dir / record["output"], output=record["output_sha256"]))
    result.append(dict(label="hologram_grid", target=Path(grid["source"]),
                       original=grid["source_sha256"],
                       candidate=grid_dir / "hologram_grid.material.candidate",
                       output=grid["candidate_sha256"]))
    if {row["label"] for row in result} != {"hologram", "hologram_side", "hologram_bottom", "hologram_grid"}:
        raise ValueError("Unexpected material scope")
    manifest = json.loads((MOD.parent / "RainbowFlame/payload/manifest.json").read_text())
    managed = {row["target"].lower() for row in manifest["files"]}
    vortex = json.loads((GAME / "vortex.deployment.json").read_text())
    deployed = {row["relPath"].replace("\\", "/").lower() for row in vortex["files"]}
    for row in result:
        path = row["target"]
        if path.is_symlink() or not path.is_file() or not row["candidate"].is_file():
            raise ValueError("Material missing or symlinked: " + row["label"])
        relative = path.relative_to(GAME).as_posix().lower()
        if not relative.startswith("bundle/data/") or relative in managed or relative in deployed:
            raise ValueError("Unowned / mod-managed target: " + relative)
        if sha(row["candidate"]) != row["output"]:
            raise ValueError("Authored candidate drift: " + row["label"])
    return result


def preflight():
    game_closed()
    require_build()
    result = rows()
    for row in result:
        if sha(row["target"]) != row["original"]:
            raise ValueError("Original bytes changed: " + row["label"])
    return result


def replace_exact(target, source, digest):
    temporary = target.with_name(target.name + ".burningtertium-" + uuid.uuid4().hex + ".tmp")
    try:
        with source.open("rb") as input_file, temporary.open("xb") as output_file:
            shutil.copyfileobj(input_file, output_file)
            output_file.flush()
            os.fsync(output_file.fileno())
        if sha(temporary) != digest:
            raise ValueError("Temporary file did not match intended SHA-256")
        os.replace(temporary, target)
        if sha(target) != digest:
            raise ValueError("Replaced target did not match intended SHA-256")
    finally:
        if temporary.exists():
            temporary.unlink()


def record_state(folder, manifest):
    temporary = folder / ("manifest." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, folder / "manifest.json")


def install():
    targets = preflight()
    folder = ANALYSIS / (BACKUP_PREFIX + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") +
                         uuid.uuid4().hex[:8])
    if folder.exists() or not ANALYSIS.is_dir():
        raise ValueError("Backup destination unavailable")
    folder.mkdir()
    manifest = {"build": EXPECTED_BUILD, "purpose": "temporary red-color visual trial, NO FLAMES",
                "status": "backup_in_progress", "files": []}
    try:
        for row in targets:
            backup = folder / (row["label"] + ".original")
            shutil.copy2(row["target"], backup)
            if sha(backup) != row["original"]:
                raise ValueError("Backup hash mismatch: " + row["label"])
            manifest["files"].append({"label": row["label"], "target": str(row["target"]),
                                      "backup": backup.name, "original_sha256": row["original"],
                                      "candidate_sha256": row["output"]})
        manifest["status"] = "install_in_progress"
        record_state(folder, manifest)
        for row in targets:
            replace_exact(row["target"], row["candidate"], row["output"])
        manifest["status"] = "installed"
        record_state(folder, manifest)
    except BaseException:
        if manifest["status"] == "install_in_progress":
            try:
                restore(folder / "manifest.json")
            except Exception as restore_error:
                raise RuntimeError("Automatic rollback failed; keep backup " + str(folder)) from restore_error
        raise
    return folder


def restore(path):
    game_closed()
    folder = path.resolve().parent
    if folder.parent != ANALYSIS.resolve() or not folder.name.startswith(BACKUP_PREFIX) or path.name != "manifest.json":
        raise ValueError("Rollback manifest is outside owned research directory")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest["build"] != EXPECTED_BUILD or len(manifest["files"]) != 4:
        raise ValueError("Unexpected backup inventory")
    entries = []
    for row in manifest["files"]:
        target = Path(row["target"])
        backup = folder / row["backup"]
        if backup.parent != folder or target.is_symlink() or not backup.is_file() or \
           target.relative_to(GAME).as_posix().lower().startswith("bundle/data/") is False:
            raise ValueError("Backup target outside owned scope")
        if sha(backup) != row["original_sha256"]:
            raise ValueError("Backup corrupt: " + row["label"])
        current = sha(target)
        if current not in (row["original_sha256"], row["candidate_sha256"]):
            raise ValueError("Target changed since trial; refusing rollback: " + row["label"])
        entries.append((target, backup, row["original_sha256"]))
    for target, backup, original in entries:
        if sha(target) != original:
            replace_exact(target, backup, original)
    manifest["status"] = "restored"
    record_state(folder, manifest)


def verify(path):
    game_closed()
    folder = path.resolve().parent
    if folder.parent != ANALYSIS.resolve() or not folder.name.startswith(BACKUP_PREFIX) or path.name != "manifest.json":
        raise ValueError("Verification manifest is outside owned research directory")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest["status"] != "installed" or manifest["build"] != EXPECTED_BUILD or len(manifest["files"]) != 4:
        raise ValueError("Not a complete installed trial")
    for row in manifest["files"]:
        target = Path(row["target"])
        backup = folder / row["backup"]
        if target.is_symlink() or backup.parent != folder or \
           not target.relative_to(GAME).as_posix().lower().startswith("bundle/data/") or \
           sha(target) != row["candidate_sha256"] or sha(backup) != row["original_sha256"]:
            raise ValueError("Installed trial or rollback input differs: " + row["label"])
    return [row["label"] for row in manifest["files"]]


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    group = cli.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Read-only four-file preflight")
    group.add_argument("--install", action="store_true", help="Install authorized local red trial")
    group.add_argument("--verify", type=Path, metavar="MANIFEST", help="Verify installed trial and backups")
    group.add_argument("--restore", type=Path, metavar="MANIFEST", help="Restore exact owned original bytes")
    args = cli.parse_args()
    if args.check:
        print(json.dumps({"status": "read-only preflight passed", "build": EXPECTED_BUILD,
                          "materials": [row["label"] for row in preflight()]}, indent=2))
    elif args.install:
        print(json.dumps({"status": "temporary red trial installed", "backup": str(install())}, indent=2))
    elif args.verify:
        print(json.dumps({"status": "installed trial and backups verified",
                          "materials": verify(args.verify)}, indent=2))
    else:
        restore(args.restore)
        print(json.dumps({"status": "original materials restored", "backup": str(args.restore.parent)}, indent=2))
