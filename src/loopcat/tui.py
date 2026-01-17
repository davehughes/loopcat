"""TUI player for loopcat - mimics RC-300 controls."""

from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Label, ProgressBar, Static

from loopcat.models import Patch, Track
from loopcat.player import AudioPlayer


class TrackWidget(Static):
    """Widget displaying a single track with playback controls."""

    position = reactive(0.0)
    duration = reactive(1.0)
    playing = reactive(False)

    def __init__(
        self,
        track: Track,
        track_number: int,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.track = track
        self.track_number = track_number
        self._is_playing = False

    def compose(self) -> ComposeResult:
        # Track name and info
        name = self.track.analysis.suggested_name if self.track.analysis else self.track.filename
        role = self.track.analysis.role if self.track.analysis else ""
        key = self.track.detected_key or ""

        info_parts = [p for p in [role, key] if p]
        info_str = " • ".join(info_parts) if info_parts else ""

        with Container(classes="track-container", id=f"container-{self.track_number}"):
            with Horizontal(classes="track-header"):
                yield Label(
                    f"[bold white on dark_red] {self.track_number} [/] [bold]{name}[/]",
                    id=f"track-label-{self.track_number}",
                    classes="track-name",
                )
                yield Label("[dim]⏹ STOPPED[/]", id=f"status-{self.track_number}", classes="track-status")
            if info_str:
                yield Label(f"[dim]{info_str}[/]", classes="track-info")
            with Horizontal(classes="track-progress"):
                yield ProgressBar(total=100, show_eta=False, id=f"progress-{self.track_number}")
                yield Label("0.0s / 0.0s", id=f"time-{self.track_number}", classes="track-time")

    def update_state(self, position: float, duration: float, playing: bool) -> None:
        """Update the track display state."""
        self.position = position
        self.duration = duration
        self.playing = playing

        # Update progress bar
        progress = self.query_one(f"#progress-{self.track_number}", ProgressBar)
        pct = (position / duration * 100) if duration > 0 else 0
        progress.progress = pct

        # Update time display
        time_label = self.query_one(f"#time-{self.track_number}", Label)
        time_label.update(f"{position:.1f}s / {duration:.1f}s")

        # Update status and track label styling
        status_label = self.query_one(f"#status-{self.track_number}", Label)
        track_label = self.query_one(f"#track-label-{self.track_number}", Label)
        container = self.query_one(f"#container-{self.track_number}", Container)
        name = self.track.analysis.suggested_name if self.track.analysis else self.track.filename

        if playing != self._is_playing:
            self._is_playing = playing
            if playing:
                status_label.update("[bold green]▶ PLAYING[/]")
                track_label.update(f"[bold white on dark_green] {self.track_number} [/] [bold green]{name}[/]")
                container.add_class("playing")
                container.remove_class("stopped")
            else:
                status_label.update("[dim]⏹ STOPPED[/]")
                track_label.update(f"[bold white on dark_red] {self.track_number} [/] [bold]{name}[/]")
                container.remove_class("playing")
                container.add_class("stopped")


class PlayerApp(App):
    """TUI application for playing patches."""

    CSS = """
    Screen {
        background: $surface;
    }

    #header {
        dock: top;
        height: 3;
        background: $primary;
        padding: 0 1;
    }

    #header-content {
        width: 100%;
    }

    .logo {
        color: $text;
    }

    .patch-info {
        text-align: right;
        width: 100%;
    }

    #tracks-container {
        padding: 1 2;
    }

    .track-container {
        margin-bottom: 1;
        padding: 1;
        border: solid $error;
        height: auto;
    }

    .track-container.playing {
        border: solid $success;
        background: $success 10%;
    }

    .track-container.stopped {
        border: solid $error;
        background: $surface;
    }

    .track-header {
        width: 100%;
    }

    .track-name {
        width: 1fr;
    }

    .track-status {
        width: auto;
        text-align: right;
    }

    .track-info {
        margin-top: 0;
    }

    .track-progress {
        margin-top: 1;
        width: 100%;
    }

    .track-time {
        width: 16;
        text-align: right;
    }

    ProgressBar {
        width: 1fr;
        padding-right: 1;
    }

    ProgressBar > .bar--complete {
        color: $success;
    }

    #controls-hint {
        dock: bottom;
        height: 3;
        background: $surface-darken-1;
        padding: 1;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_all", "All Play/Stop"),
        Binding("1", "toggle_track_1", "Track 1", show=False),
        Binding("2", "toggle_track_2", "Track 2", show=False),
        Binding("3", "toggle_track_3", "Track 3", show=False),
        Binding("l", "toggle_loop", "Loop"),
        Binding("left", "prev_patch", "Prev"),
        Binding("right", "next_patch", "Next"),
        Binding("escape", "back_to_list", "Back"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        patch: Patch,
        all_patches: Optional[list[Patch]] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.patch = patch
        self.all_patches = all_patches or [patch]
        self.current_patch_index = next(
            (i for i, p in enumerate(self.all_patches) if p.id == patch.id),
            0,
        )
        self.player: Optional[AudioPlayer] = None
        self.track_widgets: dict[int, TrackWidget] = {}
        self.loop_mode = True

    def compose(self) -> ComposeResult:
        # Header
        patch_name = self.patch.analysis.suggested_name if self.patch.analysis else f"Patch #{self.patch.catalog_number}"
        bpm_str = ""
        if self.patch.tracks and self.patch.tracks[0].bpm:
            bpm_str = f" │ {self.patch.tracks[0].bpm:.0f} BPM"

        with Container(id="header"):
            with Horizontal(id="header-content"):
                yield Label("[bold]∞╱╲_╱╲∞ LOOPCAT[/]", classes="logo")
                yield Label(
                    f"[bold]{patch_name}[/] (#{self.patch.catalog_number}){bpm_str}",
                    classes="patch-info",
                )

        # Tracks
        with Vertical(id="tracks-container"):
            for track in sorted(self.patch.tracks, key=lambda t: t.track_number):
                widget = TrackWidget(track, track.track_number, id=f"track-{track.track_number}")
                self.track_widgets[track.track_number] = widget
                yield widget

        # Controls hint
        yield Static(
            "[bold]SPACE[/] All Play/Stop  │  [bold]1-3[/] Toggle Track  │  "
            "[bold]←/→[/] Prev/Next  │  [bold]L[/] Loop  │  [bold]ESC[/] Back  │  [bold]Q[/] Quit",
            id="controls-hint",
        )

        yield Footer()

    def on_mount(self) -> None:
        """Initialize audio player when app starts."""
        self.player = AudioPlayer(on_position_update=self._on_position_update)

        # Load all tracks
        for track in self.patch.tracks:
            wav_path = Path(track.wav_path)
            if wav_path.exists():
                self.player.load_track(track.track_number, wav_path)

        # Set initial stopped state for all tracks
        for track_num, widget in self.track_widgets.items():
            info = self.player.get_track_info(track_num)
            if info:
                widget.update_state(0.0, info[1], False)

        self.player.start()

    def on_unmount(self) -> None:
        """Clean up audio player when app exits."""
        if self.player:
            self.player.stop()

    def _on_position_update(self, positions: dict[int, tuple[float, float, bool]]) -> None:
        """Handle position updates from audio player."""
        self.call_from_thread(self._update_track_displays, positions)

    def _update_track_displays(self, positions: dict[int, tuple[float, float, bool]]) -> None:
        """Update track widgets with new positions."""
        for track_num, (position, duration, playing) in positions.items():
            if track_num in self.track_widgets:
                self.track_widgets[track_num].update_state(position, duration, playing)

    def action_toggle_all(self) -> None:
        """Toggle all tracks."""
        if self.player:
            self.player.toggle_all()

    def action_toggle_track_1(self) -> None:
        """Toggle track 1."""
        if self.player:
            self.player.toggle_track(1)

    def action_toggle_track_2(self) -> None:
        """Toggle track 2."""
        if self.player:
            self.player.toggle_track(2)

    def action_toggle_track_3(self) -> None:
        """Toggle track 3."""
        if self.player:
            self.player.toggle_track(3)

    def action_toggle_loop(self) -> None:
        """Toggle loop mode."""
        if self.player:
            self.loop_mode = not self.loop_mode
            self.player.set_loop(self.loop_mode)
            self.notify(f"Loop: {'ON' if self.loop_mode else 'OFF'}")

    def action_prev_patch(self) -> None:
        """Go to previous patch."""
        if self.current_patch_index > 0:
            self._switch_patch(self.current_patch_index - 1)

    def action_next_patch(self) -> None:
        """Go to next patch."""
        if self.current_patch_index < len(self.all_patches) - 1:
            self._switch_patch(self.current_patch_index + 1)

    def _switch_patch(self, new_index: int) -> None:
        """Switch to a different patch."""
        if self.player:
            self.player.stop()

        self.current_patch_index = new_index
        self.patch = self.all_patches[new_index]

        # Restart app with new patch (simple approach)
        self.exit(result=("switch", self.patch))

    def action_back_to_list(self) -> None:
        """Go back to patch selector."""
        if self.player:
            self.player.stop()
        self.exit(result="back")

    def action_quit(self) -> None:
        """Quit the player."""
        if self.player:
            self.player.stop()
        self.exit()


def run_player(patch: Patch, all_patches: Optional[list[Patch]] = None) -> Optional[str]:
    """Run the TUI player for a patch.

    Args:
        patch: The patch to play.
        all_patches: All patches for prev/next navigation.

    Returns:
        "back" if user wants to return to patch selector, None otherwise.
    """
    current_patch = patch
    patches = all_patches or [patch]

    while True:
        app = PlayerApp(current_patch, patches)
        result = app.run()

        if isinstance(result, tuple) and result[0] == "switch":
            current_patch = result[1]
        elif result == "back":
            return "back"
        else:
            return None
