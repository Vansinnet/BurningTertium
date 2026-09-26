# BurningTertium

BurningTertium sets the Tertium hologram above the Mourningstar mission table
on fire. The projected city turns saturated red, and real, animated fire
burns on its rooftops with drifting smoke. Only the hologram on the mission
table changes; other screens, lights and holograms, gameplay, missions and
networking are untouched.

## What is changed

- **Red hologram:** four hologram material streams are redirected: the city,
  sides, base and grid. The city shader's own hardcoded green light and green
  base gradient are mirrored to red, so no green remains. Transparency,
  scanlines and city detail are preserved.
- **Fire:** the DMF mod places Darktide's own lingering fire-grenade fire on
  verified rooftop positions of the hologram's city model and keeps it
  burning. It loads the stock effect packages itself; no fire resources are
  modified.

## Requirements

- Darktide Mod Loader (DML) and Darktide Mod Framework (DMF).
- Windows x64; the four original material streams must match the stock
  SHA-256 hashes for Steam build `24735202` (Darktide `1.3.770.210`).
  After a game update, any changed material falls back to its stock appearance.

## Installation

1. Download `BurningTertium.zip` from the latest GitHub release. Extract it
   into the game's `mods` directory, so you have
   `mods/BurningTertium/BurningTertium.mod`. Keep the entire `BurningTertium`
   folder together, including `bin/`, `payload/` and `scripts/`.
2. Add `BurningTertium` to `mods/mod_load_order.txt`, or install and enable the
   ZIP with your mod manager. Start Darktide and visit the Mourningstar mission
   table. No separate installer or .NET runtime is needed.

The redirect library checks each original material's SHA-256 before serving a
replacement. The standalone mod does not change files under `bundle/`. The
four full replacement materials and the Asset Redirect v2 library/DLL are
included in the ZIP. Use `/asset_redirect` and the log to check redirect status.
If a material reports `restart_required`, restart the game.

### In-game commands

| Command | Effect |
|---|---|
| `/bt_flames fire` | Fire-grenade fire on every 3rd roof, smoke on every 6th (default) |
| `/bt_flames fire2` / `fire3` | Alternative stock ground fires |
| `/bt_flames smoke` | Smoke only |
| `/bt_flames 1`–`20` | Fire on every N-th roof in the current mode |
| `/bt_flames off` / `status` | Turn off / show count |

### Updating and uninstalling

If upgrading from an installer-based 1.0.x release, close the game and run
that release's **Uninstall** first to restore its four original game files.
Then install this ZIP as above. Back up any settings you want to keep before
using the old uninstaller. For future updates, replace the
`mods/BurningTertium` folder. To uninstall this version, remove its folder
and its load-order entry.
After a game update, the redirect library skips any material whose stock hash
has changed; an updated mod is needed to restore that part of the red hologram.
If a separate development trial changed the four `bundle/data` files, restore
it with that trial's rollback before using this version.

## Compatibility

The redirect owns four hologram material streams and does not edit them on
disk. RainbowBarrels recolours `liquid_area/fire_lingering` only while a real
liquid area is being filled, so BurningTertium's rooftop effects are not
recoloured by it. See [LICENSE](LICENSE), [NOTICE](NOTICE) and
[CHANGELOG.md](CHANGELOG.md).
