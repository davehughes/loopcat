"""Audio playback engine for loopcat."""

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf


@dataclass
class TrackState:
    """State of a single track."""

    track_number: int
    file_path: Path
    duration: float
    sample_rate: int
    channels: int
    data: np.ndarray
    playing: bool = False
    position: int = 0  # Current sample position
    loop: bool = True


@dataclass
class PlayerState:
    """State of the audio player."""

    tracks: dict[int, TrackState] = field(default_factory=dict)
    master_playing: bool = False
    loop: bool = True
    _stream: Optional[sd.OutputStream] = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _on_position_update: Optional[Callable] = None


class AudioPlayer:
    """Multi-track audio player mimicking RC-300 behavior."""

    def __init__(self, on_position_update: Optional[Callable] = None):
        """Initialize the audio player.

        Args:
            on_position_update: Callback called periodically with position updates.
        """
        self.state = PlayerState()
        self.state._on_position_update = on_position_update
        self._sample_rate = 44100
        self._channels = 2
        self._block_size = 1024
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def load_track(self, track_number: int, file_path: Path) -> None:
        """Load a track from a WAV file.

        Args:
            track_number: Track number (1, 2, or 3).
            file_path: Path to the WAV file.
        """
        data, sample_rate = sf.read(file_path, dtype="float32")

        # Convert mono to stereo if needed
        if len(data.shape) == 1:
            data = np.column_stack([data, data])

        # Resample if needed (simple approach - just store original rate)
        duration = len(data) / sample_rate

        with self.state._lock:
            self.state.tracks[track_number] = TrackState(
                track_number=track_number,
                file_path=file_path,
                duration=duration,
                sample_rate=sample_rate,
                channels=data.shape[1] if len(data.shape) > 1 else 1,
                data=data,
                playing=False,
                position=0,
                loop=self.state.loop,
            )

        # Update player sample rate to match first track
        if len(self.state.tracks) == 1:
            self._sample_rate = sample_rate

    def _audio_callback(self, outdata: np.ndarray, frames: int, time_info, status) -> None:
        """Audio stream callback - mixes all playing tracks."""
        outdata.fill(0)

        with self.state._lock:
            for track in self.state.tracks.values():
                if not track.playing:
                    continue

                # Get the chunk of audio for this track
                start = track.position
                end = start + frames

                if end <= len(track.data):
                    # Normal playback
                    chunk = track.data[start:end]
                    track.position = end
                elif track.loop:
                    # Loop: wrap around
                    remaining = len(track.data) - start
                    if remaining > 0:
                        chunk = np.vstack([
                            track.data[start:],
                            track.data[: frames - remaining],
                        ])
                    else:
                        chunk = track.data[: frames]
                    track.position = (end) % len(track.data)
                else:
                    # No loop: play what's left, then stop
                    chunk = np.zeros((frames, 2), dtype="float32")
                    remaining = len(track.data) - start
                    if remaining > 0:
                        chunk[:remaining] = track.data[start:]
                    track.playing = False
                    track.position = 0

                # Mix into output (simple sum, could add volume control)
                if len(chunk) == frames:
                    outdata[:] += chunk

        # Clamp to prevent clipping
        np.clip(outdata, -1.0, 1.0, out=outdata)

    def _position_update_loop(self) -> None:
        """Background thread to send position updates."""
        while self._running:
            if self.state._on_position_update:
                positions = {}
                with self.state._lock:
                    for num, track in self.state.tracks.items():
                        positions[num] = (
                            track.position / track.sample_rate,
                            track.duration,
                            track.playing,
                        )
                self.state._on_position_update(positions)
            time.sleep(0.05)  # 20 updates per second

    def start(self) -> None:
        """Start the audio stream."""
        if self.state._stream is not None:
            return

        self._running = True
        self.state._stream = sd.OutputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            callback=self._audio_callback,
            blocksize=self._block_size,
            dtype="float32",
        )
        self.state._stream.start()

        # Start position update thread
        self._thread = threading.Thread(target=self._position_update_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the audio stream."""
        self._running = False
        if self.state._stream is not None:
            self.state._stream.stop()
            self.state._stream.close()
            self.state._stream = None

    def play_track(self, track_number: int) -> None:
        """Start playing a specific track.

        Args:
            track_number: Track number to play.
        """
        with self.state._lock:
            if track_number in self.state.tracks:
                self.state.tracks[track_number].playing = True
                self.state.master_playing = True

    def stop_track(self, track_number: int) -> None:
        """Stop a specific track.

        Args:
            track_number: Track number to stop.
        """
        with self.state._lock:
            if track_number in self.state.tracks:
                self.state.tracks[track_number].playing = False
                self.state.tracks[track_number].position = 0

            # Update master state
            self.state.master_playing = any(t.playing for t in self.state.tracks.values())

    def toggle_track(self, track_number: int) -> None:
        """Toggle a track's play state.

        Args:
            track_number: Track number to toggle.
        """
        with self.state._lock:
            if track_number in self.state.tracks:
                track = self.state.tracks[track_number]
                if track.playing:
                    track.playing = False
                    track.position = 0
                else:
                    track.playing = True

                self.state.master_playing = any(t.playing for t in self.state.tracks.values())

    def play_all(self) -> None:
        """Start all tracks."""
        with self.state._lock:
            for track in self.state.tracks.values():
                track.playing = True
            self.state.master_playing = True

    def stop_all(self) -> None:
        """Stop all tracks and reset positions."""
        with self.state._lock:
            for track in self.state.tracks.values():
                track.playing = False
                track.position = 0
            self.state.master_playing = False

    def toggle_all(self) -> None:
        """Toggle all tracks (RC-300 style all start/stop)."""
        with self.state._lock:
            if self.state.master_playing:
                for track in self.state.tracks.values():
                    track.playing = False
                    track.position = 0
                self.state.master_playing = False
            else:
                for track in self.state.tracks.values():
                    track.playing = True
                self.state.master_playing = True

    def set_loop(self, loop: bool) -> None:
        """Set loop mode for all tracks.

        Args:
            loop: Whether to loop playback.
        """
        with self.state._lock:
            self.state.loop = loop
            for track in self.state.tracks.values():
                track.loop = loop

    def is_playing(self, track_number: Optional[int] = None) -> bool:
        """Check if a track (or any track) is playing.

        Args:
            track_number: Specific track to check, or None for any.

        Returns:
            True if playing.
        """
        with self.state._lock:
            if track_number is not None:
                return self.state.tracks.get(track_number, TrackState(0, Path(), 0, 0, 0, np.array([]))).playing
            return self.state.master_playing

    def get_track_info(self, track_number: int) -> Optional[tuple[float, float, bool]]:
        """Get track position info.

        Args:
            track_number: Track number.

        Returns:
            Tuple of (current_position_seconds, duration_seconds, is_playing) or None.
        """
        with self.state._lock:
            track = self.state.tracks.get(track_number)
            if track:
                return (
                    track.position / track.sample_rate,
                    track.duration,
                    track.playing,
                )
            return None
