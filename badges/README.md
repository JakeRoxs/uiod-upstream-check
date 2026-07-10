# Status Badges

The README displays these badges near the top of the page. They are generated from `badges/index.json` and `badges/metadata.json`.

Run `python scripts/update_status_badges.py` after changing badge definitions or metadata.

| Badge | Metadata field | Source | Logic |
| --- | --- | --- | --- |
| Version | `version` | badges/metadata.json field `version` | Shows this repository's internal date/time version in UTC using YYYY.MM.DD.HHMM format. |
| UIOD | `uiod_version` | badges/metadata.json field `uiod_version` | Shows the upstream UI Overhaul Dynamic version from the downloaded `descriptor.mod` `version` field, with Steam `timeupdated` and vendored-file content hash fallbacks. |
| Stellaris | `stellaris_version` | badges/metadata.json field `stellaris_version` | Shows the Stellaris supported version from the downloaded `descriptor.mod` `supported_version` field. |
| Sync | `sync_status` | badges/metadata.json field `sync_status` | Shows whether the vendored upstream files and generated patched files are in sync after the latest generator run. |
