"""TUI interface for fadercat - a MIDI fader controller."""

from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widgets import Static, OptionList, Label
from textual.widgets.option_list import Option

from cat_common import (
    ControlsFooter as ControlsFooterBase,
    HelpScreenBase,
    ThemePickerScreen,
    get_config_path,
    get_theme,
    register_themes,
    set_theme,
)

from fadercat.midi import MidiEngine


# Fader configuration: 8 faders with dual-key control
# Top row keys increase, bottom row keys decrease
FADER_KEYS_UP = ["q", "w", "e", "r", "t", "y", "u", "i"]
FADER_KEYS_DOWN = ["a", "s", "d", "f", "g", "h", "j", "k"]
FADER_LABELS_UP = ["Q", "W", "E", "R", "T", "Y", "U", "I"]
FADER_LABELS_DOWN = ["A", "S", "D", "F", "G", "H", "J", "K"]

# Default CC numbers for each fader
DEFAULT_CC_NUMBERS = [1, 2, 3, 4, 5, 6, 7, 8]

# Default fader labels
DEFAULT_FADER_LABELS = [
    "Mod", "Breath", "CC3", "Foot", "Port", "Data", "Volume", "Balance"
]

# Step sizes
STEP_NORMAL = 4
STEP_FINE = 1
STEP_COARSE = 16


class FaderWidget(Static):
    """A single fader with visual bar and value display."""

    DEFAULT_CSS = """
    FaderWidget {
        width: 9;
        height: 100%;
        padding: 0 1;
    }

    FaderWidget .fader-label {
        text-align: center;
        height: 1;
    }

    FaderWidget .fader-cc {
        text-align: center;
        height: 1;
        color: $text-muted;
    }

    FaderWidget .fader-bar {
        height: 1fr;
        width: 100%;
        content-align: center bottom;
    }

    FaderWidget .fader-keys {
        text-align: center;
        height: 1;
        color: $text-muted;
    }

    FaderWidget .fader-value {
        text-align: center;
        height: 1;
    }

    FaderWidget.selected {
        background: $primary-darken-3;
    }
    """

    value: reactive[int] = reactive(0)
    selected: reactive[bool] = reactive(False)

    def __init__(
        self,
        fader_index: int,
        cc_number: int,
        label: str,
        key_up: str,
        key_down: str,
        **kwargs,
    ) -> None:
        """Initialize the fader widget.

        Args:
            fader_index: Index of this fader (0-7).
            cc_number: The CC number this fader controls.
            label: Display label for the fader.
            key_up: Key label for increasing value.
            key_down: Key label for decreasing value.
        """
        super().__init__(**kwargs)
        self.fader_index = fader_index
        self.cc_number = cc_number
        self.label = label
        self.key_up = key_up
        self.key_down = key_down

    def compose(self) -> ComposeResult:
        yield Static(f"[bold]{self.label}[/]", classes="fader-label")
        yield Static(f"CC{self.cc_number}", classes="fader-cc")
        yield Static("", classes="fader-bar", id=f"bar-{self.fader_index}")
        yield Static(f"[{self.key_up}]^ [{self.key_down}]v", classes="fader-keys")
        yield Static("0", classes="fader-value", id=f"value-{self.fader_index}")

    def on_mount(self) -> None:
        """Update display on mount."""
        self._update_display()

    def watch_value(self, value: int) -> None:
        """React to value changes."""
        self._update_display()

    def watch_selected(self, selected: bool) -> None:
        """React to selection changes."""
        if selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")

    def _update_display(self) -> None:
        """Update the bar and value display."""
        try:
            bar = self.query_one(f"#bar-{self.fader_index}", Static)
            value_display = self.query_one(f"#value-{self.fader_index}", Static)

            # Create visual bar
            bar_content = self._render_bar()
            bar.update(bar_content)

            # Update value
            value_display.update(str(self.value))
        except Exception:
            pass

    def _render_bar(self) -> str:
        """Render the fader bar visualization."""
        # Get available height (approximated)
        height = 8  # Fixed height for simplicity
        filled = int((self.value / 127) * height)
        empty = height - filled

        lines = []
        for _ in range(empty):
            lines.append("[dim]░░░░░[/]")
        for _ in range(filled):
            lines.append("[bold]▓▓▓▓▓[/]")

        return "\n".join(lines)


class FaderContainer(Horizontal):
    """Container for all faders."""

    DEFAULT_CSS = """
    FaderContainer {
        height: 1fr;
        width: 100%;
        padding: 1;
    }
    """


class StatusBar(Static):
    """Status bar showing page, channel, and output."""

    DEFAULT_CSS = """
    StatusBar {
        dock: top;
        height: 1;
        background: $primary;
        padding: 0 1;
    }
    """


class ControlsFooter(ControlsFooterBase):
    """Custom footer with fadercat controls."""

    def __init__(self) -> None:
        content = (
            "[dim]Q-I[/] up  "
            "[dim]A-K[/] down  "
            "[dim]Shift[/] fine  "
            "[dim]Ctrl[/] coarse  "
            "[dim]Space[/] reset  "
            "[dim]1-8[/] select  "
            "[dim]o[/] output  "
            "[dim]t[/] theme"
        )
        super().__init__(content)


class HelpScreen(HelpScreenBase):
    """Help screen for fadercat."""

    TITLE = "Fadercat Help"
    HELP_TEXT = """[bold]Fader Controls[/]
[dim]Q, W, E, R, T, Y, U, I[/]  Increase faders 1-8
[dim]A, S, D, F, G, H, J, K[/]  Decrease faders 1-8

[bold]Modifiers[/]
[dim]Shift + key[/]             Fine adjustment (+/- 1)
[dim]Ctrl + key[/]              Coarse adjustment (+/- 16)
[dim]No modifier[/]             Normal adjustment (+/- 4)

[bold]Selection[/]
[dim]1-8[/]                     Select fader for editing
[dim]Space[/]                   Reset selected fader to 0

[bold]Settings[/]
[dim]o[/]                       Select MIDI output
[dim]c[/]                       Select MIDI channel
[dim]t[/]                       Change theme

[bold]General[/]
[dim]?[/]                       Show this help
[dim]q[/]                       Quit (when fader not selected)"""


class OutputPickerScreen(ModalScreen[str | None]):
    """Modal for selecting MIDI output."""

    CSS = """
    OutputPickerScreen {
        align: center middle;
    }

    #output-dialog {
        width: 50;
        height: auto;
        max-height: 70%;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    #output-list {
        height: auto;
        max-height: 15;
    }

    #output-hint {
        dock: bottom;
        height: 1;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select", "Select", priority=True),
    ]

    def __init__(self, outputs: list[str], current: Optional[str] = None) -> None:
        super().__init__()
        self.outputs = outputs
        self.current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="output-dialog"):
            yield Static("[bold]Select MIDI Output[/]", id="output-title")
            if self.outputs:
                yield OptionList(
                    *[Option(o, id=o) for o in self.outputs], id="output-list"
                )
            else:
                yield Static("[dim]No MIDI outputs available[/]")
            yield Static("[dim]enter[/] select  [dim]esc[/] cancel", id="output-hint")

    def on_mount(self) -> None:
        if self.outputs:
            option_list = self.query_one("#output-list", OptionList)
            option_list.focus()
            if self.current and self.current in self.outputs:
                try:
                    idx = self.outputs.index(self.current)
                    option_list.highlighted = idx
                except ValueError:
                    pass

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_select(self) -> None:
        if not self.outputs:
            self.dismiss(None)
            return
        option_list = self.query_one("#output-list", OptionList)
        if option_list.highlighted is not None:
            option = option_list.get_option_at_index(option_list.highlighted)
            if option:
                self.dismiss(option.id)
                return
        self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option:
            self.dismiss(event.option.id)


class ChannelPickerScreen(ModalScreen[int | None]):
    """Modal for selecting MIDI channel."""

    CSS = """
    ChannelPickerScreen {
        align: center middle;
    }

    #channel-dialog {
        width: 30;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    #channel-list {
        height: 10;
    }

    #channel-hint {
        dock: bottom;
        height: 1;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select", "Select", priority=True),
    ]

    def __init__(self, current_channel: int) -> None:
        super().__init__()
        self.current_channel = current_channel

    def compose(self) -> ComposeResult:
        with Vertical(id="channel-dialog"):
            yield Static("[bold]Select MIDI Channel[/]", id="channel-title")
            yield OptionList(
                *[Option(f"Channel {i+1}", id=str(i)) for i in range(16)],
                id="channel-list",
            )
            yield Static("[dim]enter[/] select  [dim]esc[/] cancel", id="channel-hint")

    def on_mount(self) -> None:
        option_list = self.query_one("#channel-list", OptionList)
        option_list.focus()
        option_list.highlighted = self.current_channel

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_select(self) -> None:
        option_list = self.query_one("#channel-list", OptionList)
        if option_list.highlighted is not None:
            self.dismiss(option_list.highlighted)
        else:
            self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option:
            self.dismiss(int(event.option.id))


class FaderScreen(Screen):
    """Main fader screen."""

    BINDINGS = [
        Binding("o", "select_output", "Output"),
        Binding("c", "select_channel", "Channel"),
        Binding("t", "select_theme", "Theme"),
        Binding("question_mark", "show_help", "Help"),
        Binding("space", "reset_fader", "Reset"),
        Binding("escape", "deselect", "Deselect", show=False),
    ]

    midi_output: reactive[str] = reactive("")
    midi_channel: reactive[int] = reactive(0)
    selected_fader: reactive[int] = reactive(-1)

    def __init__(self, midi_engine: MidiEngine) -> None:
        super().__init__()
        self.midi = midi_engine
        self._faders: list[FaderWidget] = []
        self._held_keys: set[str] = set()

    def compose(self) -> ComposeResult:
        yield StatusBar(self._make_status())
        with FaderContainer():
            for i in range(8):
                fader = FaderWidget(
                    fader_index=i,
                    cc_number=DEFAULT_CC_NUMBERS[i],
                    label=DEFAULT_FADER_LABELS[i],
                    key_up=FADER_LABELS_UP[i],
                    key_down=FADER_LABELS_DOWN[i],
                    id=f"fader-{i}",
                )
                self._faders.append(fader)
                yield fader
        yield ControlsFooter()

    def _make_status(self) -> str:
        """Generate status bar content."""
        output = self.midi_output or "[dim]None[/]"
        selected = f"Fader {self.selected_fader + 1}" if self.selected_fader >= 0 else "[dim]None[/]"
        return (
            f"[bold]FADERCAT[/]  │  "
            f"Ch: {self.midi_channel + 1}  │  "
            f"Out: {output}  │  "
            f"Sel: {selected}"
        )

    def _update_status(self) -> None:
        """Update the status bar."""
        try:
            status = self.query_one(StatusBar)
            status.update(self._make_status())
        except Exception:
            pass

    def watch_midi_output(self, output: str) -> None:
        """React to MIDI output changes."""
        self._update_status()

    def watch_midi_channel(self, channel: int) -> None:
        """React to MIDI channel changes."""
        self._update_status()

    def watch_selected_fader(self, index: int) -> None:
        """React to fader selection changes."""
        for i, fader in enumerate(self._faders):
            fader.selected = (i == index)
        self._update_status()

    def _get_step(self, shift: bool, ctrl: bool) -> int:
        """Get step size based on modifiers."""
        if shift:
            return STEP_FINE
        elif ctrl:
            return STEP_COARSE
        else:
            return STEP_NORMAL

    def _adjust_fader(self, index: int, delta: int) -> None:
        """Adjust a fader's value and send CC."""
        if 0 <= index < len(self._faders):
            fader = self._faders[index]
            new_value = max(0, min(127, fader.value + delta))
            if new_value != fader.value:
                fader.value = new_value
                self.midi.cc(fader.cc_number, new_value)

    def on_key(self, event) -> None:
        """Handle key press for fader control."""
        key = event.key

        # Check for modifier keys in key string
        has_shift = key.startswith("shift+")
        has_ctrl = key.startswith("ctrl+")

        # Extract base key
        base_key = key
        if has_shift:
            base_key = key[6:]  # Remove "shift+"
        elif has_ctrl:
            base_key = key[5:]  # Remove "ctrl+"

        # Number keys 1-8 for fader selection
        if base_key in "12345678":
            self.selected_fader = int(base_key) - 1
            return

        # Check for fader up keys
        if base_key in FADER_KEYS_UP:
            index = FADER_KEYS_UP.index(base_key)
            step = self._get_step(has_shift, has_ctrl)
            self._adjust_fader(index, step)
            return

        # Check for fader down keys
        if base_key in FADER_KEYS_DOWN:
            index = FADER_KEYS_DOWN.index(base_key)
            step = self._get_step(has_shift, has_ctrl)
            self._adjust_fader(index, -step)
            return

    def action_select_output(self) -> None:
        """Open output selection dialog."""
        outputs = self.midi.list_outputs()

        def handle_output(output: str | None) -> None:
            if output:
                if self.midi.connect(output):
                    self.midi_output = output

        self.app.push_screen(
            OutputPickerScreen(outputs, self.midi_output or None), handle_output
        )

    def action_select_channel(self) -> None:
        """Open channel selection dialog."""

        def handle_channel(channel: int | None) -> None:
            if channel is not None:
                self.midi.set_channel(channel)
                self.midi_channel = channel

        self.app.push_screen(
            ChannelPickerScreen(self.midi_channel), handle_channel
        )

    def action_select_theme(self) -> None:
        """Open theme picker."""
        config_path = get_config_path("fadercat")

        def handle_theme(theme: str | None) -> None:
            if theme:
                self.app.theme = theme
                set_theme(theme, config_path)

        self.app.push_screen(ThemePickerScreen(self.app.theme), handle_theme)

    def action_show_help(self) -> None:
        """Show help screen."""
        self.app.push_screen(HelpScreen())

    def action_reset_fader(self) -> None:
        """Reset selected fader to 0."""
        if 0 <= self.selected_fader < len(self._faders):
            fader = self._faders[self.selected_fader]
            fader.value = 0
            self.midi.cc(fader.cc_number, 0)

    def action_deselect(self) -> None:
        """Deselect current fader."""
        self.selected_fader = -1


class FadercatApp(App):
    """Fadercat TUI MIDI controller application."""

    CSS = """
    Screen {
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.midi = MidiEngine()
        register_themes(self)

    def on_mount(self) -> None:
        """Load theme and push fader screen on mount."""
        config_path = get_config_path("fadercat")
        theme = get_theme(config_path)
        self.theme = theme

        # Push the fader screen
        fader_screen = FaderScreen(self.midi)
        self.push_screen(fader_screen)

        # Auto-connect to first available output after screen is ready
        self.call_after_refresh(self._auto_connect_midi)

    def _auto_connect_midi(self) -> None:
        """Auto-connect to first available MIDI output."""
        outputs = self.midi.list_outputs()
        if outputs:
            if self.midi.connect(outputs[0]):
                try:
                    fader_screen = self.query_one(FaderScreen)
                    fader_screen.midi_output = outputs[0]
                except Exception:
                    pass

    def action_quit(self) -> None:
        """Quit cleanly."""
        self.midi.disconnect()
        self.exit()


def main() -> None:
    """Run the fadercat app."""
    app = FadercatApp()
    app.run()


if __name__ == "__main__":
    main()
