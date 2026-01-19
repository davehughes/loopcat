"""Tests to verify loopcat works after the cat_common refactor."""

from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest


class TestLoopCatImportsCatCommon:
    """Tests that loopcat correctly imports from cat_common."""

    def test_loopcat_tui_imports_themes(self):
        """loopcat.tui imports THEMES from cat_common."""
        from loopcat.tui import THEMES
        assert len(THEMES) > 0
        assert "textual-dark" in THEMES

    def test_loopcat_tui_imports_theme_picker(self):
        """loopcat.tui imports ThemePickerScreen from cat_common."""
        from loopcat.tui import ThemePickerScreen
        screen = ThemePickerScreen("textual-dark")
        assert screen.current_theme == "textual-dark"

    def test_loopcat_tui_has_controls_footer(self):
        """loopcat.tui has ControlsFooter (extended from cat_common)."""
        from loopcat.tui import ControlsFooter
        # The loopcat version extends the base
        footer = ControlsFooter()
        assert footer is not None



class TestLoopCatAppStarts:
    """Tests that LoopCatApp can be instantiated after refactor."""

    @pytest.fixture
    def sample_patch(self):
        """Create a minimal patch for testing."""
        from loopcat.models import Patch, Track

        track = Track(
            id="track-1",
            patch_id="patch-1",
            track_number=1,
            filename="001_1.wav",
            original_path="/original/001_1.wav",
            wav_path="/tmp/test/001_1.wav",
            xxhash="abc123",
            quick_hash="quick123",
            file_created_at=datetime.now(),
            file_modified_at=datetime.now(),
            duration_seconds=10.0,
            sample_rate=44100,
            channels=2,
        )

        return Patch(
            id="patch-1",
            catalog_number=1,
            original_bank=42,
            source_device="Boss RC-300",
            source_path="/test",
            tracks=[track],
            created_at=datetime.now(),
        )

    def test_loopcat_app_instantiates(self, sample_patch):
        """LoopCatApp can be instantiated."""
        from loopcat.tui import LoopCatApp

        app = LoopCatApp([sample_patch])
        assert app.patches == [sample_patch]

    def test_loopcat_app_has_register_themes(self, sample_patch):
        """LoopCatApp uses register_themes from cat_common."""
        from loopcat.tui import LoopCatApp, register_themes

        # register_themes should be importable
        assert callable(register_themes)

    @pytest.mark.asyncio
    async def test_loopcat_app_starts_with_themes(self, sample_patch):
        """LoopCatApp starts and has themes registered."""
        from loopcat.tui import LoopCatApp

        with patch('loopcat.tui.AudioPlayer') as MockPlayer:
            mock_player = MagicMock()
            mock_player.get_track_info.return_value = (0.0, 10.0, False)
            MockPlayer.return_value = mock_player

            app = LoopCatApp([sample_patch], initial_patch=sample_patch)
            async with app.run_test() as pilot:
                await pilot.pause()
                # App should have started successfully
                assert app.is_running


class TestThemePickerStillWorks:
    """Tests that ThemePickerScreen works via cat_common import."""

    @pytest.fixture
    def sample_patch(self):
        """Create a minimal patch for testing."""
        from loopcat.models import Patch, Track

        track = Track(
            id="track-1",
            patch_id="patch-1",
            track_number=1,
            filename="001_1.wav",
            original_path="/original/001_1.wav",
            wav_path="/tmp/test/001_1.wav",
            xxhash="abc123",
            quick_hash="quick123",
            file_created_at=datetime.now(),
            file_modified_at=datetime.now(),
            duration_seconds=10.0,
            sample_rate=44100,
            channels=2,
        )

        return Patch(
            id="patch-1",
            catalog_number=1,
            original_bank=42,
            source_device="Boss RC-300",
            source_path="/test",
            tracks=[track],
            created_at=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_theme_picker_opens(self, sample_patch):
        """Theme picker opens when 't' is pressed."""
        from loopcat.tui import LoopCatApp, ThemePickerScreen

        with patch('loopcat.tui.AudioPlayer') as MockPlayer:
            mock_player = MagicMock()
            mock_player.get_track_info.return_value = (0.0, 10.0, False)
            MockPlayer.return_value = mock_player

            app = LoopCatApp([sample_patch], initial_patch=sample_patch)
            async with app.run_test() as pilot:
                await pilot.pause()

                # Press 't' to open theme picker
                await pilot.press("t")
                await pilot.pause()

                # Should be on theme picker screen
                assert isinstance(app.screen, ThemePickerScreen)

    @pytest.mark.asyncio
    async def test_theme_picker_has_all_themes(self, sample_patch):
        """Theme picker shows all themes from cat_common."""
        from loopcat.tui import LoopCatApp, ThemePickerScreen, THEMES
        from textual.widgets import OptionList

        with patch('loopcat.tui.AudioPlayer') as MockPlayer:
            mock_player = MagicMock()
            mock_player.get_track_info.return_value = (0.0, 10.0, False)
            MockPlayer.return_value = mock_player

            app = LoopCatApp([sample_patch], initial_patch=sample_patch)
            async with app.run_test() as pilot:
                await pilot.pause()

                # Press 't' to open theme picker
                await pilot.press("t")
                await pilot.pause()

                theme_screen = app.screen
                assert isinstance(theme_screen, ThemePickerScreen)

                # Verify all themes are listed
                option_list = theme_screen.query_one("#theme-list", OptionList)
                assert option_list.option_count == len(THEMES)
