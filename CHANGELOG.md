# Changelog

All notable release-facing changes to BurningTertium are documented here.

## [1.1.0] - 2026-09-26

### Changed

- Install as a standalone DMF mod folder, including through a mod manager;
  no separate executable installer or .NET runtime is required.
- Serve the four red hologram materials through Asset Redirect v2 without
  modifying game files on disk. Mismatched stock materials fall back to stock.
- The user confirmed the new installation works in game.

## [1.0.1] - 2026-09-25

### Fixed

- Installer window keeps its action buttons accessible at larger text and display scales.
- Local trial rollback preserves later Vortex load-order changes and recognizes fully restored stock files.

## [1.0.0] - 2026-09-25

### Added

- Red Tertium hologram at the Mourningstar mission table: city, sides, base and
  grid materials, including the city shader's hardcoded green light and base
  gradient mirrored to red.
- Rooftop fire on 180 verified roof positions using Darktide's stock lingering
  fire-grenade effect, re-lit every 7 seconds so it never burns out, plus stock
  smoke. Alternative fire and smoke modes via `/bt_flames`.
- Safe Windows installer with build, dependency and hash checks, backups,
  Repair, Repair after update and Uninstall.
