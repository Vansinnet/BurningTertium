# BurningTertium Installer

The .NET 10 x64 WinForms application is a transparent, framework-dependent
installer. It uses only managed .NET APIs and does not use networking, scripts,
shell execution, WMI, elevation, unsafe code, native FFI, packing, or obfuscation.

The UI delegates Install, Repair, Repair after update, and Uninstall to the tested core. The core gates
Steam build `24735202` and executable version `1.3.770.210`, checks that Darktide is
stopped with `Process.GetProcessesByName`, explains missing DML/DMF dependencies,
rejects reparse points and unknown files, reconstructs authenticated COPY/INSERT
deltas, stages on the game volume, writes durable journals, rolls back failures,
and preserves versioned backups under `%LOCALAPPDATA%/BurningTertium/backups`.

The engine, UI and tests are a port of the RainbowFlame 1.2.0 installer with
only the product identity, staging prefixes and owned directories changed.

`Repair after update` permits Steam build and executable-version drift only for an
existing owned installation. Before creating a journal or writing anything, it
requires every managed replacement to match either the known stock input or the
BurningTertium output, and every managed addition to be absent or exact. If an update
changed a required bundle, it stops and requires a new BurningTertium release.

Build and test from this directory:

```text
dotnet build BurningTertium.Installer.sln -c Release
dotnet run --project BurningTertium.Installer.Tests -c Release
dotnet run --project tools/BurningTertium.PayloadGenerator -c Release -- --workspace <workspace-root>
```

The generator reads the SHA-pinned stock backups and tested outputs from the
local, ignored `analysis/` tree (see `Sources` in its `Program.cs`) and writes
`payload/manifest.json` plus `payload/inserts/*.bin`. It refuses unauthenticated
inputs and writes `payload/blockers.json` instead.

Tests create disposable fixtures under the system temporary directory. They never
write to an installed game.
