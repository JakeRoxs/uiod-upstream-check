import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from scripts import update_status_badges
from scripts import update_uiod_gui


START_STOP_GUI = """buttonType = {
    name = "start_stop_icons"
    alwaysTransparent = yes
}
"""


class TestUpdateUiodGuiCoverageWorkflows(TestCase):
    def test_load_manifest_validates_required_fields(self):
        with TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "variants.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "uiod": {
                            "display_name": "UIOD",
                            "workshop_id": "1623423360",
                            "upstream_file": "interface/main.gui",
                            "vendor_path": "vendor/main.gui",
                            "patched_path": "patched/main.gui",
                            "mod_path": "mods/UIOD",
                        }
                    }
                ),
                encoding="utf-8",
            )

            manifest = update_uiod_gui.load_manifest(manifest_path)

            self.assertIn("uiod", manifest)

    def test_load_manifest_rejects_missing_required_fields(self):
        with TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "variants.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "uiod": {
                            "display_name": "UIOD",
                        }
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "vendor_path"):
                update_uiod_gui.load_manifest(manifest_path)

    def test_check_generated_accepts_matching_patched_file(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            vendored_path = root / "vendor" / "main.gui"
            patched_path = root / "patched" / "main.gui"
            vendored_path.parent.mkdir(parents=True)
            patched_path.parent.mkdir(parents=True)
            vendored_path.write_text(START_STOP_GUI, encoding="utf-8")
            patched_path.write_text(
                update_uiod_gui.apply_spacebar_pause_patch(START_STOP_GUI),
                encoding="utf-8",
            )

            result = update_uiod_gui.check_generated("uiod", {}, vendored_path, patched_path)

            self.assertEqual(0, result)

    def test_check_generated_rejects_outdated_patched_file(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            vendored_path = root / "vendor" / "main.gui"
            patched_path = root / "patched" / "main.gui"
            vendored_path.parent.mkdir(parents=True)
            patched_path.parent.mkdir(parents=True)
            vendored_path.write_text(START_STOP_GUI, encoding="utf-8")
            patched_path.write_text("stale\n", encoding="utf-8")

            result = update_uiod_gui.check_generated("uiod", {}, vendored_path, patched_path)

            self.assertEqual(1, result)

    def test_check_full_mod_stack_accepts_matching_descriptor_gui_and_picture(self):
        with TemporaryDirectory() as directory:
            mod_root = Path(directory) / "mods" / "Example"
            target = mod_root / "interface" / "main.gui"
            target.parent.mkdir(parents=True)
            target.write_text("patched\n", encoding="utf-8")
            (mod_root / "descriptor.mod").write_text('picture="thumbnail.png"\n', encoding="utf-8")
            (mod_root / "thumbnail.png").write_text("image", encoding="utf-8")
            config = {
                "mod_path": str(mod_root),
                "upstream_file": "interface/main.gui",
            }

            result = update_uiod_gui.check_full_mod_stack("uiod", config, "patched\n")

            self.assertEqual(0, result)

    def test_check_full_mod_stack_rejects_missing_descriptor(self):
        with TemporaryDirectory() as directory:
            mod_root = Path(directory) / "mods" / "Example"
            target = mod_root / "interface" / "main.gui"
            target.parent.mkdir(parents=True)
            target.write_text("patched\n", encoding="utf-8")
            config = {
                "mod_path": str(mod_root),
                "upstream_file": "interface/main.gui",
            }

            result = update_uiod_gui.check_full_mod_stack("uiod", config, "patched\n")

            self.assertEqual(1, result)

    def test_check_or_update_upstream_update_writes_all_outputs(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            upstream_path = root / "download" / "main.gui"
            vendored_path = root / "vendor" / "main.gui"
            patched_path = root / "patched" / "main.gui"
            mod_root = root / "mods" / "Example"
            upstream_path.parent.mkdir(parents=True)
            upstream_path.write_text(START_STOP_GUI, encoding="utf-8")
            config = {
                "mod_path": str(mod_root),
                "upstream_file": "interface/main.gui",
            }

            result = update_uiod_gui.check_or_update_upstream(
                "uiod",
                config,
                upstream_path,
                vendored_path,
                patched_path,
                None,
                True,
            )

            self.assertEqual(0, result)
            self.assertEqual(START_STOP_GUI, vendored_path.read_text(encoding="utf-8"))
            patched = patched_path.read_text(encoding="utf-8")
            self.assertIn('shortcut = "SPACE"', patched)
            self.assertEqual(patched, (mod_root / "interface" / "main.gui").read_text(encoding="utf-8"))

    def test_check_or_update_upstream_rejects_changed_upstream_without_update(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            upstream_path = root / "download" / "main.gui"
            vendored_path = root / "vendor" / "main.gui"
            patched_path = root / "patched" / "main.gui"
            upstream_path.parent.mkdir(parents=True)
            vendored_path.parent.mkdir(parents=True)
            upstream_path.write_text(START_STOP_GUI, encoding="utf-8")
            vendored_path.write_text(START_STOP_GUI.replace("yes", "no"), encoding="utf-8")

            result = update_uiod_gui.check_or_update_upstream(
                "uiod",
                {},
                upstream_path,
                vendored_path,
                patched_path,
                None,
                False,
            )

            self.assertEqual(1, result)


class TestUpdateStatusBadgesCoverageWorkflows(TestCase):
    def test_load_json_rejects_non_object_root(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            path.write_text("[]", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "JSON root must be an object"):
                update_status_badges.load_json(path)

    def test_workshop_item_metadata_reports_missing_sections(self):
        cases = {
            "missing AppWorkshop": "{}",
            "missing WorkshopItemsInstalled": '"AppWorkshop" { }',
            "missing item": '"AppWorkshop" { "WorkshopItemsInstalled" { } }',
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "appworkshop_281990.acf"
            for name, content in cases.items():
                with self.subTest(name=name):
                    path.write_text(content, encoding="utf-8")

                    with self.assertRaises(ValueError):
                        update_status_badges.workshop_item_metadata(path, "1623423360")

    def test_render_badge_section_requires_badges_and_metadata_fields(self):
        with self.assertRaisesRegex(ValueError, "Badge index"):
            update_status_badges.render_badge_section({}, {})

        index = {
            "badges": [
                {
                    "id": "version",
                    "label": "Version",
                    "metadata_field": "version",
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "missing metadata field"):
            update_status_badges.render_badge_section(index, {})

    def test_replace_generated_section_inserts_before_first_heading(self):
        index = {
            "start_marker": "<!-- status-badges:start -->",
            "end_marker": "<!-- status-badges:end -->",
        }

        updated = update_status_badges.replace_generated_section("# Title\n\n## Body\n", index, "badges")

        self.assertEqual(
            "# Title\n\n\n<!-- status-badges:start -->\nbadges\n<!-- status-badges:end -->\n\n## Body\n",
            updated,
        )

    def test_replace_generated_section_appends_when_no_section_heading_exists(self):
        index = {
            "start_marker": "<!-- status-badges:start -->",
            "end_marker": "<!-- status-badges:end -->",
        }

        updated = update_status_badges.replace_generated_section("# Title\n", index, "badges")

        self.assertEqual(
            "# Title\n\n<!-- status-badges:start -->\nbadges\n<!-- status-badges:end -->\n",
            updated,
        )

    def test_render_and_write_outputs_update_readme_metadata_and_docs(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            readme_path = root / "README.md"
            docs_path = root / "badges" / "README.md"
            metadata_path = root / "badges" / "metadata.json"
            docs_path.parent.mkdir(parents=True)
            readme_path.write_text("# Title\n\n## Body\n", encoding="utf-8")
            docs_path.write_text("old docs\n", encoding="utf-8")
            metadata = {"version": "1.0.0"}
            index = {
                "metadata_path": str(metadata_path),
                "readme_path": str(readme_path),
                "docs_path": str(docs_path),
                "docs_heading": "Status Badges",
                "start_marker": "<!-- status-badges:start -->",
                "end_marker": "<!-- status-badges:end -->",
                "badges": [
                    {
                        "id": "version",
                        "label": "Version",
                        "metadata_field": "version",
                        "source": "metadata",
                        "logic": "shown as-is",
                        "color": "blue",
                    }
                ],
            }

            current_readme, next_readme, current_docs, next_docs = update_status_badges.render_outputs(
                index,
                metadata,
                readme_path,
                docs_path,
            )
            update_status_badges.write_outputs(metadata_path, metadata, readme_path, next_readme, docs_path, next_docs)

            self.assertEqual("# Title\n\n## Body\n", current_readme)
            self.assertEqual("old docs\n", current_docs)
            self.assertIn("![Version: 1.0.0]", readme_path.read_text(encoding="utf-8"))
            self.assertIn("# Status Badges", docs_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata, json.loads(metadata_path.read_text(encoding="utf-8")))

    def test_derive_versions_uses_file_fallback_when_descriptor_and_workshop_are_unavailable(self):
        with TemporaryDirectory() as directory:
            fallback = Path(directory) / "main.gui"
            fallback.write_text("gui content", encoding="utf-8")
            args = argparse.Namespace(
                version="2026.01.01.0000",
                version_now=False,
                uiod_version=None,
                stellaris_version=None,
                uiod_descriptor=Path(directory) / "missing-descriptor.mod",
                workshop_acf=None,
                uiod_workshop_id="1623423360",
                uiod_file_fallback=fallback,
            )

            version, uiod_version, stellaris_version = update_status_badges.derive_versions(args)

            self.assertEqual("2026.01.01.0000", version)
            self.assertRegex(uiod_version, r"^sha-[0-9a-f]{12}$")
            self.assertIsNone(stellaris_version)

    def test_outputs_changed_detects_metadata_readme_and_docs_differences(self):
        self.assertFalse(
            update_status_badges.outputs_changed(
                {"version": "1"},
                {"version": "1"},
                "readme",
                "readme",
                "docs",
                "docs",
            )
        )
        self.assertTrue(
            update_status_badges.outputs_changed(
                {"version": "1"},
                {"version": "2"},
                "readme",
                "readme",
                "docs",
                "docs",
            )
        )
