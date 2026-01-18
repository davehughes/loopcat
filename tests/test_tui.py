"""Tests for the TUI player."""

from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from loopcat.models import Patch, Track
from loopcat.tui import TrackWidget, LoopCatApp, PlayerScreen, ThemePickerScreen, THEMES


@pytest.fixture
def sample_track():
    """Create a sample track for testing."""
    return Track(
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
        duration_seconds=32.5,
        sample_rate=44100,
        channels=2,
    )


@pytest.fixture
def sample_patch_single_track(sample_track):
    """Create a sample patch with one track."""
    return Patch(
        id="patch-1",
        catalog_number=1,
        original_bank=42,
        source_device="Boss RC-300",
        source_path="/test",
        tracks=[sample_track],
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_patch_multi_track():
    """Create a sample patch with multiple tracks."""
    tracks = []
    for i in range(1, 4):
        tracks.append(
            Track(
                id=f"track-{i}",
                patch_id="patch-multi",
                track_number=i,
                filename=f"001_{i}.wav",
                original_path=f"/original/001_{i}.wav",
                wav_path=f"/tmp/test/001_{i}.wav",
                xxhash=f"hash{i}",
                quick_hash=f"quick{i}",
                file_created_at=datetime.now(),
                file_modified_at=datetime.now(),
                duration_seconds=10.0 * i,
                sample_rate=44100,
                channels=2,
            )
        )
    return Patch(
        id="patch-multi",
        catalog_number=2,
        original_bank=10,
        source_device="Boss RC-300",
        source_path="/test",
        tracks=tracks,
        created_at=datetime.now(),
    )


class TestTrackWidget:
    """Tests for TrackWidget."""

    def test_track_widget_creation(self, sample_track):
        """Test that TrackWidget can be instantiated."""
        widget = TrackWidget(sample_track, 1, id="track-1")
        assert widget.track == sample_track
        assert widget.track_number == 1

    def test_track_widget_initial_state(self, sample_track):
        """Test TrackWidget initial state values."""
        widget = TrackWidget(sample_track, 1, id="track-1")
        assert widget._playing is False

    def test_track_widget_update_state(self, sample_track):
        """Test updating track widget state."""
        widget = TrackWidget(sample_track, 1, id="track-1")
        widget.update_state(playing=True)

        assert widget._playing is True


class TestLoopCatApp:
    """Tests for LoopCatApp."""

    def test_app_creation(self, sample_patch_single_track):
        """Test that LoopCatApp can be instantiated."""
        app = LoopCatApp([sample_patch_single_track])
        assert app.patches == [sample_patch_single_track]

    def test_app_with_multiple_patches(self, sample_patch_single_track, sample_patch_multi_track):
        """Test LoopCatApp with multiple patches."""
        patches = [sample_patch_single_track, sample_patch_multi_track]
        app = LoopCatApp(patches)

        assert len(app.patches) == 2

    def test_app_with_initial_patch(self, sample_patch_single_track, sample_patch_multi_track):
        """Test that LoopCatApp can start with a specific patch."""
        patches = [sample_patch_single_track, sample_patch_multi_track]
        app = LoopCatApp(patches, initial_patch=sample_patch_multi_track)

        assert app.initial_patch == sample_patch_multi_track

    def test_patch_has_multiple_tracks(self, sample_patch_multi_track):
        """Test that multi-track patches have correct track count."""
        assert len(sample_patch_multi_track.tracks) == 3

        # Verify track numbers
        track_numbers = [t.track_number for t in sample_patch_multi_track.tracks]
        assert track_numbers == [1, 2, 3]


class TestPlayerScreen:
    """Tests for PlayerScreen."""

    def test_player_screen_creation(self, sample_patch_single_track):
        """Test that PlayerScreen can be instantiated."""
        screen = PlayerScreen(sample_patch_single_track, [sample_patch_single_track], 0)
        assert screen.patch == sample_patch_single_track
        assert screen.current_patch_index == 0

    def test_player_screen_with_all_patches(self, sample_patch_single_track, sample_patch_multi_track):
        """Test PlayerScreen with multiple patches for navigation."""
        patches = [sample_patch_single_track, sample_patch_multi_track]
        screen = PlayerScreen(sample_patch_single_track, patches, 0)

        assert len(screen.all_patches) == 2
        assert screen.current_patch_index == 0

    def test_player_screen_finds_current_patch_index(self, sample_patch_single_track, sample_patch_multi_track):
        """Test that PlayerScreen correctly uses the provided index."""
        patches = [sample_patch_single_track, sample_patch_multi_track]
        # Start with the second patch
        screen = PlayerScreen(sample_patch_multi_track, patches, 1)

        assert screen.current_patch_index == 1


class TestLoopCatAppAsync:
    """Async tests for LoopCatApp using Textual's test framework."""

    @pytest.mark.asyncio
    async def test_multi_track_patch_renders_all_tracks(self, sample_patch_multi_track):
        """Test that a multi-track patch renders a TrackWidget for each track."""
        from loopcat.tui import PlayerScreen

        # Mock the AudioPlayer to avoid actual audio playback
        with patch('loopcat.tui.AudioPlayer') as MockPlayer:
            mock_player = MagicMock()
            mock_player.get_track_info.return_value = (0.0, 10.0, False)
            MockPlayer.return_value = mock_player

            app = LoopCatApp([sample_patch_multi_track], initial_patch=sample_patch_multi_track)
            async with app.run_test() as pilot:
                # Wait for screens to be set up
                await pilot.pause()

                # Verify we're on the player screen
                assert isinstance(app.screen, PlayerScreen)

                # Query for all TrackWidget instances from the current screen
                track_widgets = app.screen.query(TrackWidget)
                widget_list = list(track_widgets)

                # Should have 3 TrackWidgets for 3 tracks
                assert len(widget_list) == 3, f"Expected 3 TrackWidgets, got {len(widget_list)}"

                # Verify each track number is represented
                track_numbers = {w.track_number for w in widget_list}
                assert track_numbers == {1, 2, 3}

    @pytest.mark.asyncio
    async def test_single_track_patch_renders_one_track(self, sample_patch_single_track):
        """Test that a single-track patch renders one TrackWidget."""
        from loopcat.tui import PlayerScreen

        with patch('loopcat.tui.AudioPlayer') as MockPlayer:
            mock_player = MagicMock()
            mock_player.get_track_info.return_value = (0.0, 10.0, False)
            MockPlayer.return_value = mock_player

            app = LoopCatApp([sample_patch_single_track], initial_patch=sample_patch_single_track)
            async with app.run_test() as pilot:
                # Wait for screens to be set up
                await pilot.pause()

                # Verify we're on the player screen
                assert isinstance(app.screen, PlayerScreen)

                track_widgets = app.screen.query(TrackWidget)
                widget_list = list(track_widgets)

                assert len(widget_list) == 1
                assert widget_list[0].track_number == 1


class TestThemePickerScreen:
    """Tests for ThemePickerScreen."""

    def test_theme_picker_creation(self):
        """Test that ThemePickerScreen can be instantiated."""
        screen = ThemePickerScreen("textual-dark")
        assert screen.current_theme == "textual-dark"
        assert screen.filter_text == ""

    def test_themes_list_not_empty(self):
        """Test that THEMES list contains themes."""
        assert len(THEMES) > 0
        assert "textual-dark" in THEMES

    def test_themes_list_has_no_duplicates(self):
        """Test that THEMES list has no duplicate entries."""
        assert len(THEMES) == len(set(THEMES))

    @pytest.mark.asyncio
    async def test_theme_picker_renders_option_list(self, sample_patch_single_track):
        """Test that ThemePickerScreen renders an OptionList with themes."""
        from textual.widgets import OptionList, Input

        with patch('loopcat.tui.AudioPlayer') as MockPlayer:
            mock_player = MagicMock()
            mock_player.get_track_info.return_value = (0.0, 10.0, False)
            MockPlayer.return_value = mock_player

            app = LoopCatApp([sample_patch_single_track], initial_patch=sample_patch_single_track)
            async with app.run_test() as pilot:
                # Press 't' to open theme picker (mimics user interaction)
                await pilot.press("t")
                await pilot.pause()

                # Get the current screen (should be ThemePickerScreen)
                theme_screen = app.screen
                assert isinstance(theme_screen, ThemePickerScreen)

                # Verify the option list exists and has themes
                option_list = theme_screen.query_one("#theme-list", OptionList)
                assert option_list.option_count == len(THEMES)

                # Verify search input exists
                search_input = theme_screen.query_one("#theme-search", Input)
                assert search_input is not None

    @pytest.mark.asyncio
    async def test_theme_picker_filter(self, sample_patch_single_track):
        """Test that typing in search filters the theme list."""
        from textual.widgets import OptionList, Input

        with patch('loopcat.tui.AudioPlayer') as MockPlayer:
            mock_player = MagicMock()
            mock_player.get_track_info.return_value = (0.0, 10.0, False)
            MockPlayer.return_value = mock_player

            app = LoopCatApp([sample_patch_single_track], initial_patch=sample_patch_single_track)
            async with app.run_test() as pilot:
                # Press 't' to open theme picker
                await pilot.press("t")
                await pilot.pause()

                theme_screen = app.screen
                assert isinstance(theme_screen, ThemePickerScreen)

                # Type "dracula" in the search
                search_input = theme_screen.query_one("#theme-search", Input)
                search_input.value = "dracula"
                await pilot.pause()

                # Option list should be filtered
                option_list = theme_screen.query_one("#theme-list", OptionList)
                # Should have fewer options than full list
                assert option_list.option_count < len(THEMES)
                assert option_list.option_count > 0  # "dracula" should match

    @pytest.mark.asyncio
    async def test_theme_picker_cancel_restores_theme(self, sample_patch_single_track):
        """Test that canceling the picker restores the original theme."""
        with patch('loopcat.tui.AudioPlayer') as MockPlayer:
            mock_player = MagicMock()
            mock_player.get_track_info.return_value = (0.0, 10.0, False)
            MockPlayer.return_value = mock_player

            app = LoopCatApp([sample_patch_single_track], initial_patch=sample_patch_single_track)
            async with app.run_test() as pilot:
                original_theme = app.theme

                # Press 't' to open theme picker
                await pilot.press("t")
                await pilot.pause()

                # Press escape to cancel
                await pilot.press("escape")
                await pilot.pause()

                # Theme should be restored
                assert app.theme == original_theme

    @pytest.mark.asyncio
    async def test_theme_picker_keyboard_navigation(self, sample_patch_single_track):
        """Test that arrow keys and ctrl+j/k navigate the theme list."""
        from textual.widgets import OptionList

        with patch('loopcat.tui.AudioPlayer') as MockPlayer:
            mock_player = MagicMock()
            mock_player.get_track_info.return_value = (0.0, 10.0, False)
            MockPlayer.return_value = mock_player

            app = LoopCatApp([sample_patch_single_track], initial_patch=sample_patch_single_track)
            async with app.run_test() as pilot:
                # Press 't' to open theme picker
                await pilot.press("t")
                await pilot.pause()

                theme_screen = app.screen
                option_list = theme_screen.query_one("#theme-list", OptionList)

                # Set a known starting position
                option_list.highlighted = 5
                await pilot.pause()

                # Test ctrl+j to move down (vim-style)
                await pilot.press("ctrl+j")
                await pilot.pause()
                assert option_list.highlighted == 6, f"Expected 6 after ctrl+j, got {option_list.highlighted}"

                # Test ctrl+k to move up (vim-style)
                await pilot.press("ctrl+k")
                await pilot.pause()
                assert option_list.highlighted == 5, f"Expected 5 after ctrl+k, got {option_list.highlighted}"

                # Test down arrow
                await pilot.press("down")
                await pilot.pause()
                assert option_list.highlighted == 6, f"Expected 6 after down, got {option_list.highlighted}"

                # Test up arrow
                await pilot.press("up")
                await pilot.pause()
                assert option_list.highlighted == 5, f"Expected 5 after up, got {option_list.highlighted}"

                # Test ctrl+n to move down
                await pilot.press("ctrl+n")
                await pilot.pause()
                assert option_list.highlighted == 6, f"Expected 6 after ctrl+n, got {option_list.highlighted}"

    @pytest.mark.asyncio
    async def test_theme_picker_enter_selects_theme(self, sample_patch_single_track):
        """Test that pressing enter selects the highlighted theme."""
        from textual.widgets import OptionList

        with patch('loopcat.tui.AudioPlayer') as MockPlayer:
            mock_player = MagicMock()
            mock_player.get_track_info.return_value = (0.0, 10.0, False)
            MockPlayer.return_value = mock_player

            # Mock set_theme to verify it gets called
            with patch('loopcat.tui.set_theme') as mock_set_theme:
                app = LoopCatApp([sample_patch_single_track], initial_patch=sample_patch_single_track)
                async with app.run_test() as pilot:
                    original_theme = app.theme

                    # Press 't' to open theme picker
                    await pilot.press("t")
                    await pilot.pause()

                    theme_screen = app.screen
                    assert isinstance(theme_screen, ThemePickerScreen)

                    option_list = theme_screen.query_one("#theme-list", OptionList)

                    # Navigate to a different theme (index 3)
                    option_list.highlighted = 3
                    await pilot.pause()

                    # Get the theme name at index 3
                    target_theme = THEMES[3]

                    # Press enter to select
                    await pilot.press("enter")
                    await pilot.pause()

                    # Theme picker should be dismissed and theme should be set
                    # The screen should no longer be ThemePickerScreen
                    assert not isinstance(app.screen, ThemePickerScreen), "Theme picker should be dismissed"

                    # set_theme should have been called with the selected theme
                    mock_set_theme.assert_called_once_with(target_theme)
