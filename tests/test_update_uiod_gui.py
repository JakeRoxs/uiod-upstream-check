from unittest import TestCase, main
from tempfile import TemporaryDirectory
from pathlib import Path

from scripts import update_status_badges
from scripts import update_uiod_gui


class TestUpdateUiodGui(TestCase):
    def test_remove_pause_clicksound_with_comments_and_whitespace(self):
        upstream = """buttonType = {
    name = "start_stop_icons"
    clicksound = \"ui_click_pause\"
    clicksound = \"ui_click_pause\"  # pause sound
    clicksound = \"ui_click_play\"
    alwaysTransparent = yes
}\n"""
        patched = update_uiod_gui.apply_spacebar_pause_patch(upstream, remove_pause_clicksound=True)

        self.assertNotIn('clicksound = "ui_click_pause"', patched)
        self.assertIn('clicksound = "ui_click_play"', patched)

    def test_inserts_frame_and_shortcut_in_start_stop_icons_block(self):
        upstream = """buttonType = {
    name = "start_stop_icons"
    alwaysTransparent = yes
}\n"""
        patched = update_uiod_gui.apply_spacebar_pause_patch(upstream)

        self.assertIn('frame = 1', patched)
        self.assertIn('shortcut = "SPACE"', patched)
        self.assertNotIn('alwaysTransparent = yes', patched)

    def test_raises_when_start_stop_icons_missing(self):
        upstream = """buttonType = {
    name = "other_button"
    alwaysTransparent = yes
}\n"""
        with self.assertRaisesRegex(ValueError, "Could not find the start_stop_icons pause button"):
            update_uiod_gui.apply_spacebar_pause_patch(upstream)

    def test_raises_when_buttontype_block_missing(self):
        upstream = """name = "start_stop_icons"
    alwaysTransparent = yes
}\n"""
        with self.assertRaisesRegex(ValueError, "Could not find the start_stop_icons buttonType block start"):
            update_uiod_gui.apply_spacebar_pause_patch(upstream)

    def test_raises_when_alwaystransparent_missing(self):
        upstream = """buttonType = {
    name = "start_stop_icons"
    frame = 1
}\n"""
        with self.assertRaisesRegex(ValueError, "Could not find alwaysTransparent = yes in the start_stop_icons buttonType block"):
            update_uiod_gui.apply_spacebar_pause_patch(upstream)

    def test_writes_full_mod_stack_gui(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = {
                "mod_path": str(root / "mods" / "Example Mod"),
                "upstream_file": "interface/main.gui",
            }

            target = update_uiod_gui.write_full_mod_stack(config, "patched\n")

            self.assertEqual((root / "mods" / "Example Mod" / "interface" / "main.gui"), target)
            self.assertEqual("patched\n", target.read_text(encoding="utf-8"))


class TestUpdateStatusBadges(TestCase):
    def test_formats_timestamp_version_as_utc_date_time(self):
        self.assertEqual(update_status_badges.timestamp_version(1767225600), "2026.01.01.0000")

    def test_reads_uiod_version_from_workshop_acf_timeupdated(self):
        acf = '''"AppWorkshop"
{
    "WorkshopItemsInstalled"
    {
        "1623423360"
        {
            "timeupdated" "1767225600"
        }
    }
}
'''
        with TemporaryDirectory() as directory:
            path = Path(directory) / "appworkshop_281990.acf"
            path.write_text(acf, encoding="utf-8")

            version = update_status_badges.uiod_version_from_workshop_acf(path, "1623423360")

        self.assertEqual(version, "2026.01.01.0000")

    def test_reads_uiod_version_from_descriptor_mod_version(self):
        descriptor = '''name="UI Overhaul Dynamic"
version="4.4.*"
supported_version="v4.4.*"
remote_file_id="1623423360"
'''
        with TemporaryDirectory() as directory:
            path = Path(directory) / "descriptor.mod"
            path.write_text(descriptor, encoding="utf-8")

            version = update_status_badges.uiod_version_from_descriptor(path)

        self.assertEqual(version, "4.4.*")

    def test_reads_stellaris_version_from_descriptor_supported_version(self):
        descriptor = '''name="UI Overhaul Dynamic"
version="4.4.*"
supported_version="v4.4.*"
remote_file_id="1623423360"
'''
        with TemporaryDirectory() as directory:
            path = Path(directory) / "descriptor.mod"
            path.write_text(descriptor, encoding="utf-8")

            version = update_status_badges.stellaris_version_from_descriptor(path)

        self.assertEqual(version, "v4.4.*")

    def test_file_fallback_uses_content_hash_instead_of_workshop_id(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "main.gui"
            path.write_text("gui content", encoding="utf-8")

            version = update_status_badges.uiod_version_from_file(path)

        self.assertRegex(version, r"^sha-[0-9a-f]{12}$")

    def test_renders_badge_group_from_metadata_fields(self):
        index = {
            "badges": [
                {
                    "id": "version",
                    "label": "Version",
                    "metadata_field": "version",
                    "source": "metadata version",
                    "logic": "version logic",
                    "color": "blue",
                },
                {
                    "id": "sync_status",
                    "label": "Sync",
                    "metadata_field": "sync_status",
                    "source": "metadata sync_status",
                    "logic": "sync logic",
                    "color": "brightgreen",
                },
            ],
        }
        metadata = {"version": "1.2.3", "sync_status": "synced"}

        section = update_status_badges.render_badge_section(index, metadata)

        self.assertIn("![Version: 1.2.3](https://img.shields.io/badge/Version-1.2.3-blue)", section)
        self.assertIn("![Sync: synced](https://img.shields.io/badge/Sync-synced-brightgreen)", section)
        self.assertNotIn("| Badge |", section)

    def test_renders_badge_docs_from_index(self):
        index = {
            "docs_heading": "Status Badges",
            "badges": [
                {
                    "id": "version",
                    "label": "Version",
                    "metadata_field": "version",
                    "source": "metadata version",
                    "logic": "version logic",
                    "color": "blue",
                },
                {
                    "id": "sync_status",
                    "label": "Sync",
                    "metadata_field": "sync_status",
                    "source": "metadata sync_status",
                    "logic": "sync logic",
                    "color": "brightgreen",
                },
            ],
        }

        docs = update_status_badges.render_badge_docs(index)

        self.assertIn("# Status Badges", docs)
        self.assertIn("| Version | `version` | metadata version | version logic |", docs)
        self.assertIn("| Sync | `sync_status` | metadata sync_status | sync logic |", docs)

    def test_replaces_existing_generated_section(self):
        index = {
            "start_marker": "<!-- status-badges:start -->",
            "end_marker": "<!-- status-badges:end -->",
        }
        readme = "# Title\n\n<!-- status-badges:start -->\nold\n<!-- status-badges:end -->\n\n## Next\n"

        updated = update_status_badges.replace_generated_section(readme, index, "new")

        self.assertIn("<!-- status-badges:start -->\nnew\n<!-- status-badges:end -->", updated)
        self.assertNotIn("old", updated)


if __name__ == "__main__":
    main()
