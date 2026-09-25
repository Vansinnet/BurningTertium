# BurningTertium: Mourningstar table investigation

## Release 1.0.0 packaging — 2026-09-25

**Status.** The user confirmed the re-lit `fire` mode works ("fungerar fint").
Release scope: the four red hologram materials plus the Lua mod with stock
fire/smoke modes only. The candle hub-bundle variant, the large-flame and
procedural-fire candle streams (`author_fire_*`, `fire_dsl.py`, `fire_model.py`,
`local_fire_flame_trial.py`; offline only, never installed) are superseded and
**not** part of the release; the `candle` mode was removed from the Lua because
its effect exists only with the 124 MB modified hub bundle.

**Why an installer at all.** Runtime material variables cannot fix the colour:
the green light gain and base gradient are hardcoded in pixel program
`1d465925213c`, and a safe runtime handle to the level's hologram unit was
never established (the broad unit scan crashed). The fire itself needs no
game-file change.

**Installer.** `installer/` is a port of the RainbowFlame 1.2.0 installer
(journals, backups, Repair after update, load-order line). The payload generator
builds COPY/INSERT recipes from the pinned stock backups in
`analysis/local-red-trial-20260923T203209Z-d11ff686/` and the tested outputs
`5d1fcc93…` (hologram), `6541de8e…` (side), `3250e754…` (bottom), `eed51d39…`
(grid); inserts total about 174 KB and contain no complete stock file.
Validation in this sandbox (.NET 10.0.401 on Linux, `EnableWindowsTargeting`):
build without warnings; 22/23 installer tests pass — the Windows reparse-point
fixture cannot be created on Linux; a real-payload end-to-end run on a fixture
game root made of the stock material bytes installed all nine files with the
expected hashes, repaired, uninstalled back to the exact stock bytes and removed
only its own load-order line. The WinForms UI and a real game install are not
tested.

**Local machine.** The development trials are still installed on the author's
PC and are not installer-owned. `resource/restore_local_trials.py --check` /
`--restore` undoes them in the required order (Lua revisions → Lua deployment →
hologram shader → four materials → large flame → candle hub bundle) before the
installer can be run there.

## Real fire instead of candle billboards — 2026-09-24 (late)

User confirmed after the shader trial: the city is clearly red and "super
snyggt"; the 180 candle billboards should become real flames.

**Offline evidence.** The stock hub bundle's 28 particle registrations (names
resolved with the pinned public dictionary, SHA-256 `33cc674d…`) contain no real
fire — only `candle_flame_01`. `bundle_database.data` shows that particle
resources such as `content/fx/particles/enemies/buff_burning` are **their own
packages** (bundle file = murmur64 of the name, e.g. `bundle/3d574968047de622`
with the particle, 3 streamed textures and 12 materials). Darktide itself loads
resource names as packages (`DecalManager` loads unit names via
`Managers.package:load(name, "DecalManager")`). `PackageManager.load/
has_loaded_id/release` were read in local `darktide-source` 1.12.4 (identical to
the 1.12.5 public copy used for search).

**Change (Lua only).** `BurningTertium.lua` now has three modes:
`fire` (default, stock `buff_burning` — the looping fire on burning enemies),
`pilot` (`zealot_flamer_pilot_light`) and `candle` (the previous red hologram
candle). Package effects are loaded with reference `BurningTertium` before
spawning, polled with `has_loaded_id`, and released in `cleanup()` after owned
particles are destroyed. `/bt_flames fire|pilot|candle [N]` uses every N-th
of the 180 verified roofs (fire default N=2, i.e. 90). Placements, batching,
hub gating and off/status are unchanged. Stock fire scale is 1.

Validation: `luac5.4 -p` passed; LuaLS 3.18.2 (Linux) with types, dmf-source
and `darktide-source/scripts/foundation` (the full source OOM-killed LuaLS in
this sandbox) reports only `DEDICATED_SERVER` undefined, identical to the
unchanged baseline under the same reduced library. The canonical Windows
`tools\validate.ps1` has not been run.

Installed after user-confirmed game closure: only the deployed
`BurningTertium.lua` (`9bdde7b4…` → `7c1629f0…`), backup and manifest in
`analysis/local-fire-lua-20260924T204422Z-98cfc880/`. Fire size at scale 1,
look, FPS cost and package release on hub exit are untested in game.

**In-game result (user screenshot):** with `buff_burning` only smoke and embers
appeared — no flames. Cause from source: `burning_settings.lua` spawns
`buff_burning` with `material_emission = true`, and `BuffExtensionBase`
then calls `World.set_particles_surface_effect(world, id, unit, ...)`, so its
flames are emitted from the burning enemy's mesh surface. Free-standing, only
the non-surface emitters (smoke, embers) remain. `buff_burning_stack_lvl02/03`
have no `material_emission` (node-linked only). The user liked the smoke.

Revision (installed after user-confirmed closure, `7c1629f0…` → `1cd6a383…`,
backup `analysis/local-fire-lua-20260924T210139Z-939d20cc/`): layered modes —
`fire` = `buff_burning_stack_lvl03` every 2nd roof + `buff_burning` smoke every
6th roof; `fire2` = the same with `stack_lvl02`; `fuse` = `cultist_flamer_fuse_loop`
every 3rd; `smoke`; `candle`. `/bt_flames N` alone changes the flame-layer
spacing for the current mode. luac and LuaLS (same reduced library) show no new
diagnostics. Visible flames are not yet observed.

**In-game result (2026-09-25, user screenshot):** `stack_lvl03` produced only
glowing embers on one side, no real flames.

Next revision (installed after user-confirmed closure, `1cd6a383…` →
`20a3695a…`, backup `analysis/local-fire-lua-20260925T150514Z-949633be/`):
liquid-area fire cells, which the game itself spawns free-standing with
`World.create_particles(world, vfx_name_filled, position, rotation)` in
`liquid_area_extension.lua` / `husk_liquid_area_extension.lua` /
`liquid_area_drawer.lua` (no unit link or surface). Modes: `fire` =
`fire_grenade_player_lingering_fire` (bundle `83abc9987ace18ee`), `fire2` =
`liquid_area/fire_lingering`, `fire3` = `promethium_fire_lingering`
(`a35c9515dabf894b`), each every 3rd roof plus `buff_burning` smoke every 6th.
These packages also contain `content/fx/units/fx_fire_decal_ground_01`; a scorch
decal on the table/hologram is possible. Stage-2 stack modes were removed.
Visible flames, size and FPS are pending.

**In-game result (2026-09-25):** `fire` (player fire-grenade lingering fire)
shows real flames across the city; the user called the look "precis perfekt".
The flames end after about 10 s — the effect has a finite lifetime like its
grenade. Revision: each flame layer with `renew = 7` re-lights at the same roof
every 7 s while the old instance burns out (overlap, no gap). First renewals are
staggered randomly across 3.5–7 s. Ended IDs are pruned only on frames where a
renewal happened; cleanup still destroys every owned ID. Installed after
user-confirmed closure (`20a3695a…` → new hash in the manifest), backup
`analysis/local-fire-lua-20260925T151054Z-6160ffb8/`. Continuous burning and
long-run FPS are pending.

## Procedural fire flames — 2026-09-24 (late evening)

**Hologram result observed.** After the shader-color trial the user reported
the hologram "verkligen supersnyggt" with a Mourningstar screenshot: the city,
grid and base read saturated red, no green remains at the base, scanlines and
transparency are intact, and the 180 roof flames are still in place. The
flames still read as static candle teardrops (pale warm core). The user asked
for real flames next.

**Stock candle path (offline).** Pixel program `21e48952b7d5` is additive
(alpha output 0): a distortion-noise sample offsets the lookup into a
teardrop mask, and the mask indexes an RGB ramp. Vertex `7dea7622bcc3`
writes `CUSTOM3 = (0.5 - 0.5*cx, 0.5 + 0.5*cy)` (billboard UV, `cy` along the
tangent) and `CUSTOM1` = tiled UV + per-particle random (`TEXCOORD5`) + time
scroll. The Linux no-op rebuild reproduces the Windows candle no-op
`a2be5e45…` byte for byte.

**Change.** `resource/fire_model.py` defines procedural fire (value-noise with an
ALU-only hash, 2 octaves rising over time, sideways sway, narrowing envelope,
noise-eroded tongues, per-particle flicker, colour ramp red → orange → yellow
with a small white core) from only already-used inputs (`CUSTOM3.xy`,
`CUSTOM1.xy` as per-particle seed, `CUSTOM0.w` fade, `time` wrapped every
1000 s). "Up" is taken from the screen-space `ddy` of `CUSTOM3.y`, so it does
not depend on the unverified tangent/texture orientation. `resource/fire_dsl.py`
evaluates the same graph in numpy (`resource/preview_fire.py` →
`analysis/fire-flame-shader-24735202/preview.gif`; synthetic red background) and
emits the DXIL. `resource/author_fire_shader.py` replaces only the three RGB
store values (511 added instructions); alpha output, texture/feedback paths
and ISG1/OSG1/SFI0/PSV0 are unchanged; DXC validation passed. Program SHA-256
`35c97e68bddb0d35f4b51fcbf35b4b8fbd863b77679f90bb7b761d44ead2dad6`.

`resource/author_fire_material.py` swaps only that program (replacing
red_holographic `751a24ec…`) in the installed large-flame material `d0581de7…`;
the two sixfold vertex programs, the discard pass `d02b57bf…` and material
parameters are unchanged, so the accepted size and placement stay.
Candidate `analysis/fire-flame-material-24735202/fire_flame.material.candidate`,
69,500 bytes, SHA-256
`10085308e43f3a7b6b053cb821bac5296680b01636f962fe36a0186f7efcf6aa`.
`resource/local_fire_flame_trial.py` replaces only `bundle/data/03/03ecd13324afc322`
(`d0581de7…` → `10085308…`); restore it before the large-flame and candle trials.
The Lua controller is unchanged. Brightness (gain 1.1), exact look and GPU cost
are untested in game; the discard-only pass still uses the stock teardrop mask.


## Hologram color root cause — 2026-09-24 (evening)

**Cause of the copper/orange city and the green base (offline evidence).**
The city's color pixel program `1d465925213c` (material `hologram`, frames 1
and 9) contains two hardcoded green terms that no material variable reaches:

* a bottom gradient `lerp((0.1, 0.4, 0.1), scan * base_color,
  saturate((CUSTOM0.z * 11)^0.3))` — the stock `hologram_bottom` green is baked
  into the city shader, so the lowest part of the projection stays green
  whatever `base_color` is;
* a fake light multiplied per channel into the final color:
  `(0.16, 0.72, 0.32) * max(dot(N, L), 0) + (0.08, 0.36, 0.16)`.

The second term gives green 4.5x the gain of red. With the installed red
parameters `(0.15, 0.0075, 0.003)` the linear output ratio R:G is 4.4:1 at every
angle — orange/copper after tonemapping — while the base region evaluates to
about `(0.024, 0.432, 0.048)`, i.e. strongly green. Changing `base_color` further
cannot fix either. Only this program (of all main/side/bottom/grid pixel
programs) contains per-channel color constants; fog in-scattering is added
after these terms and was left untouched. The hologram unit record has no light
color, and the world level record contains no green 0-1 float triplets, so no
separate hologram light was found.

**Change.** `resource/author_holo_main_shader.py` swaps only the red and green
operands of those eight instructions (blue, alpha, scanline, distance fade and
fog are unchanged). Bottom becomes `(0.4, 0.1, 0.1)` and the light
`(0.72, 0.16, 0.32)n + (0.36, 0.08, 0.16)` — the stock design mirrored into red.
Modelled city R:G becomes 90:1. `resource/author_holo_main_material.py` builds on the
installed red-parameter material (`4ceb5c…`) and replaces frames 1 and 9 with
stored frames; all other 14 frames, the parameter block, shader defaults and
tail are unchanged. Outputs:

* `analysis/red-holo-main-shader-24735202/` — red program SHA-256
  `de751017f73fb8619f382147c61226e8a5560cc3051e88d8bffa91172420027d`
  (no-op `6398c52b…`); DXC validation passed with signature chunks unchanged.
* `analysis/red-holo-main-material-24735202/hologram.material.candidate`,
  133,912 bytes, SHA-256
  `5d1fcc93ee8e9e951ab874ddd1298751cb6c157b528090652cfdfcd3d0850250`.

`resource/verify_holo_main_material.py` independently decodes stock vs candidate:
only frames 1 and 9 differ, their disassembled function body differs from stock
in exactly the eight intended instructions (control-flow hint IDs renumbered,
values equal), and only the two known color parameters differ from stock.

**Toolchain.** This session had no shell on the Windows PC, so the build ran on
Linux: conda-forge `directx-shader-compiler-1.9.2602.24` via
`resource/dxc_linux.py` (same COM slots as `dxc_api.py`) and `pyooz` 0.0.8
for Kraken decoding. Cross-checks: the Linux `-dumpbin` of `1d465925213c` is
byte-identical to the pinned Windows v1.9.2607 dump; the Linux no-op rebuild
of grid program `903327e46fdd` reproduces the Windows no-op SHA-256
`1fad4201…`; and `material_repack.py` (adapted from `author_grid_material.py`,
plus relocation of the non-empty shader-default block this material has)
reproduces the installed, game-accepted grid candidate `eed51d39…` byte for
byte. pyooz decoding reproduces all pinned program hashes.

**Deployment.** `resource/local_holo_shader_trial.py` (check/install/verify/restore)
replaces only `bundle/data/ba/bacd9b3be2a4c57f`, from `4ceb5c…` to `5d1fcc…`,
with its own backup. Restore it **before** the parent four-material red trial.
Flames, Lua, bundle and the other three materials are untouched. In-game
appearance is not yet observed.

**Installed 2026-09-24 19:51Z** after explicit user approval and user-confirmed
game closure, through the desktop file bridge (no local shell, so the script's
own tasklist/appmanifest checks did not run; the pre-install target was read
back as the owned `4ceb5c…` baseline). Backup `hologram.previous` (`4ceb5c…`)
and manifest are in `analysis/local-holo-shader-20260924T195111Z-3cc70c34/`;
the installed file was read back as `5d1fcc…`. Restore with, game closed:
`python -B "mods\active\BurningTertium\resource\local_holo_shader_trial.py" --restore "mods\active\BurningTertium\analysis\local-holo-shader-20260924T195111Z-3cc70c34\manifest.json"`.
Engine acceptance and appearance in Mourningstar are pending.


## Current rooftop implementation — 2026-09-24

**User screenshot after rooftop deployment:** many flame shapes are visibly
distributed across the lower buildings and the central tower at different
heights. This supports visible operation and broad rooftop coverage of the
new controller. It does not count all 180 effects or prove exact contact at
every anchor. The image still shows a copper/orange city, pale warm flame
centres and green at the base. User assessment of final density/appearance,
FPS impact, off/on cleanup and hub-return behavior remains pending.

The user accepted the sixfold geometry trial's flame size and requested many
flames directly on the projected buildings. The active Lua controller now
uses **180 offline-sampled rooftop positions** and exclusively the authored
red effect at the accepted scale 5. It creates at most six effects per
update, with at least 0.04 accumulated seconds between batches, and never
scans world units or raycasts the scene at runtime. Once all positions are
created it performs no per-particle update loop. Owned IDs are cleared on
hub exit/unload or `/bt_flames off`; `/bt_flames roofs` recreates the set and
`/bt_flames status` reports the created count. Previous near/table/stock/red
diagnostic commands and automatic diagnostic logging were removed.

**Geometry evidence:** `resource/roof_geometry.py` reads the pinned
`mission_table_hologram.unit.record` version 115. A structural lead was
`https://gitlab.com/stingray-modding/stingray_reverse_engineering/-/raw/main/hexpats/dt_unit.hexpat`
(repository tree blob `e19c06801465e2d1c0338ffcae69a2e220bfcec7`), with
`includes/stingray_shared.hexpat` (blob `92573135e0fcd83780908d6eaedd37259096ace6`).
The lead is not runtime authority. The target reader verifies six geometry
records, counted stream/channel/index/batch framing and finite mesh bounds.
All eight node transforms are identity, there are no skins or simple animation,
and the three building LODs share the verified `hologram` material-slot hash.

The exact model-linked external stream is
`D:/Steam/steamapps/common/Warhammer 40,000 DARKTIDE/bundle/data/0e/0ec28850be53166b.stream`,
6,637,572 bytes, SHA-256
`68d82d0d753c52d27089a4277f541b22e4a95d1fbc55141f9937032bba6e644b`.
It was read only after checking it is not listed in the known Vortex and
RainbowFlame manifests and is not a symlink. Independent Steam provenance
is not asserted. `resource/roof_stream.py` consumes both stream records
exactly; every vertex/index byte count matches the unit's descriptors.
The highest-detail building mesh has 123,843 HALF4 position vertices and
66,704 indexed triangles. Decoded XYZ extrema match the independently stored
mesh bounds within 0.005 model units.

The level record supplies position `(-0.0008,-155.5007,101.56)`, rotation
approximately `(0,0,1,0.000001)`, and **nonuniform scale `(2,2,1.5)`**.
Roof sampling applies the full quaternion and scale, selecting topmost,
mostly horizontal surfaces above the base. These are actual mesh roofs,
not estimated building heights. Evidence is in
`analysis/roof-placement-refined-24735202.json`.
`resource/verify_roofs.py` independently intersects all building triangles
at the shipped positions: all **180 unique samples are on the topmost
surface within 0.001 m**. It caught one initial sample hidden by an overlapping
upper roof; the generator was refined and verification now passes.
The renderer adds 0.02 m clearance to each anchor. Particle texture/pivot
alignment to the roof remains an in-game visual question.

The controller, new `roof_positions.lua`, localization and manifest pass
canonical LuaLS with zero diagnostics and syntax validation (4 Lua files,
5 syntax files including `.mod`). After confirmed game closure this rooftop
revision was installed and hash-verified under
`analysis/local-flame-deployment-20260924T191636Z-92ba66d0/`, following
verified rollback of the prior four-file diagnostic deployment. All five
runtime files and the load-order backup passed verification. The accepted
large-flame material and its backup also passed their hash check.
Appearance, 180-effect cost, full-set cleanup and hub-return behavior
must be observed. No additional material or bundle edit is needed for this
placement update; the accepted large material remains installed.

Status: **development trial, not a release**. Four red-color material files
are still installed with original backups; screenshots show an orange/copper
cast and some green near the base. A flat world-GUI triangle-flame test was
rejected and rolled back. A new isolated red particle variant has passed
offline checks and is installed; near-rim testing confirmed visible color
variation, but its size remains too small. No finished flame effect, installer or
distributable asset exists yet. `analysis/` holds extracted records,
development candidates, and rollback inputs; do not package that directory.

## Requested appearance

### Geometry-size trial (installed, visual result pending)

The user reported barely any size difference between `/bt_flames near red 5`
and scale 10. This does not prove the engine scale argument is generally ignored.
The two pinned candle vertex programs derive billboard geometry from particle
size inputs (`%62/%63` in `7dea7622bcc3`, `%57/%58` in `b2e1514a28f1`).
`resource/build_large_flame.py` scales those geometry operands sixfold in both
programs while preserving the UV calculations and both pixel programs.
DXC no-op and edited shaders validate with unchanged interface chunks;
material readback verifies both replacements and a byte-identical no-op.
The candidate is under `analysis/large-red-flame-24735202/`, SHA-256
`d0581de73e4886a486763d7cbaf5e957512b60febfd743b774a3cd0053dc5a35`.
Actual size, anchoring, animation and culling are untested. After explicit
user approval and confirmed game closure, the owned added material stream
was replaced and its SHA-256 plus rollback backup verified. The manifest is
`analysis/local-large-flame-20260924T185223Z-f5245f0e/manifest.json`.
Game acceptance of the modified vertices has not yet been observed.
`resource/local_large_flame_trial.py` prepares a one-file trial of the owned
red-flame stream. Restore this installed size trial first, before the
parent candle-bundle trial whose smaller stream hash remains pinned.

### Latest particle trial observation

The approved physical no-op was installed under
`analysis/local-candle-trial-20260924T173238Z-68d33205/`; the user reached
Mourningstar with the same copper/green-base appearance. The trial was then
promoted to the authored variant and new material stream, with hashes verified.
Particle-controller deployment is recorded under
`analysis/local-flame-deployment-20260924T174234Z-fe1710b4/`.
The user supplied a new screenshot and reported **no flames**. This proves
neither particle creation nor the authored shader's visible behavior.

The focused console log
`console-2026-09-24-17.43.20-36e05aaa-ea61-4579-b1ee-a86c9056cde5.log`
confirms DMF initialization and registration of the expected
`mourningstar/world.level` sublevel. No target-specific error was found in
the searched excerpt. The active source now contains temporary diagnostic
logging: one creation-count message and one playing-count message after two
seconds, limited to the six owned particle IDs. That diagnostic revision is
LuaLS/syntax validated and now locally deployed, with installed files and
load-order backup hash-verified under
`analysis/local-flame-deployment-20260924T175909Z-d0e46a38/`.
The previous Lua deployment was restored before installing this revision;
the resource trials remain installed. Its log results are pending. Remove it after identifying the
failure; no broad unit scan or repeated per-frame logging is needed.

The next user-confirmed hub visit produced a partial log observation in
`console-2026-09-24-18.00.11-cf2018f9-296f-4510-99b7-de8e8002e8af.log`:
at 18:00:36.775, `spawn completed: requested=6 created=6`. GameplayStateRun
was entered at 18:00:37.713. Thus six non-nil IDs were returned during
initialization; this does not prove they remained alive or rendered.
The file ended at 18:00:37.791 when inspected, before the expected two-second
diagnostic. The absent second line is inconclusive while live logging may
be buffered. No code or installed-resource change was made on this evidence.

After a new explicit LuaExec-ready confirmation, PID 26832's compact preflight
confirmed BurningTertium present/enabled and `hub`. The live log contained the
missing line at 18:00:38.776: `after 2s: created=6 playing=6`. All six IDs
therefore remained playing at the two-second snapshot, despite no visible
flames reported. The saved log was incomplete; missing creation or immediate
effect termination is not supported by this observation. The session was
read-only, without unit scanning or mutation.

The next source-only diagnostic candidate compares one stock
`candle_flame_01` against the authored red variant, at neighboring positions
with the same scale and height. This isolates the custom resource path from
shared spawning/visibility behavior, rather than guessing another size.
This paired revision passes selected LuaLS and syntax validation. After the
user confirmed game closure, the six-particle diagnostic deployment was
hash-verified and restored, then the paired revision was installed and
hash-verified under
`analysis/local-flame-deployment-20260924T180832Z-03310993/`.
Only the Lua deployment and its owned load-order entry were replaced;
the installed material and bundle trials were not changed. Visual comparison
is pending. The comparison is not a final flame layout.

The user then reported **neither original nor red flame visible**, with a
screenshot. The paired-test log
`console-2026-09-24-18.09.34-3dbf48ae-3d78-4d2a-b3aa-815fab9b7068.log`
records `stock/custom pair: requested=2 created=2` at 18:10:55.084.
This makes a custom-shader-only explanation insufficient; it does not by
itself identify the shared failure. Read-only inspection of the deployed
VFX Swapper `vfx_limiter.lua` found exact-name filtering that includes neither
`candle_flame_01` nor the new effect. The deployed clear_smoke code affects
SmokeFogSystem and smoke-grenade decals, not these particle names. This
rules out those specific paths, not all mod interactions. No code or game
file was changed based solely on this screenshot.

A subsequent explicitly approved read-only session on PID 8444 confirmed
BurningTertium present/enabled and game mode `hub`. `ComponentSystem` held
46 `ParticleEffect` units; a bounded filter of their registered components
found zero whose `_particle_name` equals `candle_flame_01`. No unit positions
were scanned. Package inclusion therefore cannot be treated as evidence of
a live, component-managed stock candle to use as a control.

The active source adds a temporary `/bt_flames` command for the next diagnostic
revision. It clears only owned effect IDs in the current hub and lets the
existing update path recreate the unchanged stock/custom pair on the next
tick. Invoking it normally from chat after loading isolates creation timing;
it makes no shader, scale or placement change. DMF command registration was
verified at `dmf-source/scripts/mods/dmf/modules/core/commands.lua:10-43`;
the existing command types suffice. Selected LuaLS and syntax validation
passed. After the user confirmed game closure, this revision was installed
and hash-verified under
`analysis/local-flame-deployment-20260924T182034Z-17e3aa32/`, following
verified rollback of the previous paired-test Lua deployment. Material and
bundle trials were not changed. The manual respawn result is pending;
timing is a hypothesis, not an established cause. Remove the diagnostic
command/logs after resolution.

Manual timing test: the user reported no flame after `/bt_flames`. In the
explicitly approved read-only session on PID 32088, live logs confirm
manual respawn at 18:22:05.694, `requested=2 created=2` at 18:22:05.702,
and `created=2 playing=2` at 18:22:07.704. Creation during initial loading
alone is therefore not an adequate explanation for missing visibility.
One targeted read of the alive local player's position returned
`(2.0447,-147.0051,101.0130)`, approximately 10.886 m from the stock test
effect. This is a single player lookup, not a world-unit scan.

The next diagnostic revision adds `/bt_flames near` to place
the same stock/custom pair at the near rim around `(2,-148.8007,103.2)`.
Scale stays 5 for both effects; only placement changes. `/bt_flames table`
restores the original comparison positions. Geometry occlusion or small
screen size remains a hypothesis, not proven by the distance measurement.
The revised source passes selected LuaLS and syntax validation. After
confirmed game closure it was installed and hash-verified under
`analysis/local-flame-deployment-20260924T183038Z-ea8ae732/`, following
verified rollback of the prior Lua deployment. The material and bundle
trials were not changed. Near-rim visibility remains untested.

The next screenshot contained a small yellow-white flame-shaped feature high
on the left. The user confirmed seeing this small flame after it was pointed
out. No red flame was identified. This is evidence of a visible flame-like
feature, not yet proof of its ownership by the stock/custom test pair.
The saved log for this session
`console-2026-09-24-18.31.47-1f46d8ea-edfa-422a-808a-26fdc2e6d939.log`
only contained the initial two-ID spawn when inspected; near-command execution
was not yet visible in that buffered file. The next comparison should keep
the camera fixed and alternate existing `/bt_flames table` and
`/bt_flames near` commands to establish whether the visible feature moves
with the owned pair. Do not infer red-shader failure or adjust scale from
the screenshot alone.

The user confirmed the small visible flame disappears with `/bt_flames table`
and returns with `/bt_flames near`. This establishes that at least one of the
owned test effects is visibly rendering near the rim. It does not identify
which of the two effects is visible or demonstrate that the red variant fails.
The next source revision adds `stock`, `red` and `pair` choices plus a bounded
1-20 scale argument. Single-effect stock/red modes use **the exact same first
position**, allowing a controlled material comparison, with chat confirmation
of the selected mode and scale. Initial comparisons should use scale 5 for
both before testing larger values. Selected LuaLS and syntax pass. After
confirmed game closure, this revision was installed and hash-verified under
`analysis/local-flame-deployment-20260924T184136Z-ce09da39/`, following
verified rollback of the prior near/table Lua deployment. The bundle and
material trials were not changed. Single-effect visual comparison remains
pending. Diagnostic controls remain temporary.

Single-effect comparison result: the user ran `/bt_flames near stock 5`
followed by `/bt_flames near red 5` and reported that the first was brighter
and the second changed the flame's color. This supports visible rendering of
both effects at the same near-rim point, and a visible effect from the isolated
authored material. It does not establish final hue, scanline quality, desired
size, table placement or cleanup. Earlier reports of no red flame cannot be
treated as evidence that the authored resource failed to load. Next use the
already installed command's bounded scale argument to compare red 5 with red
10; do not replace resource files just to test scale.

Turn the *whole* projected Tertium city red, including its associated green
projection elements, and add stylized red holographic flames rising from the
city. Limit the effect to the Mourningstar table and retain clean disable,
world-transition, and hot-reload behavior. The city is Tertium; the new mod's
name is BurningTertium.

## Game and static evidence

- Steam app manifest `D:/Steam/steamapps/appmanifest_1361210.acf` reported
  build `24735202`; the running `Darktide.exe` reported `e770210`
  (`1.3.770.210`).
- `darktide-source/scripts/settings/mission/templates/hub_mission_templates.lua`
  identifies the hub level as
  `content/levels/hub/hub_ship/missions/hub_ship`.
- `darktide-source/scripts/ui/views/mission_board_view/mission_board_view_settings.lua`
  lists three **separate mission-board UI** materials: `hologram_02`,
  `hologram_bottom`, `hologram_grid`. Its named hologram unit belongs to a
  viewport world, not to Mourningstar's gameplay world. Do not reuse its unit
  name as a purported hub API.
- The read-only index inspection of `bundle/8aaa27ad87976cf4` confirmed the
  root hub level record at index 35, the
  `content/levels/hub/hub_ship/mourningstar/world` record at index 30, and
  registrations for `hologram_bottom` at index 3839 and `hologram_grid` at
  index 3980. The exact hub bundle SHA-256 was
  `f9ff268a1af54914215aacb88f36643a01cd96840ac1cf769f4e4a3cd3c3ced2`.
  `hologram_02` is registered in the distinct UI bundle
  `bundle/b30a7b3e4b2d5c06` (SHA-256
  `7b6ae5c6f61cb8a9aeefc104526a9be4e139c9434f0ff90a03dc851b09803df2`),
  **not** in the hub bundle. A tested `hologram_01` name hypothesis also did
  not match either index. The hub's actual unnumbered city material is
  identified in the offline update below.
- The exact extracted world-level record was 1,298,870 bytes, SHA-256
  `9b89b1ba12ca8baa6750425d606e64bb005030d12a4b047abe4d5d1195d74cd9`.
  The root level record was 88,422 bytes, SHA-256
  `ef30914b3b4d10da86e8acee73bc635dfab69cfc4d784ba4a64bafc5bc22a6e1`.
  Neither record exposes a plaintext name for the city's hologram unit.
- Hub `hologram_bottom` registration, SHA-256
  `de04216d16440e2a7f53b29e8d326fce02cf5e8aa0641652ee08cc2abb2c58cc`,
  points to `bundle/data/51/51f7e0e66641669b` (84,848 bytes,
  SHA-256 `078ed294f4bab50fa984a035d9c94da4e5521da858c148cc52316f5fcfe448e8`).
  Its version-61 material exposes one vector3 value, approximately
  `(0.1, 0.4, 0.1)`, with name hash `cb577b8f`. The checked, source-evidenced
  parameter names (`color`, `tint_color`, `emissive_color`, `light_color`,
  `emissive_color_intensity`, `color_filter`) did **not** resolve that hash.
  A later targeted check against the material's DXC reflection verified the
  name `base_color`; its visible effect in game remains untested.
- Hub `hologram_grid` registration, SHA-256
  `9524fc7161295a5925ddb52040b8beb553bc46de75aa8c9ceb059ab0cfaf24b7`,
  points to `bundle/data/59/59c4260bff372016` (217,128 bytes,
  SHA-256 `c49cba30643a8c863c2818df51bbf5f761f7dc0cd32c4912b3d51d037e655db4`).
  Its version-61 material has no exposed material variables in the bounded
  parser. That alone does not rule out shader, texture, or inherited rendering
  color contributions.

### Offline identification update

The public hash dictionary at
`https://gitlab.com/qasikfwn/bitsquid-blender-tools/-/raw/dev/bitsquid/murmur/dictionaries/dictionary_hashcat_dt.txt`
was streamed and reduced to target-specific hash matches only. The dictionary
response had 349,084 entries and SHA-256
`33cc674d9fe278ead021761c41a20f4f6bcf61066e045e114755202d99d17d35`.
The matches were independently checked against the **current hub bundle's**
indexed resource type/name identities (not accepted on dictionary authority).

- `content/environment/artsets/imperial/hub/mission_table_hologram` is a
  `unit` resource at hub index 3322 (record SHA-256
  `e8278669c76a6d192865fbed5a31663bd7fb82ce776e52912887d7e8a1bf6383`).
  Its record contains the four material hashes **once each**; the world-level
  record has the unit's hash at offset 584214. This establishes the four
  material dependencies for the hub city without identifying a safe runtime
  object handle or a level-unit ID.
- The city's main material is the unnumbered
  `content/environment/artsets/imperial/hub/mission_board_table_hologram/hologram`,
  hub index 4088, stream `bundle/data/ba/bacd9b3be2a4c57f`, SHA-256
  `e0d63444385473b9b4e299318cd3fdc85e2188f9df9da06ab2224a41654cb616`.
  It has two green-biased vector3 parameters: `base_color` at offset 232 and
  `material_variable_046f8451` at offset 244 in that installed stream.
- The fourth material is `hologram_side`, index 4085, stream
  `bundle/data/97/97b5490a85966a77`, SHA-256
  `28a94fa9b2a988d8dd93925c40e4687091b6e766f57d1c283eab9fddbaa03a03`.
  It and `hologram_bottom` also expose the green-biased `base_color` parameter;
  its name hash `cb577b8f` equals the independently calculated hash of
  `base_color`. The main material's second vector3 hash `8216e41d` equals the
  name reported by the material's shader reflection above. `hologram_grid`
  exposes no material color parameter.
- The full dictionary did not resolve the three source material texture hashes.
  Material shader analysis remains necessary to establish which texture, grid
  shader and lighting contributions remain green. The unique program inventory
  for main and grid has been decoded with hash-pinned Oodle and DXC under
  `analysis/hologram-shaders-24735202/` and
  `analysis/hologram-vertex-24735202/`.

`resource/author_red_materials.py` created offline trial copies of the
main, side and bottom material streams under
`analysis/red-material-trial-24735202/`. It changed only the four
source-identified green-biased vector3 fields to red-biased values and
independently parsed their readback; a bytewise inverse reconstructs every
 source stream. Its shader programs, texture references, unit registration and
 the entire grid material remained untouched in *that first stage*; a separate
 grid-shader material candidate was subsequently authored and installed for
 the color test below. Neither is a release payload. Resource isolation from
 the separate mission-board UI still needs an explicit compatibility check.

### Installed four-material visual trial

The user explicitly approved one local, reversible color test. When Darktide
was closed, `resource/local_red_trial.py --check` verified Steam build
`24735202`, all four original hashes, all four candidate hashes, and absence
from the current Vortex/RainbowFlame ownership lists. `--install` created
four SHA-256-checked original backups and installed the candidates to the
four exact material-stream paths listed in
`analysis/local-red-trial-20260923T203209Z-d11ff686/manifest.json`.
`--verify` checked all eight installed/backup hashes before the user started
the game. This changes four game material files; the Lua mod was not installed
for the color screenshot. To restore the original four materials, close
Darktide completely, then run:

```powershell
python -B "mods\active\BurningTertium\resource\local_red_trial.py" --restore "mods\active\BurningTertium\analysis\local-red-trial-20260923T203209Z-d11ff686\manifest.json"
```

The user initially reported the entire hologram red, then supplied a close
hub screenshot. That screenshot supports visible recoloring of the city and
grid, **but it reads copper/orange rather than a saturated red**, with small
green areas near the bottom. Green near the bottom has not been proven to
come from the hologram itself. Disassembly of its `hologram_bottom` color
pixel program shows `base_color` directly controls RGB after multiplication
by a sampled scalar; the locally installed `base_color` is red-biased.
The adjacent physical table/cogitator unit references
`content/environment/artsets/imperial/materials/misc/cogitator/cogitator_display_01`,
whose installed material contains an independent green-biased vector3
`(0.5, 1.0, 0.78)`. This identifies a plausible separate source for
green on the consoles, not proof that it is the specific visible patch in
the screenshot. That shared display material has not been edited.

The first local deployment of BurningTertium's runtime files was backed up
under `analysis/local-flame-deployment-20260923T210232Z-5472dcf0/`.
The console log confirmed DMF initialized the mod, but no flames appeared.
A target-only read-only LuaExec probe identified a Lua gate typo: the actual
registered sublevel is
`content/levels/hub/hub_ship/mourningstar/world.level`, not the path without
`.level`. After the correction was deployed under
`analysis/local-flame-deployment-20260923T211058Z-84799afe/`, the user's
screenshot showed six oversized, flat red triangular constructs. The user
rejected them; both local GUI deployments and their load-order changes have
now been **restored**, leaving the separate red material trial untouched.

`BurningTertium.mod` now has a replacement Lua controller for an authored
particle effect rather than GUI triangles. Its flame positions are near the
resource-verified level placement `(-0.0008,-155.5007,101.56)` and are
limited to the local hub world. It has passed static LuaLS/syntax checks for
its current stock-particle prototype; the authored effect name has not yet
been deployed or observed in game. Removing the Lua mod alone cannot undo
the four separate installed red material trial files.

### Isolated holographic candle-flame candidate

The same unchanged stock hub bundle contains a persistent candle effect,
`content/fx/particles/environment/candle_flame_01`, at particle index 1652.
Its single billboard cloud references material `bea498ce22b86bf9`, registered
at hub index 4210; the pinned material stream is
`bundle/data/37/3775630fa25a37a0`, SHA-256
`90ff8d9836fcad0ecddc9785122a399ddb7a8dec1e7b63dc88a940459ec4f998`.
Its 4 shader programs contain one color-writing pixel program. An offline DXC
no-op plus red/animated-scanline variant validated with identical SFI0, ISG1,
OSG1, PSV0 signatures and the original alpha path. The new material stream
passes a byte-identical no-op reconstruction, with only that one pixel program
replaced. This is an authored variant, **not** an observed holographic flame.

`resource/build_candle_variant.py` preserves all 4,376 original logical
resources, all 539 earlier compressed chunks, and the original candle particle
and material. It appends exactly two registrations to the hub bundle: a
**new isolated material**
`content/environment/artsets/imperial/hub/burning_tertium/candle_hologram_red`
whose external stream path is `bundle/data/03/03ecd13324afc322`, and a new
particle `content/fx/particles/burning_tertium/hologram_flame_red` with only
its material reference and resource name changed from the stock candle.
The candidate hub bundle SHA-256 is
`23b3d1832fcb4b487227ddb2a236d8e4595985cac9cf30de95fc3a59c8918fb9`;
the new material stream SHA-256 is
`8069dc045f4ecc46b0355c0e03cf314103dabdcde09f0a442b8c9cc8926f335f`.
`resource/verify_candle_variant.py` independently confirms the added
identities and records, unchanged original block bytes, the single material
redirect and only one replaced pixel program. A **physical no-op control**
that changes only the final chunk's storage encoding and none of its 4,376
logical resources is also under `analysis/candle-noop-bundle-24735202/`
(SHA-256 `82a19eea254e8e8c534d10446de8627cc15d3cf099bc78dfd5818c306f7ffddd`).
Neither no-op nor edited hub bundle has been installed or tested by the game.
`resource/local_candle_trial.py` prepares a hash-checked two-stage local test
and rollback, but running its install/promote commands requires separate
explicit approval. Do not equate offline readback with engine acceptance or
visible flames.

The pinned files are not listed as managed outputs by the RainbowFlame manifest
or the current Vortex deployment manifest. The Steam build and these negative
ownership checks do **not** independently verify a Steam-provided stock hash;
treat the bytes as *stock candidates*, never as a verified original when
authoring a replacement. The extraction changed no installed game files.

## Read-only game observation

With Darktide in the regular Mourningstar hub, a LuaExec read-only snapshot
found `Managers.state.game_mode:game_mode_name() == "hub"` and a
`level_world`. The UI-only name `mission_table_hologram_02` was **absent** from
that world. Neither `MissionBoardOutline` nor `ExpeditionHologramTable`
registered units there. The verified `ComponentSystem` reported 29
`Interactable` units, six tagged `mission_board`, arranged around a table
near `(0, -155.5, 101.8)`; these were interaction targets, not the
hologram mesh. All six had zero child units. The checks did not change the
game. The process later exited, invalidating this runtime session. No red
appearance, flames, or cleanup behavior has been observed in game.

On a second game process (`PID 18620`), a new read-only preflight again found
`hub`, `level_world`, and an alive local player. `World.units(level_world)`
returned a count of 7,543. A subsequent source-verified but more expensive
one-shot proximity-filtered read-only query returned transport `EOF`; that
game process then exited. No result from the proximity query was obtained and
no further game-connected probes were attempted. The cause of exit is unknown;
do not repeat that query without a much cheaper, reviewed method and a new
healthy game session.

The user supplied the corresponding crash report: GUID
`2a903cb3-70e2-437e-ae52-7706de36abd9`, engine build identifier
`5ff3df374e5f4b558202ad2f8a63b073da34ffcb`, access violation
`0xc0000005`, read address `0000000000000030`, instruction address
`00007FF7CD395ED7`. `Log File` and `Info Type` were empty in the provided
excerpt; no Lua stack or named engine function was available. The report is
temporally associated with the query, but the offending native call is not
identified. Avoid `World.units`/`Unit.world_position` inspection of arbitrary
hub units through LuaExec, even if `Unit.alive` returns true; read-only does
not guarantee native-code safety. Do not infer a working asset contract from
this crash.

## Remaining proof before implementation

1. Continue the now-identified city's material shader/texture/color path,
   especially `hologram_grid`, and identify a safe runtime level-unit lookup
   or a resource-only replacement. The viewport unit is distinct; do not
   resume the crashed live unit scan.
2. Establish whether color modification can reach *all* projection layers,
   and author and validate a visually holographic flame resource bound to the
   hub table. Avoid recoloring the separate mission-board UI by accident.
3. With fresh authorization and game closed, use the prepared rollback
   manifest to test the **physical no-op** hub bundle first. Only if the normal
   hub loads and renders should the authored material stream and two-record
   bundle be installed for a second acceptance/visibility test. Deployment
   and Lua mod installation remain separate controlled operations.
4. Test actual red scanlined candle appearance, flame placement, animation
   and cleanup in Mourningstar. Inspect the green
   base separately and tune the orange cast before claiming an entirely red
   projection. The red trial's offline materials and Lua renderer must later
   become one verified and reversible mod installation.

## Reproducing the bounded research

`resource/inspect_hologram.py` only reads exact-name bundle indexes.
`resource/extract_hub_level.py --level root` and `--level world` extract one
level record each; `resource/profile_hub.py` inspects the world record.
`resource/extract_holo_materials.py` extracts the verified unit and four
material registrations; `resource/profile_holo_materials.py` inspects their
pinned stream files. `resource/resolve_hologram_names.py` streams the public
dictionary and retains only target-specific matches and SHA-256 provenance.
`resource/inspect_hologram_shaders.py` inspects material shader programs, and
`resource/author_red_materials.py` builds the offline color trial. Extraction
refuses existing output directories. All scripts
read only from the installed game and write development outputs under
`analysis/`; none is a mod installer or a distributable resource builder.
