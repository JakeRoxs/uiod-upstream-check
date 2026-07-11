import json
import sys
from argparse import Namespace
from unittest import TestCase, main
from tempfile import TemporaryDirectory
from pathlib import Path

from scripts import update_status_badges


class TestUpdateStatusBadgesAdditional(TestCase):
    def test_resolve_repo_path_absolute_path(self):
        with TemporaryDirectory() as directory:
            path = (Path(directory) / "file.txt").resolve()
            self.assertEqual(update_status_badges.resolve_repo_path(str(path)), path)

    def test_resolve_repo_path_relative_path(self):
        path = Path("relative/file.txt")
        expected = update_status_badges.ROOT / path
        self.assertEqual(update_status_badges.resolve_repo_path(str(path)), expected)

    def test_display_path_returns_relative_when_possible(self):
        relative_path = update_status_badges.ROOT / "README.md"
        self.assertEqual(update_status_badges.display_path(relative_path), "README.md")

    def test_display_path_returns_absolute_outside_root(self):
        outside = Path("C:/somewhere/else/file.txt")
        self.assertEqual(update_status_badges.display_path(outside), str(outside))

    def test_badge_url_encodes_safe_characters(self):
        url = update_status_badges.badge_url("Version-Info", "1.2.3", "blue")
        self.assertIn("Version--Info", url)
        self.assertIn("1.2.3", url)

    def test_current_timestamp_version_matches_utc_pattern(self):
        version = update_status_badges.current_timestamp_version()
        self.assertRegex(version, r"^\d{4}\.\d{2}\.\d{2}\.\d{4}$")

    def test_parse_keyvalues_tokens_trailing_data_raises(self):
        with self.assertRaisesRegex(ValueError, "Missing value for KeyValues key: extra"):
            update_status_badges.parse_keyvalues_object('"key" "value" "extra"')

    def test_workshop_item_metadata_missing_appworkshop_raises(self):
        acf = '"NotAppWorkshop"\n{\n}\n'
        with TemporaryDirectory() as directory:
            path = Path(directory) / "appworkshop_281990.acf"
            path.write_text(acf, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Missing AppWorkshop object"):
                update_status_badges.workshop_item_metadata(path, "1623423360")

    def test_workshop_item_metadata_missing_workshop_installed_raises(self):
        acf = '"AppWorkshop"\n{\n    "WorkshopItemsInstalled"\n    {\n    }\n}\n'
        with TemporaryDirectory() as directory:
            path = Path(directory) / "appworkshop_281990.acf"
            path.write_text(acf, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Missing workshop item 1623423360"):
                update_status_badges.workshop_item_metadata(path, "1623423360")

    def test_uoid_version_from_workshop_acf_missing_timeupdated_raises(self):
        acf = '"AppWorkshop"\n{\n    "WorkshopItemsInstalled"\n    {\n        "1623423360"\n        {\n        }\n    }\n}\n'
        with TemporaryDirectory() as directory:
            path = Path(directory) / "appworkshop_281990.acf"
            path.write_text(acf, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "missing timeupdated"):
                update_status_badges.uiod_version_from_workshop_acf(path, "1623423360")

    def test_uoid_version_from_descriptor_missing_raises(self):
        descriptor = 'name="UI Overhaul Dynamic"\n'
        with TemporaryDirectory() as directory:
            path = Path(directory) / "descriptor.mod"
            path.write_text(descriptor, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Descriptor is missing version"):
                update_status_badges.uiod_version_from_descriptor(path)

    def test_stellaris_version_from_descriptor_missing_raises(self):
        descriptor = 'name="UI Overhaul Dynamic"\n'
        with TemporaryDirectory() as directory:
            path = Path(directory) / "descriptor.mod"
            path.write_text(descriptor, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Descriptor is missing supported_version"):
                update_status_badges.stellaris_version_from_descriptor(path)

    def test_render_badge_docs_with_default_heading(self):
        index = {
            "badges": [
                {
                    "id": "version",
                    "label": "Version",
                    "metadata_field": "version",
                    "source": "metadata version",
                    "logic": "version logic",
                    "color": "blue",
                }
            ]
        }

        docs = update_status_badges.render_badge_docs(index)

        self.assertIn("# Status Badges", docs)
        self.assertIn("| Version | `version` | metadata version | version logic |", docs)

    def test_update_metadata_applies_all_fields(self):
        current = {"version": "1.0", "sync_status": "stale"}
        updated = update_status_badges.update_metadata(current, "synced", "1.2.3", "uiod", "stellaris")

        self.assertEqual(updated["version"], "1.2.3")
        self.assertEqual(updated["sync_status"], "synced")
        self.assertEqual(updated["uiod_version"], "uiod")
        self.assertEqual(updated["stellaris_version"], "stellaris")

    def test_derive_descriptor_versions_uses_descriptor_when_present(self):
        with TemporaryDirectory() as directory:
            descriptor = Path(directory) / "descriptor.mod"
            descriptor.write_text('name="UI Overhaul Dynamic"\nversion="4.4.*"\nsupported_version="v4.4.*"\n', encoding="utf-8")
            args = Namespace(
                uiod_descriptor=str(descriptor),
                uiod_version=None,
                stellaris_version=None,
                workshop_acf=None,
                uiod_file_fallback=None,
            )

            uiod_version, stellaris_version = update_status_badges.derive_descriptor_versions(args)
            self.assertEqual(uiod_version, "4.4.*")
            self.assertEqual(stellaris_version, "v4.4.*")

    def test_derive_descriptor_versions_missing_descriptor_raises_when_fallback_absent(self):
        args = Namespace(
            uiod_descriptor=str(Path("missing.mod")),
            uiod_version=None,
            stellaris_version=None,
            workshop_acf=None,
            uiod_file_fallback=None,
        )

        with self.assertRaisesRegex(FileNotFoundError, "UIOD descriptor not found"):
            update_status_badges.derive_descriptor_versions(args)

    def test_derive_workshop_version_reads_from_acf_when_present(self):
        with TemporaryDirectory() as directory:
            acf_path = Path(directory) / "appworkshop_281990.acf"
            acf_path.write_text('"AppWorkshop"\n{\n    "WorkshopItemsInstalled"\n    {\n        "1623423360"\n        {\n            "timeupdated" "1767225600"\n        }\n    }\n}\n', encoding="utf-8")
            args = Namespace(
                workshop_acf=str(acf_path),
                uiod_file_fallback=None,
                uiod_version=None,
                uiod_workshop_id="1623423360",
            )

            result = update_status_badges.derive_workshop_version(args, None)
            self.assertEqual(result, "2026.01.01.0000")

    def test_derive_workshop_version_missing_acf_and_no_fallback_raises(self):
        args = Namespace(
            workshop_acf=str(Path("missing.acf")),
            uiod_file_fallback=None,
            uiod_version=None,
            uiod_workshop_id="1623423360",
        )

        with self.assertRaisesRegex(FileNotFoundError, "Workshop ACF file not found"):
            update_status_badges.derive_workshop_version(args, None)

    def test_derive_file_fallback_version_preserves_existing_version(self):
        args = Namespace(
            uiod_file_fallback=None,
        )

        self.assertEqual(update_status_badges.derive_file_fallback_version(args, "4.4.*"), "4.4.*")

    def test_render_outputs_without_docs(self):
        with TemporaryDirectory() as directory:
            metadata_path = Path(directory) / "metadata.json"
            readme_path = Path(directory) / "README.md"
            metadata_path.write_text('{"version": "1.0"}\n', encoding="utf-8")
            readme_path.write_text("# Title\n", encoding="utf-8")
            index = {
                "metadata_path": str(metadata_path),
                "readme_path": str(readme_path),
                "badges": [
                    {
                        "id": "version",
                        "label": "Version",
                        "metadata_field": "version",
                        "source": "metadata version",
                        "logic": "version logic",
                        "color": "blue",
                    }
                ],
                "start_marker": "<!-- status-badges:start -->",
                "end_marker": "<!-- status-badges:end -->",
            }

            current_readme, next_readme, current_docs, next_docs = update_status_badges.render_outputs(
                index,
                {"version": "1.0"},
                readme_path,
                None,
            )

            self.assertEqual(current_readme, "# Title\n")
            self.assertIsNone(current_docs)
            self.assertIn("!", next_readme)

    def test_outputs_changed_returns_true_when_metadata_changes(self):
        self.assertTrue(update_status_badges.outputs_changed(
            {"version": "1.0"},
            {"version": "1.1"},
            "# Title\n",
            "# Title\n",
            None,
            None,
        ))

    def test_main_check_detects_out_of_date_outputs(self):
        with TemporaryDirectory() as directory:
            index = {
                "metadata_path": str(Path(directory) / "metadata.json"),
                "readme_path": str(Path(directory) / "README.md"),
                "docs_path": str(Path(directory) / "docs.md"),
                "badges": [
                    {
                        "id": "version",
                        "label": "Version",
                        "metadata_field": "version",
                        "source": "metadata version",
                        "logic": "version logic",
                        "color": "blue",
                    }
                ],
                "start_marker": "<!-- status-badges:start -->",
                "end_marker": "<!-- status-badges:end -->",
            }
            index_path = Path(directory) / "index.json"
            index_path.write_text(json.dumps(index), encoding="utf-8")
            metadata_path = Path(directory) / "metadata.json"
            metadata_path.write_text('{"version": "1.0"}\n', encoding="utf-8")
            readme_path = Path(directory) / "README.md"
            readme_path.write_text("# Title\n", encoding="utf-8")

            original_argv = sys.argv
            try:
                sys.argv = [original_argv[0], "--index", str(index_path), "--version", "1.1", "--check"]
                result = update_status_badges.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(result, 1)

    def test_write_json_writes_formatted_data(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.json"
            update_status_badges.write_json(path, {"version": "2.0"})
            self.assertEqual(path.read_text(encoding="utf-8"), '{\n  "version": "2.0"\n}\n')


if __name__ == "__main__":
    main()
