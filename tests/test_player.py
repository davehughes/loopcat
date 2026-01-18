"""Tests for the audio player."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from loopcat.player import AudioPlayer, TrackState


@pytest.fixture
def mock_sounddevice():
    """Mock sounddevice to avoid actual audio output."""
    with patch('loopcat.player.sd') as mock_sd:
        mock_stream = MagicMock()
        mock_sd.OutputStream.return_value = mock_stream
        yield mock_sd


@pytest.fixture
def mock_soundfile():
    """Mock soundfile to avoid reading actual files."""
    with patch('loopcat.player.sf') as mock_sf:
        # Return stereo audio data at 44100 Hz, 1 second long
        mock_sf.read.return_value = (
            np.zeros((44100, 2), dtype='float32'),
            44100
        )
        yield mock_sf


class TestAudioPlayer:
    """Tests for AudioPlayer."""

    def test_player_creation(self, mock_sounddevice):
        """Test that AudioPlayer can be instantiated."""
        player = AudioPlayer()
        assert player.state.master_playing is False
        assert player.state.master_position == 0

    def test_load_track(self, mock_sounddevice, mock_soundfile):
        """Test loading a track."""
        player = AudioPlayer()
        player.load_track(1, Path("/fake/track.wav"))

        assert 1 in player.state.tracks
        assert player.state.tracks[1].track_number == 1
        assert player.state.tracks[1].playing is False

    def test_toggle_track_starts_playing(self, mock_sounddevice, mock_soundfile):
        """Test that toggling a track starts it playing."""
        player = AudioPlayer()
        player.load_track(1, Path("/fake/track.wav"))

        player.toggle_track(1)

        assert player.state.tracks[1].playing is True
        assert player.state.master_playing is True

    def test_toggle_track_stops_playing(self, mock_sounddevice, mock_soundfile):
        """Test that toggling a playing track stops it."""
        player = AudioPlayer()
        player.load_track(1, Path("/fake/track.wav"))

        player.toggle_track(1)  # Start
        player.toggle_track(1)  # Stop

        assert player.state.tracks[1].playing is False
        assert player.state.master_playing is False

    def test_master_position_resets_when_all_stopped(self, mock_sounddevice, mock_soundfile):
        """Test that master position resets when all tracks stop."""
        player = AudioPlayer()
        player.load_track(1, Path("/fake/track.wav"))

        # Simulate some playback by advancing master position
        player.toggle_track(1)
        player.state.master_position = 10000

        # Stop track
        player.toggle_track(1)

        assert player.state.master_position == 0

    def test_stop_all_resets_master_position(self, mock_sounddevice, mock_soundfile):
        """Test that stop_all resets master position."""
        player = AudioPlayer()
        player.load_track(1, Path("/fake/track.wav"))
        player.load_track(2, Path("/fake/track2.wav"))

        player.play_all()
        player.state.master_position = 50000

        player.stop_all()

        assert player.state.master_position == 0
        assert player.state.master_playing is False

    def test_toggle_all_resets_master_position_on_stop(self, mock_sounddevice, mock_soundfile):
        """Test that toggle_all resets master position when stopping."""
        player = AudioPlayer()
        player.load_track(1, Path("/fake/track.wav"))
        player.load_track(2, Path("/fake/track2.wav"))

        player.toggle_all()  # Start all
        player.state.master_position = 30000

        player.toggle_all()  # Stop all

        assert player.state.master_position == 0
        assert player.state.master_playing is False


class TestAudioPlayerSync:
    """Tests for track synchronization."""

    def test_tracks_share_master_position(self, mock_sounddevice, mock_soundfile):
        """Test that multiple tracks use the same master position for sync."""
        player = AudioPlayer()
        player.load_track(1, Path("/fake/track1.wav"))
        player.load_track(2, Path("/fake/track2.wav"))

        # Start first track
        player.toggle_track(1)

        # Simulate playback advancing
        player.state.master_position = 22050  # Half a second

        # Start second track - it should sync to master position
        player.toggle_track(2)

        # Both tracks should be playing
        assert player.state.tracks[1].playing is True
        assert player.state.tracks[2].playing is True

        # Master position should be preserved (not reset)
        assert player.state.master_position == 22050

    def test_audio_callback_uses_master_position(self, mock_sounddevice, mock_soundfile):
        """Test that audio callback derives track position from master."""
        player = AudioPlayer()

        # Create track with known data
        track_data = np.arange(44100 * 2, dtype='float32').reshape(-1, 2)
        mock_soundfile.read.return_value = (track_data, 44100)

        player.load_track(1, Path("/fake/track.wav"))
        player.toggle_track(1)

        # Set master position
        player.state.master_position = 1000

        # Simulate audio callback
        outdata = np.zeros((512, 2), dtype='float32')
        player._audio_callback(outdata, 512, None, None)

        # Master position should have advanced
        assert player.state.master_position == 1000 + 512

    def test_audio_callback_wraps_track_position(self, mock_sounddevice, mock_soundfile):
        """Test that track position wraps correctly for shorter tracks."""
        player = AudioPlayer()

        # Create short track (1000 samples)
        track_data = np.ones((1000, 2), dtype='float32') * 0.5
        mock_soundfile.read.return_value = (track_data, 44100)

        player.load_track(1, Path("/fake/track.wav"))
        player.toggle_track(1)

        # Set master position beyond track length
        player.state.master_position = 1500

        # Simulate audio callback
        outdata = np.zeros((100, 2), dtype='float32')
        player._audio_callback(outdata, 100, None, None)

        # Track position should be wrapped (1500 % 1000 = 500, then +100 = 600)
        assert player.state.tracks[1].position == 600

    def test_new_track_syncs_to_existing_playback(self, mock_sounddevice, mock_soundfile):
        """Test that a newly started track syncs to existing playback position."""
        player = AudioPlayer()

        # Load two tracks with same length
        track_data = np.ones((44100, 2), dtype='float32')
        mock_soundfile.read.return_value = (track_data, 44100)

        player.load_track(1, Path("/fake/track1.wav"))
        player.load_track(2, Path("/fake/track2.wav"))

        # Start track 1 and advance
        player.toggle_track(1)
        player.state.master_position = 11025  # Quarter second

        # Simulate callback to update track 1 position
        outdata = np.zeros((512, 2), dtype='float32')
        player._audio_callback(outdata, 512, None, None)

        # Now start track 2
        player.toggle_track(2)

        # Run another callback
        player._audio_callback(outdata, 512, None, None)

        # Both tracks should have similar positions (derived from same master)
        pos1 = player.state.tracks[1].position
        pos2 = player.state.tracks[2].position

        # They should be equal since they have the same length and share master position
        assert pos1 == pos2
