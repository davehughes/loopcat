"""Tests for the TUI player."""

from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from loopcat.models import Patch, Track
from loopcat.tui import TrackWidget, PlayerApp


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
        assert widget._position == 0.0
        assert widget._duration == 1.0
        assert widget._playing is False

    def test_track_widget_update_state(self, sample_track):
        """Test updating track widget state."""
        widget = TrackWidget(sample_track, 1, id="track-1")
        widget.update_state(position=15.0, duration=30.0, playing=True)

        assert widget._position == 15.0
        assert widget._duration == 30.0
        assert widget._playing is True


class TestPlayerApp:
    """Tests for PlayerApp."""

    def test_player_app_creation(self, sample_patch_single_track):
        """Test that PlayerApp can be instantiated."""
        app = PlayerApp(sample_patch_single_track)
        assert app.patch == sample_patch_single_track
        assert app.loop_mode is True

    def test_player_app_with_all_patches(self, sample_patch_single_track, sample_patch_multi_track):
        """Test PlayerApp with multiple patches for navigation."""
        patches = [sample_patch_single_track, sample_patch_multi_track]
        app = PlayerApp(sample_patch_single_track, all_patches=patches)

        assert len(app.all_patches) == 2
        assert app.current_patch_index == 0

    def test_player_app_finds_current_patch_index(self, sample_patch_single_track, sample_patch_multi_track):
        """Test that PlayerApp correctly finds the current patch in the list."""
        patches = [sample_patch_single_track, sample_patch_multi_track]
        # Start with the second patch
        app = PlayerApp(sample_patch_multi_track, all_patches=patches)

        assert app.current_patch_index == 1

    def test_patch_has_multiple_tracks(self, sample_patch_multi_track):
        """Test that multi-track patches have correct track count."""
        assert len(sample_patch_multi_track.tracks) == 3

        # Verify track numbers
        track_numbers = [t.track_number for t in sample_patch_multi_track.tracks]
        assert track_numbers == [1, 2, 3]


class TestPlayerAppAsync:
    """Async tests for PlayerApp using Textual's test framework."""

    @pytest.mark.asyncio
    async def test_multi_track_patch_renders_all_tracks(self, sample_patch_multi_track):
        """Test that a multi-track patch renders a TrackWidget for each track."""
        # Mock the AudioPlayer to avoid actual audio playback
        with patch('loopcat.tui.AudioPlayer') as MockPlayer:
            mock_player = MagicMock()
            mock_player.get_track_info.return_value = (0.0, 10.0, False)
            MockPlayer.return_value = mock_player

            app = PlayerApp(sample_patch_multi_track)
            async with app.run_test() as pilot:
                # Query for all TrackWidget instances
                track_widgets = app.query(TrackWidget)
                widget_list = list(track_widgets)

                # Should have 3 TrackWidgets for 3 tracks
                assert len(widget_list) == 3, f"Expected 3 TrackWidgets, got {len(widget_list)}"

                # Verify each track number is represented
                track_numbers = {w.track_number for w in widget_list}
                assert track_numbers == {1, 2, 3}

    @pytest.mark.asyncio
    async def test_single_track_patch_renders_one_track(self, sample_patch_single_track):
        """Test that a single-track patch renders one TrackWidget."""
        with patch('loopcat.tui.AudioPlayer') as MockPlayer:
            mock_player = MagicMock()
            mock_player.get_track_info.return_value = (0.0, 10.0, False)
            MockPlayer.return_value = mock_player

            app = PlayerApp(sample_patch_single_track)
            async with app.run_test() as pilot:
                track_widgets = app.query(TrackWidget)
                widget_list = list(track_widgets)

                assert len(widget_list) == 1
                assert widget_list[0].track_number == 1
