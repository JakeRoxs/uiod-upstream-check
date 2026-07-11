import json
import sys
from unittest import TestCase, main
from tempfile import TemporaryDirectory
from pathlib import Path

from scripts import update_uiod_gui


class TestUpdateUiodGuiAdditional(TestCase):
    def test_write_text_creates_parent_directories(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "interface" / "main.gui"
            update_uiod_gui.write_text(path, "content\n")

            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(encoding="utf-8"), "content\n")

    def test_check_generated_missing_vendored_path_returns_error(self):
        with TemporaryDirectory() as directory:
            vendored_path = Path(directory) / "vendor.gui"
            patched_path = Path(directory) / "patched.gui"
            patched_path.write_text("patched\n", encoding="utf-8")

            result = update_uiod_gui.check_generated("variant", {}, vendored_path, patched_path)

            self.assertEqual(result, 1)

    def test_check_generated_missing_patched_path_returns_error(self):
        with TemporaryDirectory() as directory:
            vendored_path = Path(directory) / "vendor.gui"
            vendored_path.write_text("vendor\n", encoding="utf-8")
            patched_path = Path(directory) / "patched.gui"

            result = update_uiod_gui.check_generated("variant", {}, vendored_path, patched_path)

            self.assertEqual(result, 1)

    def test_check_generated_reports_out_of_date_when_patch_differs(self):
        with TemporaryDirectory() as directory:
            vendored_path = Path(directory) / "vendor.gui"
            patched_path = Path(directory) / "patched.gui"
            vendored_path.write_text("buttonType = {\n    name = \"start_stop_icons\"\n    alwaysTransparent = yes\n}\n", encoding="utf-8")
            patched_path.write_text("buttonType = {\n    name = \"start_stop_icons\"\n    alwaysTransparent = yes\n    frame = 1\n    shortcut = \"SPACE\"\n}\n", encoding="utf-8")

            result = update_uiod_gui.check_generated("variant", {"remove_pause_clicksound": True}, vendored_path, patched_path)

            self.assertEqual(result, 1)

    def test_check_or_update_upstream_missing_upstream_returns_error(self):
        with TemporaryDirectory() as directory:
            vendored_path = Path(directory) / "vendor.gui"
            patched_path = Path(directory) / "patched.gui"
            local_path = Path(directory) / "local.gui"

            result = update_uiod_gui.check_or_update_upstream(
                "variant",
                {},
                Path(directory) / "missing.gui",
                vendored_path,
                patched_path,
                local_path,
                update=False,
            )

            self.assertEqual(result, 1)

    def test_check_or_update_upstream_update_writes_files_and_returns_zero(self):
        with TemporaryDirectory() as directory:
            upstream_path = Path(directory) / "upstream.gui"
            vendored_path = Path(directory) / "vendor.gui"
            patched_path = Path(directory) / "patched.gui"
            upstream_path.write_text(
                "buttonType = {\n    name = \"start_stop_icons\"\n    alwaysTransparent = yes\n}\n",
                encoding="utf-8",
            )

            result = update_uiod_gui.check_or_update_upstream(
                "variant",
                {
                    "vendor_path": "vendor.gui",
                    "patched_path": "patched.gui",
                    "mod_path": str(Path(directory) / "mods" / "Example Mod"),
                    "upstream_file": "interface/main.gui",
                },
                upstream_path,
                vendored_path,
                patched_path,
                None,
                update=True,
            )

            self.assertEqual(result, 0)
            self.assertTrue(vendored_path.exists())
            self.assertTrue(patched_path.exists())

    def test_check_or_update_upstream_no_update_vendored_missing_returns_error(self):
        with TemporaryDirectory() as directory:
            upstream_path = Path(directory) / "upstream.gui"
            upstream_path.write_text(
                "buttonType = {\n    name = \"start_stop_icons\"\n    alwaysTransparent = yes\n}\n",
                encoding="utf-8",
            )
            vendored_path = Path(directory) / "vendor.gui"
            patched_path = Path(directory) / "patched.gui"

            result = update_uiod_gui.check_or_update_upstream(
                "variant",
                {},
                upstream_path,
                vendored_path,
                patched_path,
                None,
                update=False,
            )

            self.assertEqual(result, 1)

    def test_check_or_update_upstream_no_update_custom_local_path_matches_returns_zero(self):
        with TemporaryDirectory() as directory:
            upstream_path = Path(directory) / "upstream.gui"
            vendored_path = Path(directory) / "vendor.gui"
            patched_path = Path(directory) / "patched.gui"
            local_path = Path(directory) / "local.gui"
            upstream_path.write_text(
                "buttonType = {\n    name = \"start_stop_icons\"\n    alwaysTransparent = yes\n}\n",
                encoding="utf-8",
            )
            vendored_path.write_text(upstream_path.read_text(encoding="utf-8"), encoding="utf-8")
            local_path.write_text(
                update_uiod_gui.apply_spacebar_pause_patch(upstream_path.read_text(encoding="utf-8")),
                encoding="utf-8",
            )

            result = update_uiod_gui.check_or_update_upstream(
                "variant",
                {
                    "vendor_path": "vendor.gui",
                    "patched_path": "patched.gui",
                    "mod_path": "mods/Example Mod",
                    "upstream_file": "interface/main.gui",
                },
                upstream_path,
                vendored_path,
                patched_path,
                local_path,
                update=False,
            )

            self.assertEqual(result, 0)

    def test_check_or_update_upstream_no_update_local_path_mismatch_returns_error(self):
        with TemporaryDirectory() as directory:
            upstream_path = Path(directory) / "upstream.gui"
            vendored_path = Path(directory) / "vendor.gui"
            patched_path = Path(directory) / "patched.gui"
            local_path = Path(directory) / "local.gui"
            upstream_path.write_text(
                "buttonType = {\n    name = \"start_stop_icons\"\n    alwaysTransparent = yes\n}\n",
                encoding="utf-8",
            )
            vendored_path.write_text(upstream_path.read_text(encoding="utf-8"), encoding="utf-8")
            local_path.write_text("buttonType = {\n    name = \"start_stop_icons\"\n    alwaysTransparent = yes\n    frame = 2\n}\n", encoding="utf-8")

            result = update_uiod_gui.check_or_update_upstream(
                "variant",
                {
                    "vendor_path": "vendor.gui",
                    "patched_path": "patched.gui",
                    "mod_path": "mods/Example Mod",
                    "upstream_file": "interface/main.gui",
                },
                upstream_path,
                vendored_path,
                patched_path,
                local_path,
                update=False,
            )

            self.assertEqual(result, 1)

    def test_load_manifest_empty_manifest_raises(self):
        with TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "variants.json"
            manifest_path.write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Manifest must contain at least one variant"):
                update_uiod_gui.load_manifest(manifest_path)

    def test_load_manifest_missing_required_fields_raises(self):
        with TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "variants.json"
            manifest_path.write_text('{"variant": {"display_name": "Test"}}\n', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Variant variant is missing fields"):
                update_uiod_gui.load_manifest(manifest_path)

    def test_variant_paths_uses_overrides(self):
        config = {"vendor_path": "vendor.gui", "patched_path": "patched.gui"}
        vendored, patched = update_uiod_gui.variant_paths(config, Path("/tmp/vendor.gui"), Path("/tmp/patched.gui"))

        self.assertEqual(vendored, Path("/tmp/vendor.gui"))
        self.assertEqual(patched, Path("/tmp/patched.gui"))

    def test_mod_gui_path_returns_none_when_mod_path_missing(self):
        config = {"upstream_file": "interface/main.gui"}
        self.assertIsNone(update_uiod_gui.mod_gui_path(config))

    def test_check_full_mod_stack_returns_zero_when_mod_path_missing(self):
        result = update_uiod_gui.check_full_mod_stack("variant", {}, "patched\n")
        self.assertEqual(result, 0)

    def test_check_full_mod_stack_returns_error_when_descriptor_missing(self):
        with TemporaryDirectory() as directory:
            config = {
                "mod_path": str(Path(directory) / "mods" / "Example Mod"),
                "upstream_file": "interface/main.gui",
            }
            target = Path(directory) / "mods" / "Example Mod" / "interface" / "main.gui"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("patched\n", encoding="utf-8")

            result = update_uiod_gui.check_full_mod_stack("variant", config, "patched\n")
            self.assertEqual(result, 1)

    def test_check_full_mod_stack_returns_error_when_generated_gui_out_of_sync(self):
        with TemporaryDirectory() as directory:
            config = {
                "mod_path": str(Path(directory) / "mods" / "Example Mod"),
                "upstream_file": "interface/main.gui",
                "patched_path": "patched.gui",
            }
            mod_root = Path(directory) / "mods" / "Example Mod"
            target = mod_root / "interface" / "main.gui"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("patched-other\n", encoding="utf-8")
            (mod_root / "descriptor.mod").write_text("name=\"Test\"\n", encoding="utf-8")

            result = update_uiod_gui.check_full_mod_stack("variant", config, "patched\n")
            self.assertEqual(result, 1)

    def test_check_full_mod_stack_returns_error_when_picture_missing(self):
        with TemporaryDirectory() as directory:
            config = {
                "mod_path": str(Path(directory) / "mods" / "Example Mod"),
                "upstream_file": "interface/main.gui",
                "patched_path": "patched.gui",
            }
            mod_root = Path(directory) / "mods" / "Example Mod"
            target = mod_root / "interface" / "main.gui"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("patched\n", encoding="utf-8")
            (mod_root / "descriptor.mod").write_text("picture=\"missing.png\"\n", encoding="utf-8")

            result = update_uiod_gui.check_full_mod_stack("variant", config, "patched\n")
            self.assertEqual(result, 1)

    def test_check_generated_matches_patch_and_full_mod_stack_returns_zero(self):
        with TemporaryDirectory() as directory:
            vendored_path = Path(directory) / "vendor.gui"
            patched_path = Path(directory) / "patched.gui"
            vendored_path.write_text(
                "buttonType = {\n    name = \"start_stop_icons\"\n    alwaysTransparent = yes\n}\n",
                encoding="utf-8",
            )
            expected = update_uiod_gui.apply_spacebar_pause_patch(vendored_path.read_text(encoding="utf-8"))
            patched_path.write_text(expected, encoding="utf-8")

            mod_path = Path(directory) / "mods" / "Example Mod"
            target = mod_path / "interface" / "main.gui"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(expected, encoding="utf-8")
            (mod_path / "descriptor.mod").write_text("name=\"Test\"\n", encoding="utf-8")

            config = {
                "vendor_path": "vendor.gui",
                "patched_path": "patched.gui",
                "mod_path": str(mod_path),
                "upstream_file": "interface/main.gui",
            }
            result = update_uiod_gui.check_generated("variant", config, vendored_path, patched_path)
            self.assertEqual(result, 0)

    def test_check_or_update_upstream_invalid_patch_returns_error(self):
        with TemporaryDirectory() as directory:
            upstream_path = Path(directory) / "upstream.gui"
            vendored_path = Path(directory) / "vendor.gui"
            patched_path = Path(directory) / "patched.gui"
            upstream_path.write_text(
                "buttonType = {\n    name = \"start_stop_icons\"\n}\n",
                encoding="utf-8",
            )

            result = update_uiod_gui.check_or_update_upstream(
                "variant",
                {
                    "vendor_path": "vendor.gui",
                    "patched_path": "patched.gui",
                    "mod_path": "mods/Example Mod",
                    "upstream_file": "interface/main.gui",
                },
                upstream_path,
                vendored_path,
                patched_path,
                None,
                update=True,
            )

            self.assertEqual(result, 1)

    def test_main_all_check_generated_with_manifest(self):
        with TemporaryDirectory() as directory:
            manifest = {
                "variant": {
                    "display_name": "Test",
                    "workshop_id": "123",
                    "upstream_file": "interface/main.gui",
                    "vendor_path": "vendor.gui",
                    "patched_path": "patched.gui",
                    "mod_path": "mods/Example Mod",
                }
            }
            manifest_path = Path(directory) / "variants.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            original_argv = sys.argv
            try:
                sys.argv = [original_argv[0], "--manifest", str(manifest_path), "--all", "--check-generated"]
                result = update_uiod_gui.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(result, 1)

    def test_main_unknown_variant_returns_error(self):
        with TemporaryDirectory() as directory:
            manifest = {
                "variant": {
                    "display_name": "Test",
                    "workshop_id": "123",
                    "upstream_file": "interface/main.gui",
                    "vendor_path": "vendor.gui",
                    "patched_path": "patched.gui",
                    "mod_path": "mods/Example Mod",
                }
            }
            manifest_path = Path(directory) / "variants.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            original_argv = sys.argv
            try:
                sys.argv = [original_argv[0], "--manifest", str(manifest_path), "--variant", "missing", "--check-generated"]
                result = update_uiod_gui.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(result, 1)

    def test_main_variant_with_check_generated_and_paths_overrides_errors(self):
        with TemporaryDirectory() as directory:
            manifest = {
                "variant": {
                    "display_name": "Test",
                    "workshop_id": "123",
                    "upstream_file": "interface/main.gui",
                    "vendor_path": "vendor.gui",
                    "patched_path": "patched.gui",
                    "mod_path": "mods/Example Mod",
                }
            }
            manifest_path = Path(directory) / "variants.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            original_argv = sys.argv
            try:
                sys.argv = [
                    original_argv[0],
                    "--manifest",
                    str(manifest_path),
                    "--variant",
                    "variant",
                    "--check-generated",
                    "--vendored-main-gui",
                    "vendor.gui",
                ]
                result = update_uiod_gui.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(result, 1)

    def test_main_variants_errors_when_no_variant_or_all(self):
        original_argv = sys.argv
        try:
            sys.argv = [original_argv[0]]
            result = update_uiod_gui.main()
        finally:
            sys.argv = original_argv

        self.assertEqual(result, 1)


if __name__ == "__main__":
    main()
