"""TUI interface for gridcat - a MIDI grid controller."""

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

from gridcat.midi import MidiEngine, DEFAULT_PORT_NAME


# Key-to-note mapping: 4 rows of 8 keys each
# Row 0: 1-8, Row 1: Q-I, Row 2: A-K, Row 3: Z-,
KEY_ROWS = [
    ["1", "2", "3", "4", "5", "6", "7", "8"],
    ["q", "w", "e", "r", "t", "y", "u", "i"],
    ["a", "s", "d", "f", "g", "h", "j", "k"],
    ["z", "x", "c", "v", "b", "n", "m", "comma"],
]

# Display labels for keys (what to show on the pads)
KEY_LABELS = [
    ["1", "2", "3", "4", "5", "6", "7", "8"],
    ["Q", "W", "E", "R", "T", "Y", "U", "I"],
    ["A", "S", "D", "F", "G", "H", "J", "K"],
    ["Z", "X", "C", "V", "B", "N", "M", ","],
]

# Note names for display
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_to_name(note: int) -> str:
    """Convert MIDI note number to note name.

    Args:
        note: MIDI note number (0-127).

    Returns:
        Note name like "C4" or "F#3".
    """
    octave = (note // 12) - 1
    name = NOTE_NAMES[note % 12]
    return f"{name}{octave}"


class PadConfig:
    """Configuration for a single pad."""

    def __init__(
        self,
        msg_type: str = "note",  # "note", "cc", "pc"
        note: int = 60,
        cc_number: int = 1,
        cc_value: int = 127,
        pc_number: int = 0,
        velocity: int = 100,
        label: str = "",
    ) -> None:
        self.msg_type = msg_type
        self.note = note
        self.cc_number = cc_number
        self.cc_value = cc_value
        self.pc_number = pc_number
        self.velocity = velocity
        self.label = label  # Custom label (empty = auto)


class PadWidget(Static):
    """A single pad in the grid."""

    DEFAULT_CSS = """
    PadWidget {
        width: 7;
        height: 3;
        content-align: center middle;
        text-align: center;
        border: solid $primary-darken-2;
        margin: 0 1 0 0;
    }

    PadWidget.pressed {
        background: $primary;
        border: solid $primary-lighten-2;
    }

    PadWidget.selected {
        border: solid $warning;
    }

    PadWidget.selected.pressed {
        border: solid $warning-lighten-2;
    }
    """

    pressed: reactive[bool] = reactive(False)
    selected: reactive[bool] = reactive(False)

    def __init__(
        self, key_label: str, config: PadConfig, row: int, col: int, **kwargs
    ) -> None:
        """Initialize the pad widget.

        Args:
            key_label: The key label to display (e.g., "Q").
            config: Pad configuration (note, CC, etc.).
            row: Row index in the grid.
            col: Column index in the grid.
        """
        super().__init__(**kwargs)
        self.key_label = key_label
        self.config = config
        self.row = row
        self.col = col

    def compose(self) -> ComposeResult:
        yield Label("")  # Placeholder, we render in render()

    def render(self) -> str:
        """Render the pad content."""
        cfg = self.config

        # Use custom label or generate from config
        if cfg.label:
            display = cfg.label
        elif cfg.msg_type == "note":
            display = note_to_name(cfg.note)
        elif cfg.msg_type == "cc":
            display = f"CC{cfg.cc_number}"
        elif cfg.msg_type == "pc":
            display = f"PC{cfg.pc_number}"
        else:
            display = "?"

        return f"[bold]{self.key_label}[/]\n{display}"

    def watch_pressed(self, pressed: bool) -> None:
        """React to pressed state changes."""
        if pressed:
            self.add_class("pressed")
        else:
            self.remove_class("pressed")

    def watch_selected(self, selected: bool) -> None:
        """React to selection state changes."""
        if selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")


class GridContainer(Container):
    """Container for the 4x8 grid of pads."""

    DEFAULT_CSS = """
    GridContainer {
        height: auto;
        width: auto;
        padding: 1;
    }
    """


class PadRow(Horizontal):
    """A row of pads."""

    DEFAULT_CSS = """
    PadRow {
        height: auto;
        width: auto;
        margin-bottom: 1;
    }
    """


class StatusBar(Static):
    """Status bar showing octave, channel, and output."""

    DEFAULT_CSS = """
    StatusBar {
        dock: top;
        height: 1;
        background: $primary;
        padding: 0 1;
    }
    """


class ControlsFooter(ControlsFooterBase):
    """Custom footer with gridcat controls."""

    def __init__(self) -> None:
        content = (
            "[dim]↑↓[/] octave  "
            "[dim]Shift[/] soft  "
            "[dim]Ctrl+hjkl[/] select  "
            "[dim]:[/] commands  "
            "[dim]?[/] help"
        )
        super().__init__(content)


class HelpScreen(HelpScreenBase):
    """Help screen for gridcat."""

    TITLE = "Gridcat Help"
    HELP_TEXT = """[bold]Grid Controls[/]
[dim]1-8, Q-I, A-K, Z-,[/]  Trigger pads

[bold]Modifiers[/]
[dim]Shift + key[/]         Soft velocity (40)

[bold]Pad Selection[/]
[dim]Ctrl + h/j/k/l[/]      Navigate grid (vim-style)
[dim]Ctrl + Enter[/]        Edit selected pad
[dim]Esc[/]                 Deselect pad

[bold]Navigation[/]
[dim]↑ / ][/]               Octave up
[dim]↓ / [[/]               Octave down

[bold]Commands[/]
[dim]:[/]                   Open command palette
[dim]?[/]                   Show this help"""


# Command palette commands
COMMANDS = [
    ("edit", "Edit selected pad"),
    ("output", "Select MIDI output"),
    ("channel", "Select MIDI channel (1-16)"),
    ("theme", "Change color theme"),
    ("help", "Show keyboard shortcuts"),
    ("quit", "Exit gridcat"),
]


class CommandPalette(ModalScreen[str | None]):
    """Command palette for gridcat settings."""

    CSS = """
    CommandPalette {
        align: center middle;
    }

    #palette-dialog {
        width: 50;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    #palette-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #palette-input {
        margin-bottom: 1;
    }

    #palette-list {
        height: 8;
        margin-bottom: 1;
    }

    #palette-hint {
        text-align: center;
        color: $text-muted;
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
        Binding("ctrl+p", "cursor_up", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.filter_text = ""

    def compose(self) -> ComposeResult:
        from textual.widgets import Input

        with Container(id="palette-dialog"):
            yield Static("Commands", id="palette-title")
            yield Input(placeholder="Type to filter...", id="palette-input")
            yield OptionList(
                *[Option(f"{cmd}  [dim]{desc}[/]", id=cmd) for cmd, desc in COMMANDS],
                id="palette-list",
            )
            yield Static("[dim]↑↓[/] navigate  [dim]enter[/] run  [dim]esc[/] cancel", id="palette-hint")

    def on_mount(self) -> None:
        self.query_one("#palette-input").focus()
        option_list = self.query_one("#palette-list", OptionList)
        option_list.highlighted = 0

    def on_input_changed(self, event) -> None:
        """Filter commands as user types."""
        from textual.widgets import Input

        self.filter_text = event.value.lower()
        option_list = self.query_one("#palette-list", OptionList)
        option_list.clear_options()

        filtered = [(cmd, desc) for cmd, desc in COMMANDS if self.filter_text in cmd.lower()]
        option_list.add_options([Option(f"{cmd}  [dim]{desc}[/]", id=cmd) for cmd, desc in filtered])

        if filtered:
            option_list.highlighted = 0

    def _move_highlight(self, delta: int) -> None:
        """Move the option list highlight by delta."""
        option_list = self.query_one("#palette-list", OptionList)
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

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_select(self) -> None:
        option_list = self.query_one("#palette-list", OptionList)
        if option_list.highlighted is not None and option_list.option_count > 0:
            option = option_list.get_option_at_index(option_list.highlighted)
            if option:
                self.dismiss(option.id)
                return
        self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option:
            self.dismiss(event.option.id)


class OutputPickerScreen(ModalScreen[tuple[str, bool] | None]):
    """Modal for selecting MIDI output (virtual or existing)."""

    CSS = """
    OutputPickerScreen {
        align: center middle;
    }

    #output-dialog {
        width: 55;
        height: auto;
        max-height: 80%;
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

    .section-header {
        margin-top: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select", "Select", priority=True),
    ]

    def __init__(
        self,
        outputs: list[str],
        current: Optional[str] = None,
        is_virtual: bool = False,
    ) -> None:
        super().__init__()
        self.outputs = outputs
        self.current = current
        self.is_virtual = is_virtual

    def compose(self) -> ComposeResult:
        # Build option list with virtual port first, then existing outputs
        options = []

        # Virtual port option (always first)
        virtual_label = f"Virtual: {DEFAULT_PORT_NAME}"
        options.append(Option(virtual_label, id="__virtual__"))

        # Existing outputs
        for output in self.outputs:
            options.append(Option(output, id=output))

        with Vertical(id="output-dialog"):
            yield Static("[bold]Select MIDI Output[/]", id="output-title")
            yield OptionList(*options, id="output-list")
            yield Static("[dim]enter[/] select  [dim]esc[/] cancel", id="output-hint")

    def on_mount(self) -> None:
        option_list = self.query_one("#output-list", OptionList)
        option_list.focus()

        # Highlight current selection
        if self.is_virtual:
            option_list.highlighted = 0  # Virtual is first
        elif self.current and self.current in self.outputs:
            try:
                idx = self.outputs.index(self.current) + 1  # +1 for virtual option
                option_list.highlighted = idx
            except ValueError:
                option_list.highlighted = 0
        else:
            option_list.highlighted = 0  # Default to virtual

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_select(self) -> None:
        option_list = self.query_one("#output-list", OptionList)
        if option_list.highlighted is not None:
            option = option_list.get_option_at_index(option_list.highlighted)
            if option:
                if option.id == "__virtual__":
                    self.dismiss((DEFAULT_PORT_NAME, True))
                else:
                    self.dismiss((option.id, False))
                return
        self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option:
            if event.option.id == "__virtual__":
                self.dismiss((DEFAULT_PORT_NAME, True))
            else:
                self.dismiss((event.option.id, False))


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


class PadEditorScreen(ModalScreen[PadConfig | None]):
    """Modal for editing pad configuration."""

    CSS = """
    PadEditorScreen {
        align: center middle;
    }

    #editor-dialog {
        width: 45;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    #editor-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    .editor-row {
        height: 3;
        margin-bottom: 1;
    }

    .editor-row Label {
        width: 12;
        padding-top: 1;
    }

    .editor-row Input {
        width: 1fr;
    }

    .editor-row OptionList {
        width: 1fr;
        height: 3;
    }

    #editor-hint {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "save", "Save", priority=True),
    ]

    def __init__(self, pad: PadWidget) -> None:
        super().__init__()
        self.pad = pad
        self.config = pad.config

    def compose(self) -> ComposeResult:
        from textual.widgets import Input, Select

        with Container(id="editor-dialog"):
            yield Static(f"Edit Pad [{self.pad.key_label}]", id="editor-title")

            # Message type selector
            with Horizontal(classes="editor-row"):
                yield Label("Type:")
                yield Select(
                    [("Note", "note"), ("CC", "cc"), ("Program", "pc")],
                    value=self.config.msg_type,
                    id="msg-type",
                )

            # Note settings
            with Horizontal(classes="editor-row", id="note-row"):
                yield Label("Note:")
                yield Input(str(self.config.note), id="note-input", type="integer")

            # Velocity
            with Horizontal(classes="editor-row", id="velocity-row"):
                yield Label("Velocity:")
                yield Input(str(self.config.velocity), id="velocity-input", type="integer")

            # CC settings
            with Horizontal(classes="editor-row", id="cc-num-row"):
                yield Label("CC Number:")
                yield Input(str(self.config.cc_number), id="cc-num-input", type="integer")

            with Horizontal(classes="editor-row", id="cc-val-row"):
                yield Label("CC Value:")
                yield Input(str(self.config.cc_value), id="cc-val-input", type="integer")

            # PC settings
            with Horizontal(classes="editor-row", id="pc-row"):
                yield Label("Program:")
                yield Input(str(self.config.pc_number), id="pc-input", type="integer")

            # Custom label
            with Horizontal(classes="editor-row"):
                yield Label("Label:")
                yield Input(self.config.label, id="label-input", placeholder="(auto)")

            yield Static("[dim]enter[/] save  [dim]esc[/] cancel", id="editor-hint")

    def on_mount(self) -> None:
        self._update_visibility()
        self.query_one("#msg-type").focus()

    def on_select_changed(self, event) -> None:
        """Update field visibility when type changes."""
        if event.select.id == "msg-type":
            self._update_visibility()

    def _update_visibility(self) -> None:
        """Show/hide fields based on message type."""
        try:
            msg_type = self.query_one("#msg-type", Select).value

            # Note fields
            self.query_one("#note-row").display = (msg_type == "note")
            self.query_one("#velocity-row").display = (msg_type == "note")

            # CC fields
            self.query_one("#cc-num-row").display = (msg_type == "cc")
            self.query_one("#cc-val-row").display = (msg_type == "cc")

            # PC fields
            self.query_one("#pc-row").display = (msg_type == "pc")
        except Exception:
            pass

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        """Save the configuration."""
        from textual.widgets import Input, Select

        try:
            msg_type = self.query_one("#msg-type", Select).value

            new_config = PadConfig(
                msg_type=msg_type,
                note=int(self.query_one("#note-input", Input).value or "60"),
                velocity=int(self.query_one("#velocity-input", Input).value or "100"),
                cc_number=int(self.query_one("#cc-num-input", Input).value or "1"),
                cc_value=int(self.query_one("#cc-val-input", Input).value or "127"),
                pc_number=int(self.query_one("#pc-input", Input).value or "0"),
                label=self.query_one("#label-input", Input).value,
            )

            # Clamp values
            new_config.note = max(0, min(127, new_config.note))
            new_config.velocity = max(0, min(127, new_config.velocity))
            new_config.cc_number = max(0, min(127, new_config.cc_number))
            new_config.cc_value = max(0, min(127, new_config.cc_value))
            new_config.pc_number = max(0, min(127, new_config.pc_number))

            self.dismiss(new_config)
        except ValueError:
            # Invalid input, stay on screen
            pass


class GridScreen(Screen):
    """Main grid screen."""

    BINDINGS = [
        Binding("up", "octave_up", "Octave Up"),
        Binding("down", "octave_down", "Octave Down"),
        Binding("bracketright", "octave_up", "Octave Up", show=False),
        Binding("bracketleft", "octave_down", "Octave Down", show=False),
        Binding("colon", "command_palette", "Commands"),
        Binding("question_mark", "show_help", "Help"),
        Binding("escape", "deselect_or_quit", "Quit"),
        # Ctrl+H sends backspace in most terminals, so bind both
        Binding("ctrl+h", "select_left", "Select Left", show=False),
        Binding("backspace", "select_left", "Select Left", show=False),
        Binding("ctrl+j", "select_down", "Select Down", show=False),
        Binding("ctrl+k", "select_up", "Select Up", show=False),
        Binding("ctrl+l", "select_right", "Select Right", show=False),
        Binding("ctrl+enter", "edit_pad", "Edit Pad", show=False),
    ]

    octave: reactive[int] = reactive(3)
    midi_output: reactive[str] = reactive("")
    midi_channel: reactive[int] = reactive(0)
    is_virtual_port: reactive[bool] = reactive(False)
    selected_row: reactive[int] = reactive(-1)  # -1 = no selection
    selected_col: reactive[int] = reactive(-1)

    def __init__(self, midi_engine: MidiEngine) -> None:
        super().__init__()
        self.midi = midi_engine
        self._pads: dict[str, PadWidget] = {}
        self._pad_grid: list[list[PadWidget]] = []  # 2D grid for navigation

    def compose(self) -> ComposeResult:
        yield StatusBar(self._make_status())
        with GridContainer():
            for row_idx, row in enumerate(KEY_ROWS):
                pad_row = []
                with PadRow():
                    for col_idx, key in enumerate(row):
                        note = self._key_to_note(row_idx, col_idx)
                        label = KEY_LABELS[row_idx][col_idx]
                        config = PadConfig(note=note)
                        pad = PadWidget(label, config, row_idx, col_idx, id=f"pad-{key}")
                        self._pads[key] = pad
                        pad_row.append(pad)
                        yield pad
                self._pad_grid.append(pad_row)
        yield ControlsFooter()

    def _make_status(self) -> str:
        """Generate status bar content."""
        if self.midi_output:
            if self.is_virtual_port:
                output = f"[bold]{self.midi_output}[/] (virtual)"
            else:
                output = self.midi_output
        else:
            output = "[dim]None[/]"

        # Show selected pad info
        if self.selected_row >= 0 and self.selected_col >= 0:
            pad = self._pad_grid[self.selected_row][self.selected_col]
            cfg = pad.config
            if cfg.msg_type == "note":
                sel = f"[{pad.key_label}] {note_to_name(cfg.note)}"
            elif cfg.msg_type == "cc":
                sel = f"[{pad.key_label}] CC{cfg.cc_number}={cfg.cc_value}"
            else:
                sel = f"[{pad.key_label}] PC{cfg.pc_number}"
        else:
            sel = "[dim]None[/]"

        return (
            f"[bold]GRIDCAT[/]  │  "
            f"Oct: {self.octave}  │  "
            f"Ch: {self.midi_channel + 1}  │  "
            f"Sel: {sel}  │  "
            f"Out: {output}"
        )

    def _update_status(self) -> None:
        """Update the status bar."""
        try:
            status = self.query_one(StatusBar)
            status.update(self._make_status())
        except Exception:
            pass

    def _key_to_note(self, row: int, col: int) -> int:
        """Convert grid position to MIDI note.

        Args:
            row: Row index (0-3).
            col: Column index (0-7).

        Returns:
            MIDI note number.
        """
        # Base note is C of current octave
        # Row 0 starts at C, row 1 at G#, row 2 at E, row 3 at C+1octave
        base = (self.octave + 1) * 12  # C of octave
        note_offset = row * 8 + col
        return base + note_offset

    def _update_pad_notes(self) -> None:
        """Update all pad note values after octave change."""
        for row_idx, row in enumerate(KEY_ROWS):
            for col_idx, key in enumerate(row):
                if key in self._pads:
                    pad = self._pads[key]
                    if pad.config.msg_type == "note":
                        pad.config.note = self._key_to_note(row_idx, col_idx)
                    pad.refresh()

    def _update_selection(self) -> None:
        """Update pad selection visual state."""
        for row_idx, row in enumerate(self._pad_grid):
            for col_idx, pad in enumerate(row):
                pad.selected = (row_idx == self.selected_row and col_idx == self.selected_col)

    def watch_octave(self, octave: int) -> None:
        """React to octave changes."""
        self._update_pad_notes()
        self._update_status()

    def watch_midi_output(self, output: str) -> None:
        """React to MIDI output changes."""
        self._update_status()

    def watch_midi_channel(self, channel: int) -> None:
        """React to MIDI channel changes."""
        self._update_status()

    def watch_is_virtual_port(self, is_virtual: bool) -> None:
        """React to virtual port state changes."""
        self._update_status()

    def watch_selected_row(self, row: int) -> None:
        """React to selection row changes."""
        self._update_selection()
        self._update_status()

    def watch_selected_col(self, col: int) -> None:
        """React to selection column changes."""
        self._update_selection()
        self._update_status()

    def on_key(self, event) -> None:
        """Handle key press for grid pads (trigger mode)."""
        key = event.key

        # Check for modifier keys in key string
        has_shift = key.startswith("shift+")
        has_ctrl = key.startswith("ctrl+")

        # Ctrl+key is reserved for navigation, don't trigger pads
        if has_ctrl:
            return

        # Extract base key
        base_key = key
        if has_shift:
            base_key = key[6:]  # Remove "shift+"

        # Normalize comma key
        if base_key == ",":
            base_key = "comma"

        # Check if this is a grid key
        grid_key = None
        for row in KEY_ROWS:
            if base_key in row:
                grid_key = base_key
                break

        if grid_key is None:
            return

        # Determine velocity based on modifiers
        if has_shift:
            velocity = 40  # Soft
        else:
            velocity = 100  # Normal

        # Trigger the pad
        if grid_key in self._pads:
            pad = self._pads[grid_key]
            self._trigger_pad(pad, velocity)

    def _trigger_pad(self, pad: PadWidget, velocity: int = 100) -> None:
        """Trigger a pad based on its configuration."""
        cfg = pad.config
        pad.pressed = True

        if cfg.msg_type == "note":
            self.midi.note_on(cfg.note, velocity if cfg.velocity == 100 else cfg.velocity)
            self.set_timer(0.1, lambda p=pad: self._note_off(p))
        elif cfg.msg_type == "cc":
            self.midi.cc(cfg.cc_number, cfg.cc_value)
            self.set_timer(0.1, lambda p=pad: self._pad_off(p))
        elif cfg.msg_type == "pc":
            self.midi.pc(cfg.pc_number)
            self.set_timer(0.1, lambda p=pad: self._pad_off(p))

    def _note_off(self, pad: PadWidget) -> None:
        """Send note off and update pad state."""
        pad.pressed = False
        self.midi.note_off(pad.config.note)

    def _pad_off(self, pad: PadWidget) -> None:
        """Update pad visual state (for CC/PC which don't need note off)."""
        pad.pressed = False

    def action_octave_up(self) -> None:
        """Increase octave."""
        if self.octave < 8:
            self.octave += 1

    def action_octave_down(self) -> None:
        """Decrease octave."""
        if self.octave > -1:
            self.octave -= 1

    def action_select_left(self) -> None:
        """Move selection left (wraps around)."""
        if self.selected_row < 0:
            # No selection, start at top-left
            self.selected_row = 0
            self.selected_col = 0
        else:
            self.selected_col = (self.selected_col - 1) % 8

    def action_select_right(self) -> None:
        """Move selection right (wraps around)."""
        if self.selected_row < 0:
            self.selected_row = 0
            self.selected_col = 0
        else:
            self.selected_col = (self.selected_col + 1) % 8

    def action_select_up(self) -> None:
        """Move selection up (wraps around)."""
        if self.selected_row < 0:
            self.selected_row = 0
            self.selected_col = 0
        else:
            self.selected_row = (self.selected_row - 1) % 4

    def action_select_down(self) -> None:
        """Move selection down (wraps around)."""
        if self.selected_row < 0:
            self.selected_row = 0
            self.selected_col = 0
        else:
            self.selected_row = (self.selected_row + 1) % 4

    def action_deselect_or_quit(self) -> None:
        """Deselect pad if selected, otherwise quit."""
        if self.selected_row >= 0:
            self.selected_row = -1
            self.selected_col = -1
        else:
            self.action_quit()

    def action_edit_pad(self) -> None:
        """Edit the selected pad."""
        if self.selected_row >= 0 and self.selected_col >= 0:
            pad = self._pad_grid[self.selected_row][self.selected_col]
            self._open_pad_editor(pad)

    def _open_pad_editor(self, pad: PadWidget) -> None:
        """Open the pad editor dialog."""
        def handle_config(new_config: PadConfig | None) -> None:
            if new_config:
                pad.config = new_config
                pad.refresh()
                self._update_status()

        self.app.push_screen(PadEditorScreen(pad), handle_config)

    def action_select_output(self) -> None:
        """Open output selection dialog."""
        outputs = self.midi.list_outputs()

        def handle_output(result: tuple[str, bool] | None) -> None:
            if result:
                port_name, is_virtual = result
                if is_virtual:
                    if self.midi.open_virtual(port_name):
                        self.midi_output = port_name
                        self.is_virtual_port = True
                else:
                    if self.midi.connect(port_name):
                        self.midi_output = port_name
                        self.is_virtual_port = False

        self.app.push_screen(
            OutputPickerScreen(
                outputs,
                self.midi_output or None,
                self.is_virtual_port,
            ),
            handle_output,
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
        config_path = get_config_path("gridcat")

        def handle_theme(theme: str | None) -> None:
            if theme:
                self.app.theme = theme
                set_theme(theme, config_path)

        self.app.push_screen(ThemePickerScreen(self.app.theme), handle_theme)

    def action_command_palette(self) -> None:
        """Open command palette."""

        def handle_command(command: str | None) -> None:
            if command == "edit":
                self.action_edit_pad()
            elif command == "output":
                self.action_select_output()
            elif command == "channel":
                self.action_select_channel()
            elif command == "theme":
                self.action_select_theme()
            elif command == "help":
                self.action_show_help()
            elif command == "quit":
                self.action_quit()

        self.app.push_screen(CommandPalette(), handle_command)

    def action_show_help(self) -> None:
        """Show help screen."""
        self.app.push_screen(HelpScreen())

    def action_quit(self) -> None:
        """Quit the app."""
        self.midi.all_notes_off()
        self.app.exit()


class GridcatApp(App):
    """Gridcat TUI MIDI controller application."""

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
        """Load theme and push grid screen on mount."""
        config_path = get_config_path("gridcat")
        theme = get_theme(config_path)
        self.theme = theme

        # Push the grid screen
        grid_screen = GridScreen(self.midi)
        self.push_screen(grid_screen)

        # Open virtual port after screen is ready
        self.call_after_refresh(self._open_virtual_port)

    def _open_virtual_port(self) -> None:
        """Open virtual MIDI port on startup."""
        if self.midi.open_virtual(DEFAULT_PORT_NAME):
            try:
                grid_screen = self.query_one(GridScreen)
                grid_screen.midi_output = DEFAULT_PORT_NAME
                grid_screen.is_virtual_port = True
            except Exception:
                pass

    def action_quit(self) -> None:
        """Quit cleanly."""
        self.midi.all_notes_off()
        self.midi.disconnect()
        self.exit()


def main() -> None:
    """Run the gridcat app."""
    app = GridcatApp()
    app.run()


if __name__ == "__main__":
    main()
