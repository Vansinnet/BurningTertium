# BurningTertium

BurningTertium sets the Tertium hologram above the Mourningstar mission table
on fire. The projected city turns saturated red, and real, animated fire
burns on its rooftops with drifting smoke. Only the hologram on the mission
table changes; other screens, lights and holograms, gameplay, missions and
networking are untouched.

## What is changed

- **Red hologram:** four hologram material files are replaced: the city,
  sides, base and grid. The city shader's own hardcoded green light and green
  base gradient are mirrored to red, so no green remains. Transparency,
  scanlines and city detail are preserved.
- **Fire:** the DMF mod places Darktide's own lingering fire-grenade fire on
  verified rooftop positions of the hologram's city model and keeps it
  burning. It loads the stock effect packages itself; no fire resources are
  modified.

## Requirements

- Darktide Mod Loader (DML) and Darktide Mod Framework (DMF).
- Darktide Steam build `24735202`, executable `1.3.770.210`, Windows x64.
- Microsoft [.NET 10 Desktop Runtime](https://dotnet.microsoft.com/en-us/download/dotnet/10.0), x64.
- The four supported hologram material files must be stock before the first
  installer run. The installer refuses unknown or previously modified bytes
  instead of overwriting them.

## Installation

1. Download the complete `BurningTertium.zip` release and extract the
   **entire** archive into one folder.
2. Close Darktide. Start `BurningTertium.Installer.exe` and select the
   `Warhammer 40,000 DARKTIDE` folder if it was not found automatically.
3. Choose **Install**. The installer verifies the build, executable, DML/DMF,
   every stock input and every payload hash before changing anything, backs
   up the originals, and adds `BurningTertium` to `mods/mod_load_order.txt`.
4. Start Darktide and walk to the mission table in the Mourningstar.

Keep the installer DLLs and `payload/` beside the EXE. The release contains
only the changed bytes (insert records); stock game data is copied from your
own verified installation and is never redistributed.

### In-game commands

| Command | Effect |
|---|---|
| `/bt_flames fire` | Fire-grenade fire on every 3rd roof, smoke on every 6th (default) |
| `/bt_flames fire2` / `fire3` | Alternative stock ground fires |
| `/bt_flames smoke` | Smoke only |
| `/bt_flames 1`–`20` | Fire on every N-th roof in the current mode |
| `/bt_flames off` / `status` | Turn off / show count |

### Repair, update and uninstall

Close Darktide and run the **same release**. **Repair** restores missing or
overwritten owned files. After a Darktide patch, **Repair after update**
re-applies the release only if every managed file still matches a known stock
or BurningTertium hash; otherwise it stops before writing and a new release is
required. **Uninstall** restores the exact original materials from the
backups, removes the mod folder and removes only its own load-order line.
Backups and receipts live under `%LOCALAPPDATA%\BurningTertium\`.

### Lua-only installation

Copying only the `BurningTertium` mod folder (for example through a mod
manager) gives the rooftop fire over the stock green hologram. The red
hologram always requires the installer.

## Compatibility

The installer manages different files from RainbowFlame and RainbowBarrels
(four `bundle/data` hologram material streams plus its own mod folder), and
each installer edits only its own load-order line. RainbowBarrels recolours
`liquid_area/fire_lingering` only while a real liquid area is being filled, so
BurningTertium's rooftop effects are not recoloured by it.

## Development

`scripts/` is the DMF mod. `installer/` holds the installer, its tests and the
payload generator (`tools/BurningTertium.PayloadGenerator`), which builds
`payload/` from SHA-pinned stock backups and the in-game-tested outputs in the
local, ignored `analysis/` tree. `resource/` contains the reproducible offline
research and authoring scripts; [RESEARCH.md](RESEARCH.md) records the build,
evidence, rejected approaches and test limits. See [LICENSE](LICENSE) and
[NOTICE](NOTICE).
