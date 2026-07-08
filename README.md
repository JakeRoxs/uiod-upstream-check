# UIOD Upstream Check

This repository checks three UI Overhaul Dynamic workshop mods and regenerates the Multiplayer Spacebar Pause GUI files when upstream changes.

## Variants

Variant metadata lives in `variants.json`.

| Variant       | Workshop ID  | Upstream file               | Generated patch                                                        |
| ------------- | ------------ | --------------------------- | ---------------------------------------------------------------------- |
| `uiod`        | `1623423360` | `interface/main.gui`        | `patched/uiod-plus-mp-spacebar-pause/interface/main.gui`               |
| `uiod-et`     | `1780481482` | `interface/main_topbar.gui` | `patched/uiod-et-plus-mp-spacebar-pause/interface/main_topbar.gui`     |
| `uiod-etfdlc` | `3090328185` | `interface/main_topbar.gui` | `patched/uiod-etfdlc-plus-mp-spacebar-pause/interface/main_topbar.gui` |

## Patch

`scripts/update_uiod_gui.py` applies the Multiplayer Spacebar Pause patch by:

- Replacing `alwaysTransparent = yes` in the `start_stop_icons` button with `frame = 1` and `shortcut = "SPACE"`.
- Removing `clicksound = "ui_click_pause"` only for the base `uiod` `interface/main.gui` variant (seems to make it functional for non-host\*?).

\* Needs further testing

If the `start_stop_icons` block changes enough that the script cannot patch it safely, the workflow fails instead of guessing.

## GitHub Actions

`.github/workflows/check-uiod-upstream.yml` runs every twelve hours or can be run manually.

The workflow:

1. Downloads all three workshop items with SteamCMD.
2. Updates `vendor/...` with the current upstream GUI files.
3. Regenerates `patched/...` with the spacebar pause patch reapplied.
4. Verifies every generated patched file can be recreated from its vendored baseline.
5. Opens or updates a pull request only when generated files changed.

SteamCMD and downloaded workshop content are cached in `.steamcmd-cache` between workflow runs. The workflow still uses SteamCMD `validate` so cached workshop items are checked and updated when Steam has newer content.

## Local Commands

Check all generated patched files without Steam:

```powershell
python scripts/update_uiod_gui.py --check-generated --all
```

Regenerate one variant from an already downloaded upstream file:

```powershell
python scripts/update_uiod_gui.py "I:\SteamLibrary\steamapps\workshop\content\281990\1623423360\interface\main.gui" --variant uiod --update
```

Verify a local mod file matches upstream plus the patch:

```powershell
python scripts/update_uiod_gui.py "I:\SteamLibrary\steamapps\workshop\content\281990\1623423360\interface\main.gui" --variant uiod --local-main-gui "..\UIOD + MP Spacebar Pause\interface\main.gui"
```
