"""TUI player for loopcat - mimics RC-300 controls."""

from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from loopcat.base16_themes import BASE16_THEMES
from loopcat.config import get_theme, set_theme
from loopcat.models import Patch, Track
from loopcat.player import AudioPlayer


class TrackWidget(Static):
    """Widget displaying a single track status."""

    def __init__(
        self,
        track: Track,
        track_number: int,
        **kwargs,
    ) -> None:
        # Build initial content first
        name = track.analysis.suggested_name if track.analysis else track.filename
        initial = f"[dim]⏹[/]  [bold white on $error] {track_number} [/] [bold]{name}[/]"
        super().__init__(initial, **kwargs)
        # Set instance attributes after super().__init__
        self.track = track
        self.track_number = track_number
        self._playing = False

    def _refresh_display(self) -> None:
        """Render the track display."""
        name = self.track.analysis.suggested_name if self.track.analysis else self.track.filename
        role = self.track.analysis.role if self.track.analysis else ""
        key = self.track.detected_key or ""

        info_parts = [p for p in [role, key] if p]
        info_str = f" [dim]({', '.join(info_parts)})[/]" if info_parts else ""

        if self._playing:
            status = "[bold $success]▶[/]"
            header = f"[bold white on $success] {self.track_number} [/] [bold $success]{name}[/]{info_str}"
        else:
            status = "[dim]⏹[/]"
            header = f"[bold white on $error] {self.track_number} [/] [bold]{name}[/]{info_str}"

        self.update(f"{status}  {header}")

    def update_state(self, playing: bool) -> None:
        """Update the track display state."""
        self._playing = playing
        self._refresh_display()


class ProgressBarWidget(Static):
    """Widget displaying the master playback progress bar."""

    def __init__(self, **kwargs) -> None:
        super().__init__("[dim]░[/] " * 30 + " 0.0s", **kwargs)
        self._position = 0.0
        self._duration = 1.0
        self._playing = False

    def update_state(self, position: float, duration: float, playing: bool) -> None:
        """Update the progress bar display."""
        self._position = position
        self._duration = duration
        self._playing = playing
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Render the progress bar."""
        pct = int((self._position / self._duration * 100) if self._duration > 0 else 0)
        filled = pct * 30 // 100
        bar = "█" * filled + "░" * (30 - filled)
        time_str = f"{self._position:.1f}s / {self._duration:.1f}s"
        bar_color = "$accent" if self._playing else "dim"

        self.update(f"[{bar_color}]{bar}[/] {time_str}")


class ControlsFooter(Static):
    """Custom footer widget with grouped controls."""

    DEFAULT_CSS = """
    ControlsFooter {
        dock: bottom;
        height: 1;
        background: $primary;
        padding: 0 1;
    }
    """

    def __init__(self, content: Optional[str] = None, **kwargs) -> None:
        if content is None:
            content = (
                "[dim]track[/] [bold]1[/] [bold]2[/] [bold]3[/]  "
                "[dim]start/stop all[/] [bold]␣[/]  "
                "[dim]patch[/] [bold]h[/] [bold]←[/] [bold]→[/] [bold]l[/]  "
                "[bold]t[/] [dim]theme[/]  "
                "[bold]q[/] [bold],[/] [dim]choose[/]  "
                "[bold]esc[/] [dim]quit[/]"
            )
        super().__init__(content, **kwargs)


# Built-in Textual themes + base16 themes (deduplicated)
BUILTIN_THEMES = [
    "textual-dark",
    "textual-light",
    "nord",
    "gruvbox",
    "dracula",
    "tokyo-night",
    "monokai",
    "catppuccin-mocha",
    "catppuccin-latte",
    "solarized-dark",
    "solarized-light",
    "rose-pine",
    "rose-pine-moon",
    "rose-pine-dawn",
    "atom-one-dark",
    "atom-one-light",
    "flexoki",
    "textual-ansi",
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
        Binding("ctrl+d", "page_down", show=False, priority=True),
        Binding("ctrl+u", "page_up", show=False, priority=True),
    ]

    def __init__(self, current_theme: str) -> None:
        super().__init__()
        self.current_theme = current_theme
        self.filter_text = ""

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="theme-dialog"):
            yield Input(placeholder="Type to filter themes...", id="theme-search")
            yield OptionList(*[Option(t, id=t) for t in THEMES], id="theme-list")
            yield Static("[dim]enter[/] select  [dim]esc[/] cancel", id="theme-hint")

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

    def action_page_down(self) -> None:
        """Move cursor down by 10 in the option list."""
        self._move_highlight(10)

    def action_page_up(self) -> None:
        """Move cursor up by 10 in the option list."""
        self._move_highlight(-10)

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


class PatchPickerScreen(Screen):
    """Screen for selecting a patch to play."""

    CSS = """
    PatchPickerScreen {
        background: $surface;
    }

    #picker-header {
        dock: top;
        height: 1;
        background: $primary;
        padding: 0 1;
    }

    #picker-container {
        padding: 1;
    }

    #patch-search {
        dock: top;
        margin-bottom: 1;
    }

    #patch-list {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("escape", "quit", show=False),
        Binding("enter", "select", "Select", priority=True),
        Binding("down", "cursor_down", show=False),
        Binding("up", "cursor_up", show=False),
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
        Binding("ctrl+j", "cursor_down", show=False),
        Binding("ctrl+k", "cursor_up", show=False, priority=True),
        Binding("ctrl+n", "cursor_down", show=False),
        Binding("ctrl+d", "page_down", show=False, priority=True),
        Binding("ctrl+u", "page_up", show=False, priority=True),
        Binding("t", "cycle_theme", show=False),
    ]

    def __init__(self, patches: list[Patch], selected_index: int = 0) -> None:
        super().__init__()
        self.patches = patches
        self.selected_index = selected_index
        self.filter_text = ""
        self._filtered_patches = patches.copy()

    def compose(self) -> ComposeResult:
        yield Static("🐱[bold] loopcat[/] │ Select a patch to play", id="picker-header")

        with VerticalScroll(id="picker-container"):
            yield Input(placeholder="Type to filter patches...", id="patch-search")
            yield OptionList(*self._build_options(), id="patch-list")
        yield ControlsFooter(
            "[bold]C-j[/] [bold]↓[/] [bold]↑[/] [bold]C-k[/] [dim]navigate[/]  "
            "[bold]C-d[/] [bold]C-u[/] [dim]fast[/]  "
            "[bold]enter[/] [dim]play[/]  "
            "[bold]t[/] [dim]theme[/]  "
            "[bold]esc[/] [dim]quit[/]"
        )

    def _build_options(self) -> list[Option]:
        """Build option list entries from patches."""
        options = []
        for p in self._filtered_patches:
            name = p.analysis.suggested_name if p.analysis else f"Patch #{p.catalog_number}"
            track_count = len(p.tracks)
            total_duration = sum(t.duration_seconds for t in p.tracks)
            label = f"#{p.catalog_number:3d}  {name[:40]:<40}  {track_count} track(s), {total_duration:.1f}s"
            options.append(Option(label, id=p.id))
        return options

    def on_mount(self) -> None:
        self.call_after_refresh(self._setup_initial_state)

    def _setup_initial_state(self) -> None:
        """Set initial focus and selection."""
        self.query_one("#patch-search", Input).focus()
        option_list = self.query_one("#patch-list", OptionList)
        if option_list.option_count > 0 and self.selected_index < option_list.option_count:
            option_list.highlighted = self.selected_index

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter patches as user types."""
        self.filter_text = event.value.lower()
        option_list = self.query_one("#patch-list", OptionList)
        option_list.clear_options()

        self._filtered_patches = [
            p
            for p in self.patches
            if self.filter_text in (p.analysis.suggested_name if p.analysis else f"Patch #{p.catalog_number}").lower()
        ]
        option_list.add_options(self._build_options())
        if self._filtered_patches:
            option_list.highlighted = 0

    def _move_highlight(self, delta: int) -> None:
        """Move the option list highlight by delta."""
        option_list = self.query_one("#patch-list", OptionList)
        if option_list.option_count == 0:
            return
        if option_list.highlighted is None:
            option_list.highlighted = 0
        else:
            new_idx = option_list.highlighted + delta
            option_list.highlighted = max(0, min(new_idx, option_list.option_count - 1))

    def action_cursor_down(self) -> None:
        self._move_highlight(1)

    def action_cursor_up(self) -> None:
        self._move_highlight(-1)

    def action_page_down(self) -> None:
        self._move_highlight(10)

    def action_page_up(self) -> None:
        self._move_highlight(-10)

    def action_quit(self) -> None:
        self.app.exit()

    def action_select(self) -> None:
        """Select the highlighted patch and switch to player."""
        option_list = self.query_one("#patch-list", OptionList)
        if option_list.highlighted is not None and option_list.option_count > 0:
            option = option_list.get_option_at_index(option_list.highlighted)
            if option:
                # Find the patch by id
                patch = next((p for p in self._filtered_patches if p.id == option.id), None)
                if patch:
                    # Find index in original list
                    idx = next((i for i, p in enumerate(self.patches) if p.id == patch.id), 0)
                    self.app.push_screen(PlayerScreen(patch, self.patches, idx))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle double-click/enter on option."""
        self.action_select()

    def action_cycle_theme(self) -> None:
        """Open theme picker."""
        self.app.push_screen(ThemePickerScreen(self.app.theme), self._on_theme_selected)

    def _on_theme_selected(self, theme: str | None) -> None:
        """Handle theme selection from picker."""
        if theme:
            self.app.theme = theme
            set_theme(theme)
            self.app.notify(f"Theme: {theme}")


class PlayerScreen(Screen):
    """Screen for playing a patch with TUI controls."""

    CSS = """
    PlayerScreen {
        background: $surface;
    }

    #header {
        dock: top;
        height: 1;
        background: $primary;
        padding: 0 1;
    }

    #progress-bar {
        dock: top;
        height: auto;
        padding: 0 1;
        margin: 1 1 0 1;
        border: solid $primary;
    }

    #tracks-container {
        padding: 0 1;
    }

    TrackWidget {
        padding: 0 1;
        height: auto;
        border-bottom: solid $primary;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_all", show=False),
        Binding("1", "toggle_track_1", show=False),
        Binding("2", "toggle_track_2", show=False),
        Binding("3", "toggle_track_3", show=False),
        Binding("t", "cycle_theme", show=False),
        Binding("left", "prev_patch", show=False),
        Binding("right", "next_patch", show=False),
        Binding("h", "prev_patch", show=False),
        Binding("l", "next_patch", show=False),
        Binding("q", "back_to_list", show=False),
        Binding("comma", "back_to_list", show=False),
        Binding("escape", "quit", show=False),
    ]

    def __init__(
        self,
        patch: Patch,
        all_patches: list[Patch],
        current_index: int,
    ) -> None:
        super().__init__()
        self.patch = patch
        self.all_patches = all_patches
        self.current_patch_index = current_index
        self.player: Optional[AudioPlayer] = None
        self.track_widgets: dict[int, TrackWidget] = {}
        self.progress_bar: Optional[ProgressBarWidget] = None

    def compose(self) -> ComposeResult:
        # Header (single line)
        patch_name = (
            self.patch.analysis.suggested_name if self.patch.analysis else f"Patch #{self.patch.catalog_number}"
        )
        bpm_str = f" {self.patch.tracks[0].bpm:.0f}bpm" if self.patch.tracks and self.patch.tracks[0].bpm else ""
        yield Static(
            f"[bold]LOOPCAT[/] │ {patch_name} (#{self.patch.catalog_number}){bpm_str}",
            id="header",
        )

        # Master progress bar
        self.progress_bar = ProgressBarWidget(id="progress-bar")
        yield self.progress_bar

        # Tracks
        with VerticalScroll(id="tracks-container"):
            for track in sorted(self.patch.tracks, key=lambda t: t.track_number):
                widget = TrackWidget(track, track.track_number, id=f"track-{track.track_number}")
                self.track_widgets[track.track_number] = widget
                yield widget

        yield ControlsFooter()

    def on_mount(self) -> None:
        """Initialize audio player when screen mounts."""
        self.player = AudioPlayer(on_position_update=self._on_position_update)

        # Load all tracks (prefer MP3 over WAV)
        for track in self.patch.tracks:
            audio_path = None
            if track.mp3_path:
                mp3_path = Path(track.mp3_path)
                if mp3_path.exists():
                    audio_path = mp3_path
            if audio_path is None:
                wav_path = Path(track.wav_path)
                if wav_path.exists():
                    audio_path = wav_path
            if audio_path:
                self.player.load_track(track.track_number, audio_path)

        # Set initial progress bar state (use longest track duration)
        max_duration = (
            max((self.player.get_track_info(t.track_number) or (0, 0, False))[1] for t in self.patch.tracks) or 1.0
        )
        if self.progress_bar:
            self.progress_bar.update_state(0.0, max_duration, True)

        # Start audio stream and autoplay all tracks
        self.player.start()
        self.player.play_all()

        # Update widgets to show playing state
        for track_num, widget in self.track_widgets.items():
            widget.update_state(True)

    def on_unmount(self) -> None:
        """Clean up audio player when screen unmounts."""
        if self.player:
            self.player.stop()

    def _on_position_update(self, positions: dict[int, tuple[float, float, bool]]) -> None:
        """Handle position updates from audio player."""
        self.app.call_from_thread(self._update_track_displays, positions)

    def _update_track_displays(self, positions: dict[int, tuple[float, float, bool]]) -> None:
        """Update track widgets and progress bar with new positions."""
        any_playing = False
        max_duration = 0.0
        current_position = 0.0

        for track_num, (position, duration, playing) in positions.items():
            if track_num in self.track_widgets:
                self.track_widgets[track_num].update_state(playing)

            if playing:
                any_playing = True
                # Use the longest playing track for the progress bar
                if duration > max_duration:
                    max_duration = duration
                    current_position = position

        # Update master progress bar
        if self.progress_bar:
            if not any_playing:
                # When stopped, show the longest track's duration
                max_duration = max((dur for _, dur, _ in positions.values()), default=1.0)
                current_position = 0.0
            self.progress_bar.update_state(current_position, max_duration, any_playing)

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

    def action_cycle_theme(self) -> None:
        """Open theme picker."""
        self.app.push_screen(ThemePickerScreen(self.app.theme), self._on_theme_selected)

    def _on_theme_selected(self, theme: str | None) -> None:
        """Handle theme selection from picker."""
        if theme:
            self.app.theme = theme
            set_theme(theme)
            self.app.notify(f"Theme: {theme}")

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
        new_patch = self.all_patches[new_index]

        # Pop this screen and push new player screen
        self.app.pop_screen()
        self.app.push_screen(PlayerScreen(new_patch, self.all_patches, new_index))

    def action_back_to_list(self) -> None:
        """Go back to patch selector."""
        if self.player:
            self.player.stop()
        # Pop back to picker, updating selected index
        self.app.pop_screen()
        # Update picker's selected index
        picker = self.app.screen
        if isinstance(picker, PatchPickerScreen):
            picker.selected_index = self.current_patch_index
            option_list = picker.query_one("#patch-list", OptionList)
            if option_list.option_count > self.current_patch_index:
                option_list.highlighted = self.current_patch_index

    def action_quit(self) -> None:
        """Quit the application."""
        if self.player:
            self.player.stop()
        self.app.exit()


class LoopCatApp(App):
    """Main TUI application for loopcat."""

    CSS = """
    Screen {
        background: $surface;
    }
    """

    def __init__(self, patches: list[Patch], initial_patch: Optional[Patch] = None) -> None:
        super().__init__()
        # Register base16 themes
        for theme in BASE16_THEMES:
            self.register_theme(theme)
        self.theme = get_theme()
        self.patches = patches
        self.initial_patch = initial_patch

    def on_mount(self) -> None:
        """Set up initial screen."""
        if self.initial_patch:
            # Start directly in player mode
            idx = next((i for i, p in enumerate(self.patches) if p.id == self.initial_patch.id), 0)
            self.push_screen(PatchPickerScreen(self.patches, idx))
            self.push_screen(PlayerScreen(self.initial_patch, self.patches, idx))
        else:
            # Start with patch picker
            self.push_screen(PatchPickerScreen(self.patches))


def run_app(patches: list[Patch], initial_patch: Optional[Patch] = None) -> None:
    """Run the loopcat TUI application.

    Args:
        patches: All patches in the catalog.
        initial_patch: Optional patch to start playing immediately.
    """
    app = LoopCatApp(patches, initial_patch)
    app.run()


# Legacy function for backwards compatibility
def run_player(patch: Patch, all_patches: Optional[list[Patch]] = None) -> Optional[str]:
    """Run the TUI player for a patch (legacy interface).

    Args:
        patch: The patch to play.
        all_patches: All patches for prev/next navigation.

    Returns:
        None (legacy return value no longer used).
    """
    patches = all_patches or [patch]
    run_app(patches, patch)
    return None
