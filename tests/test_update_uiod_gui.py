from unittest import TestCase, main

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


if __name__ == "__main__":
    main()
