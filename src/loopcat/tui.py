"""TUI player for loopcat - mimics RC-300 controls."""

from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from loopcat.base16_themes import BASE16_THEMES
from loopcat.config import get_theme, set_theme
from loopcat.models import Patch, Track
from loopcat.player import AudioPlayer


class TrackWidget(Static):
    """Widget displaying a single track with playback controls."""

    def __init__(
        self,
        track: Track,
        track_number: int,
        **kwargs,
    ) -> None:
        # Build initial content first
        name = track.analysis.suggested_name if track.analysis else track.filename
        initial = f"[bold white on dark_red] {track_number} [/] [bold]{name}[/]  [dim]⏹ STOPPED[/]\n[cyan]{'░' * 20}[/] 0.0s / 0.0s"
        super().__init__(initial, **kwargs)
        # Set instance attributes after super().__init__
        self.track = track
        self.track_number = track_number
        self._position = 0.0
        self._duration = 1.0
        self._playing = False

    def _refresh_display(self) -> None:
        """Render the track display."""
        name = self.track.analysis.suggested_name if self.track.analysis else self.track.filename
        role = self.track.analysis.role if self.track.analysis else ""
        key = self.track.detected_key or ""

        info_parts = [p for p in [role, key] if p]
        info_str = f" ({', '.join(info_parts)})" if info_parts else ""

        if self._playing:
            status = "[bold green]▶ PLAYING[/]"
            header = f"[bold white on dark_green] {self.track_number} [/] [bold green]{name}[/]{info_str}"
        else:
            status = "[dim]⏹ STOPPED[/]"
            header = f"[bold white on dark_red] {self.track_number} [/] [bold]{name}[/]{info_str}"

        pct = int((self._position / self._duration * 100) if self._duration > 0 else 0)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        time_str = f"{self._position:.1f}s / {self._duration:.1f}s"
        bar_color = "cyan" if self._playing else "dim"

        self.update(f"{header}  {status}\n[{bar_color}]{bar}[/] {time_str}")

    def update_state(self, position: float, duration: float, playing: bool) -> None:
        """Update the track display state."""
        self._position = position
        self._duration = duration
        self._playing = playing
        self._refresh_display()


# Built-in Textual themes + base16 themes (deduplicated)
BUILTIN_THEMES = [
    "textual-dark", "textual-light", "nord", "gruvbox", "dracula",
    "tokyo-night", "monokai", "catppuccin-mocha", "catppuccin-latte",
    "solarized-dark", "solarized-light", "rose-pine", "rose-pine-moon",
    "rose-pine-dawn", "atom-one-dark", "atom-one-light", "flexoki", "textual-ansi",
]
_builtin_set = set(BUILTIN_THEMES)
THEMES = BUILTIN_THEMES + [t.name for t in BASE16_THEMES if t.name not in _builtin_set]


class ThemePickerScreen(ModalScreen[str | None]):
    """Modal screen for selecting a theme with search and live preview."""

    CSS = """
    ThemePickerScreen {
        align: center middle;
    }

    #theme-dialog {
        width: 60;
        height: 80%;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    #theme-search {
        dock: top;
        margin-bottom: 1;
    }

    #theme-list {
        height: 1fr;
    }

    #theme-hint {
        dock: bottom;
        height: 1;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select", "Select", priority=True),
        Binding("down", "cursor_down", show=False),
        Binding("up", "cursor_up", show=False),
        Binding("ctrl+j", "cursor_down", show=False),
        Binding("ctrl+k", "cursor_up", show=False, priority=True),
        Binding("ctrl+n", "cursor_down", show=False),
    ]

    def __init__(self, current_theme: str) -> None:
        super().__init__()
        self.current_theme = current_theme
        self.filter_text = ""

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="theme-dialog"):
            yield Input(placeholder="Type to filter themes...", id="theme-search")
            yield OptionList(*[Option(t, id=t) for t in THEMES], id="theme-list")
            yield Static("[dim]Enter[/] Select  [dim]Esc[/] Cancel", id="theme-hint")

    def on_mount(self) -> None:
        # Focus search and highlight current theme after children are ready
        self.call_after_refresh(self._setup_initial_state)

    def _setup_initial_state(self) -> None:
        """Set initial focus and selection after widgets are ready."""
        self.query_one("#theme-search", Input).focus()
        option_list = self.query_one("#theme-list", OptionList)
        try:
            idx = THEMES.index(self.current_theme)
            option_list.highlighted = idx
        except ValueError:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter themes as user types."""
        self.filter_text = event.value.lower()
        option_list = self.query_one("#theme-list", OptionList)
        option_list.clear_options()
        filtered = [t for t in THEMES if self.filter_text in t.lower()]
        option_list.add_options([Option(t, id=t) for t in filtered])
        if filtered:
            option_list.highlighted = 0

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Preview theme as user navigates."""
        if event.option:
            self.app.theme = event.option.id

    def _move_highlight(self, delta: int) -> None:
        """Move the option list highlight by delta."""
        option_list = self.query_one("#theme-list", OptionList)
        if option_list.option_count == 0:
            return
        if option_list.highlighted is None:
            option_list.highlighted = 0
        else:
            new_idx = option_list.highlighted + delta
            option_list.highlighted = max(0, min(new_idx, option_list.option_count - 1))

    def action_cursor_down(self) -> None:
        """Move cursor down in the option list."""
        self._move_highlight(1)

    def action_cursor_up(self) -> None:
        """Move cursor up in the option list."""
        self._move_highlight(-1)

    def action_cancel(self) -> None:
        """Cancel and restore original theme."""
        self.app.theme = self.current_theme
        self.dismiss(None)

    def action_select(self) -> None:
        """Select the highlighted theme."""
        option_list = self.query_one("#theme-list", OptionList)
        if option_list.highlighted is not None and option_list.option_count > 0:
            option = option_list.get_option_at_index(option_list.highlighted)
            if option:
                self.dismiss(option.id)
                return
        self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle double-click/enter on option."""
        if event.option:
            self.dismiss(event.option.id)


class PlayerApp(App):
    """TUI application for playing patches."""

    CSS = """
    Screen {
        background: $surface;
    }

    #header {
        dock: top;
        height: 1;
        background: $primary;
        padding: 0 1;
    }

    #tracks-container {
        padding: 0 1;
    }

    TrackWidget {
        padding: 0 1;
        border: solid $primary;
        height: auto;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_all", "All"),
        Binding("1", "toggle_track_1", "Trk1"),
        Binding("2", "toggle_track_2", "Trk2"),
        Binding("3", "toggle_track_3", "Trk3"),
        Binding("l", "toggle_loop", "Loop"),
        Binding("t", "cycle_theme", "Theme"),
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
        # Register base16 themes
        for theme in BASE16_THEMES:
            self.register_theme(theme)
        self.theme = get_theme()
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
        # Header (single line)
        patch_name = self.patch.analysis.suggested_name if self.patch.analysis else f"Patch #{self.patch.catalog_number}"
        bpm_str = f" {self.patch.tracks[0].bpm:.0f}bpm" if self.patch.tracks and self.patch.tracks[0].bpm else ""
        yield Static(
            f"[bold]LOOPCAT[/] │ {patch_name} (#{self.patch.catalog_number}){bpm_str}",
            id="header",
        )

        # Tracks
        with VerticalScroll(id="tracks-container"):
            for track in sorted(self.patch.tracks, key=lambda t: t.track_number):
                widget = TrackWidget(track, track.track_number, id=f"track-{track.track_number}")
                self.track_widgets[track.track_number] = widget
                yield widget

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

    def action_cycle_theme(self) -> None:
        """Open theme picker."""
        self.push_screen(ThemePickerScreen(self.theme), self._on_theme_selected)

    def _on_theme_selected(self, theme: str | None) -> None:
        """Handle theme selection from picker."""
        if theme:
            self.theme = theme
            set_theme(theme)
            self.notify(f"Theme: {theme}")

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
