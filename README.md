# UIOD Upstream Check

This repository monitors three UI Overhaul Dynamic Steam Workshop mods and regenerates the Multiplayer Spacebar Pause GUI files when upstream changes are detected.

<!-- status-badges:start -->
![Version: 2026.07.10.2112](https://img.shields.io/badge/Version-2026.07.10.2112-blue) ![UIOD: 4.4.*](https://img.shields.io/badge/UIOD-4.4.%2A-purple) ![Stellaris: v4.4.*](https://img.shields.io/badge/Stellaris-v4.4.%2A-informational) ![Sync: synced](https://img.shields.io/badge/Sync-synced-brightgreen)
<!-- status-badges:end -->

## What This Produces

The repository keeps committed copies of both upstream baselines and generated patched files:

- `vendor/...` stores the current upstream GUI files downloaded from Steam Workshop.
- `patched/...` stores generated GUI files with the Multiplayer Spacebar Pause patch reapplied.
- `badges/` stores generated status metadata, badge definitions, and badge documentation.

The GitHub Actions workflow refreshes these files and opens or updates a pull request when the committed outputs differ from the latest upstream state.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `variants.json` | Metadata for the supported UIOD variants and their generated output paths. |
| `vendor/` | Vendored upstream GUI files downloaded from Steam Workshop. |
| `patched/` | Generated patched GUI files. |
| `scripts/` | Update, verification, and badge generation scripts. |
| `badges/` | Badge definitions and generated metadata. |
| `.github/workflows/` | Scheduled upstream check workflow. |

## Variants

Variant metadata lives in `variants.json`.

| Variant       | Upstream Workshop item                                                                        | Published patched mod                                                                              | Upstream file               | Generated patch                                                        |
| ------------- | --------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------------- | ---------------------------------------------------------------------- |
| `uiod`        | [UIOD `1623423360`](https://steamcommunity.com/workshop/filedetails/?id=1623423360)           | [UIOD + MP Spacebar Pause `3759229377`](https://steamcommunity.com/sharedfiles/filedetails/?id=3759229377) | `interface/main.gui`        | `patched/uiod-plus-mp-spacebar-pause/interface/main.gui`               |
| `uiod-et`     | [UIOD ET `1780481482`](https://steamcommunity.com/sharedfiles/filedetails/?id=1780481482)     | [UIOD ET + MP Spacebar Pause `3759229978`](https://steamcommunity.com/sharedfiles/filedetails/?id=3759229978) | `interface/main_topbar.gui` | `patched/uiod-et-plus-mp-spacebar-pause/interface/main_topbar.gui`     |
| `uiod-etfdlc` | [UIOD ETFDLC `3090328185`](https://steamcommunity.com/sharedfiles/filedetails/?id=3090328185) | [UIOD ETFDLC + MP Spacebar Pause `3759228189`](https://steamcommunity.com/sharedfiles/filedetails/?id=3759228189) | `interface/main_topbar.gui` | `patched/uiod-etfdlc-plus-mp-spacebar-pause/interface/main_topbar.gui` |

## Patch Logic

`scripts/update_uiod_gui.py` applies the Multiplayer Spacebar Pause patch by:

- Replacing `alwaysTransparent = yes` in the `start_stop_icons` button with `frame = 1` and `shortcut = "SPACE"`.
- Removing `clicksound = "ui_click_pause"` only for the base `uiod` `interface/main.gui` variant. This behavior is retained because the base UIOD variant requires it for the spacebar shortcut to work reliably in tested multiplayer scenarios.

## Prerequisites

- Python 3.11 or newer. The scripts use only the Python standard library.
- SteamCMD for full upstream refreshes through GitHub Actions or equivalent local automation.
- Already downloaded Steam Workshop files when running local regeneration commands without SteamCMD.

## GitHub Actions

`.github/workflows/check-uiod-upstream.yml` runs every twelve hours, can be run manually, and reruns on pushes to `main` after merges.

The workflow:

1. Downloads all three workshop items with SteamCMD.
2. Updates `vendor/...` with the current upstream GUI files.
3. Regenerates `patched/...` with the spacebar pause patch reapplied.
4. Verifies every generated patched file can be recreated from its vendored baseline.
5. Refreshes the README badge line and `badges/README.md` from `badges/index.json` and `badges/metadata.json`.
6. Opens or updates a pull request only when generated files changed.

SteamCMD and downloaded workshop content are cached in `.steamcmd-cache` between workflow runs. The workflow still uses SteamCMD `validate` so cached workshop items are checked and updated when Steam has newer content.

## Common Workflow

1. Check generated files with `python scripts/update_uiod_gui.py --check-generated --all`.
2. If generated files are stale, regenerate the affected variant from its downloaded upstream GUI file.
3. Refresh badges with `python scripts/update_status_badges.py`.
4. Review changes under `vendor/`, `patched/`, and `badges/`.

## Failure Modes

- If the `start_stop_icons` block changes enough that `scripts/update_uiod_gui.py` cannot patch it safely, the workflow fails instead of guessing.
- If Steam has newer workshop content, SteamCMD `validate` can refresh cached workshop files before generation runs.
- Pull requests are opened or updated only when vendored files, generated patches, or badge metadata change.

## Local Commands

Check all generated patched files without Steam:

```powershell
python scripts/update_uiod_gui.py --check-generated --all
```

Regenerate one variant from an already downloaded upstream file:

```powershell
python scripts/update_uiod_gui.py "<steam-workshop-path>\281990\1623423360\interface\main.gui" --variant uiod --update
```

Verify a local mod file matches upstream plus the patch:

```powershell
python scripts/update_uiod_gui.py "<steam-workshop-path>\281990\1623423360\interface\main.gui" --variant uiod --local-main-gui "..\UIOD + MP Spacebar Pause\interface\main.gui"
```

Refresh the README badge line and badge documentation from existing metadata:

```powershell
python scripts/update_status_badges.py
```

Set this repository's internal badge version to the current UTC date/time:

```powershell
python scripts/update_status_badges.py --version-now
```

Refresh the UIOD badge from the downloaded mod descriptor version, falling back to Steam workshop metadata and then a vendored file content hash:

```powershell
python scripts/update_status_badges.py --uiod-descriptor ".steamcmd-cache/content/steamapps/workshop/content/281990/1623423360/descriptor.mod" --workshop-acf ".steamcmd-cache/content/steamapps/workshop/appworkshop_281990.acf" --uiod-file-fallback vendor/uiod/1623423360/interface/main.gui
```
