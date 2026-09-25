"""Undo every local BurningTertium development trial so the release installer starts from stock.

Order (each step hash-checked, each refuses unknown bytes):
  1. deployed BurningTertium.lua bridge revisions -> first deployed revision
  2. Lua deployment (mod folder + load-order line)       local-flame-deployment-20260924T191636Z-92ba66d0
  3. hologram shader trial                               local-holo-shader-20260924T195111Z-3cc70c34
  4. four hologram colour materials -> stock             local-red-trial-20260923T203209Z-d11ff686
  5. large-flame size trial                              local-large-flame-20260924T185223Z-f5245f0e
  6. candle hub bundle + added stream -> stock           local-candle-trial-20260924T173238Z-68d33205

--check only reads and reports. --restore performs all remaining steps. Darktide must be closed.
"""

import argparse
import json
from pathlib import Path

import local_candle_trial as candle
import local_flame_deployment as lua_deploy
from local_red_trial import GAME, game_closed, record_state, replace_exact, sha
import local_red_trial as red

ANALYSIS = Path(__file__).resolve().parents[1] / "analysis"
LUA = GAME / "mods/BurningTertium/scripts/mods/BurningTertium/BurningTertium.lua"
LUA_FIRST = "9bdde7b43398dcb48e6d484d93ceaf0eb0cee5fe7d8db2fc3013f36b50b130d4"
LUA_KNOWN = {LUA_FIRST, "7c1629f0a909cfbf1ccbf3b4ea5e869627f225c601928be370b0b20d4666fe05",
             "1cd6a383a0a9ac0358299d6410be94a3b622f3bd248aa29f2761839346ee0f46",
             "20a3695a7947cf24a88e723f01990d280243c47eed589957217fa3457cd3c30f",
             "de30fbdf99b299865aa9678d7aeef215daacdbd2da7e746d961192644a26f172"}
LUA_BACKUP = ANALYSIS / "local-fire-lua-20260924T204422Z-98cfc880/BurningTertium.lua.previous"
LUA_MANIFESTS = sorted(ANALYSIS.glob("local-fire-lua-*/manifest.json"))
DEPLOY = ANALYSIS / "local-flame-deployment-20260924T191636Z-92ba66d0/manifest.json"
SHADER = ANALYSIS / "local-holo-shader-20260924T195111Z-3cc70c34/manifest.json"
RED = ANALYSIS / "local-red-trial-20260923T203209Z-d11ff686/manifest.json"
LARGE = ANALYSIS / "local-large-flame-20260924T185223Z-f5245f0e/manifest.json"
CANDLE = ANALYSIS / "local-candle-trial-20260924T173238Z-68d33205/manifest.json"


def single(manifest_path, backup_name):
    info = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = Path(info["target"])
    backup = manifest_path.parent / backup_name
    if target.is_symlink() or sha(backup) != info["before"]:
        raise ValueError("Backup or target scope differs: " + str(manifest_path))
    return info, target, backup


def restore_single(manifest_path, backup_name, apply):
    info, target, backup = single(manifest_path, backup_name)
    current = sha(target)
    if current == info["before"]:
        return "already restored"
    if current != info["after"]:
        raise ValueError("Unknown bytes at " + str(target))
    if apply:
        replace_exact(target, backup, info["before"])
        info["status"] = "restored"
        record_state(manifest_path.parent, info)
    return "restore " + target.name


def plan(apply):
    game_closed()
    steps = []
    if LUA.exists():
        current = sha(LUA)
        if current not in LUA_KNOWN:
            raise ValueError("Deployed BurningTertium.lua has unknown bytes")
        if sha(LUA_BACKUP) != LUA_FIRST:
            raise ValueError("First Lua backup drift")
        if current != LUA_FIRST:
            steps.append("restore first deployed Lua revision")
            if apply:
                replace_exact(LUA, LUA_BACKUP, LUA_FIRST)
                for path in LUA_MANIFESTS:
                    info = json.loads(path.read_text(encoding="utf-8"))
                    info["status"] = "restored"
                    record_state(path.parent, info)
        steps.append("remove Lua deployment")
        if apply:
            lua_deploy.restore(DEPLOY)
    steps.append("hologram shader: " + restore_single(SHADER, "hologram.previous", apply))
    manifest = json.loads(RED.read_text(encoding="utf-8"))
    if any(sha(Path(row["target"])) != row["original_sha256"] for row in manifest["files"]):
        steps.append("restore four stock hologram materials")
        if apply:
            red.restore(RED)
    steps.append("large flame: " + restore_single(LARGE, "red_flame.previous", apply))
    if sha(candle.BUNDLE) != candle.ORIGINAL_SHA or candle.ADDITION.exists():
        steps.append("restore stock hub bundle and remove owned stream")
        if apply:
            candle.restore(CANDLE)
    return steps


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = cli.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--restore", action="store_true")
    args = cli.parse_args()
    print(json.dumps({"mode": "restore" if args.restore else "check", "steps": plan(args.restore)}, indent=2))
