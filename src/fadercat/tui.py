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
    load_config,
    save_config,
)

from fadercat.midi import MidiEngine, DEFAULT_PORT_NAME


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

# Display modes
MODE_VERTICAL = "vertical"
MODE_HORIZONTAL = "horizontal"


def get_display_mode(config_path) -> str:
    """Load display mode from config, default to vertical."""
    config = load_config(config_path)
    return config.get("display_mode", MODE_VERTICAL)


def set_display_mode(mode: str, config_path) -> None:
    """Save display mode to config."""
    config = load_config(config_path)
    config["display_mode"] = mode
    save_config(config, config_path)


class FaderWidget(Static):
    """A single fader with visual bar and value display."""

    DEFAULT_CSS = """
    FaderWidget {
        width: 5;
        height: 100%;
        padding: 0;
    }

    FaderWidget .fader-index {
        text-align: center;
        height: 1;
        color: $text-muted;
    }

    FaderWidget .fader-bar {
        height: 1fr;
        width: 100%;
        content-align: center bottom;
    }

    FaderWidget .fader-value {
        text-align: center;
        height: 1;
    }

    FaderWidget.selected {
        background: $primary-darken-3;
    }

    FaderWidget.selected .fader-index {
        color: $text;
        text-style: bold;
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
        self._bar_height = 10  # Default, will be updated on resize

    def compose(self) -> ComposeResult:
        yield Static(f"{self.fader_index + 1}", classes="fader-index")
        yield Static("", classes="fader-bar", id=f"bar-{self.fader_index}")
        yield Static("0", classes="fader-value", id=f"value-{self.fader_index}")

    def on_mount(self) -> None:
        """Update display on mount."""
        self._update_display()

    def on_resize(self, event) -> None:
        """Handle resize to adjust bar height."""
        try:
            bar = self.query_one(f"#bar-{self.fader_index}", Static)
            # Get the bar's content height (available space for the bar)
            self._bar_height = max(1, bar.size.height)
            self._update_display()
        except Exception:
            pass

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

            # Update bar height from actual widget size
            if bar.size.height > 0:
                self._bar_height = bar.size.height

            # Create visual bar
            bar_content = self._render_bar()
            bar.update(bar_content)

            # Update value
            value_display.update(str(self.value))
        except Exception:
            pass

    def _render_bar(self) -> str:
        """Render the fader bar visualization filling available height."""
        height = self._bar_height
        # Calculate filled rows (fine-grained: each row represents ~1 MIDI value)
        filled = int((self.value / 127) * height)
        empty = height - filled

        lines = []
        for _ in range(empty):
            lines.append("[dim]░░░[/]")
        for _ in range(filled):
            lines.append("[bold]█▓█[/]")

        return "\n".join(lines)


class HorizontalFaderWidget(Static):
    """A horizontal fader row with CC#, value, bar, and label."""

    DEFAULT_CSS = """
    HorizontalFaderWidget {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    HorizontalFaderWidget.selected {
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
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.fader_index = fader_index
        self.cc_number = cc_number
        self.label = label
        self._bar_width = 30  # Default, updated on resize

    def on_mount(self) -> None:
        self._update_display()

    def on_resize(self, event) -> None:
        # Calculate available width for bar (total - CC# - value - label - padding)
        # Format: "CC##  val ████░░░░ Label   "
        # Fixed parts: CC label (4) + spaces (2) + value (3) + space (1) + label (8) + space (1) = 19
        available = self.size.width - 19
        self._bar_width = max(10, available)
        self._update_display()

    def watch_value(self, value: int) -> None:
        self._update_display()

    def watch_selected(self, selected: bool) -> None:
        if selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")
        self._update_display()

    def _update_display(self) -> None:
        content = self._render_row()
        self.update(content)

    def _render_row(self) -> str:
        # Format: CC##  val ████░░░░ Label
        cc_str = f"CC{self.cc_number:<2}"
        val_str = f"{self.value:>3}"
        label_str = f"{self.label[:8]:<8}"

        # Render horizontal bar
        bar = self._render_bar()

        if self.selected:
            return f"[bold]{cc_str}[/]  {val_str} {bar} [bold]{label_str}[/]"
        else:
            return f"[dim]{cc_str}[/]  {val_str} {bar} {label_str}"

    def _render_bar(self) -> str:
        width = self._bar_width
        filled = int((self.value / 127) * width)
        empty = width - filled

        filled_chars = "█" * filled
        empty_chars = "░" * empty

        return f"[bold]{filled_chars}[/][dim]{empty_chars}[/]"


class HorizontalFaderContainer(Vertical):
    """Container for horizontal fader layout."""

    DEFAULT_CSS = """
    HorizontalFaderContainer {
        height: 100%;
        width: 100%;
        padding: 1;
        content-align: center middle;
    }
    """


class FaderContainer(Horizontal):
    """Container for vertical faders."""

    DEFAULT_CSS = """
    FaderContainer {
        height: 100%;
        width: auto;
        padding: 1;
    }
    """


class SidePanel(Vertical):
    """Side panel showing selected fader details."""

    DEFAULT_CSS = """
    SidePanel {
        width: 24;
        height: 100%;
        border-left: solid $primary-darken-2;
        padding: 1;
    }

    SidePanel .panel-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }

    SidePanel .panel-row {
        height: 1;
    }

    SidePanel .panel-label {
        color: $text-muted;
    }

    SidePanel .panel-value {
        text-style: bold;
    }

    SidePanel .panel-bar {
        height: 1fr;
        content-align: center bottom;
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._bar_height = 10  # Default, will be updated

    def compose(self) -> ComposeResult:
        yield Static("Selected Fader", classes="panel-title")
        yield Static("[dim]None selected[/]", id="panel-content")
        yield Static("", classes="panel-bar", id="panel-bar")

    def on_resize(self, event) -> None:
        """Handle resize to update bar height."""
        try:
            bar = self.query_one("#panel-bar", Static)
            if bar.size.height > 0:
                self._bar_height = bar.size.height
        except Exception:
            pass

    def update_fader(self, fader: Optional["FaderWidget"]) -> None:
        """Update the panel with fader details."""
        try:
            content = self.query_one("#panel-content", Static)
            bar = self.query_one("#panel-bar", Static)

            # Update bar height from actual size
            if bar.size.height > 0:
                self._bar_height = bar.size.height

            if fader is None:
                content.update("[dim]None selected[/]\n\nUse [bold]1-8[/] or [bold]h/l[/]\nto select a fader")
                bar.update("")
            else:
                info = (
                    f"[bold]{fader.label}[/]\n\n"
                    f"[dim]Fader:[/]   {fader.fader_index + 1}\n"
                    f"[dim]CC:[/]      {fader.cc_number}\n"
                    f"[dim]Value:[/]   {fader.value}\n\n"
                    f"[dim]j/k[/] adjust\n"
                    f"[dim]Shift[/] fine  [dim]Ctrl[/] coarse\n"
                    f"[dim]Space[/] reset to 0"
                )
                content.update(info)

                # Render a visual bar filling available height
                bar_content = self._render_large_bar(fader.value)
                bar.update(bar_content)
        except Exception:
            pass

    def _render_large_bar(self, value: int) -> str:
        """Render a visual bar for the side panel filling available height."""
        height = self._bar_height
        filled = int((value / 127) * height)
        empty = height - filled

        lines = []
        for _ in range(empty):
            lines.append("[dim]░░░░░░░░░░░░░░░░░░[/]")
        for _ in range(filled):
            lines.append("[bold]█▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓█[/]")

        return "\n".join(lines)


class MainContent(Horizontal):
    """Main content area with faders and side panel."""

    DEFAULT_CSS = """
    MainContent {
        height: 1fr;
        width: 100%;
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

    def __init__(self, display_mode: str = MODE_VERTICAL) -> None:
        content = self._make_content(display_mode)
        super().__init__(content)

    def _make_content(self, display_mode: str) -> str:
        if display_mode == MODE_HORIZONTAL:
            return (
                "[dim]j/k[/] select  "
                "[dim]h/l[/] adjust  "
                "[dim]Shift[/] fine  "
                "[dim]Ctrl[/] coarse  "
                "[dim]Space[/] reset  "
                "[dim]v[/] vertical  "
                "[dim]?[/] help"
            )
        else:
            return (
                "[dim]h/l[/] select  "
                "[dim]j/k[/] adjust  "
                "[dim]Shift[/] fine  "
                "[dim]Ctrl[/] coarse  "
                "[dim]Space[/] reset  "
                "[dim]v[/] horizontal  "
                "[dim]?[/] help"
            )

    def set_mode(self, display_mode: str) -> None:
        """Update footer for new display mode."""
        self.update(self._make_content(display_mode))


class HelpScreen(HelpScreenBase):
    """Help screen for fadercat."""

    TITLE = "Fadercat Help"

    HELP_TEXT_VERTICAL = """[bold]Selection[/]
[dim]1-8[/]                     Select fader directly
[dim]h / l[/]                   Move selection left/right
[dim]Esc[/]                     Deselect

[bold]Adjustment[/]
[dim]k / j[/]                   Increase/decrease value
[dim]Space[/]                   Reset to 0

[bold]Modifiers[/]
[dim]Shift + j/k[/]             Fine adjustment (+/- 1)
[dim]Ctrl + j/k[/]              Coarse adjustment (+/- 16)
[dim]No modifier[/]             Normal adjustment (+/- 4)

[bold]Settings[/]
[dim]v[/]                       Switch to horizontal mode
[dim]o[/]                       Select MIDI output
[dim]c[/]                       Select MIDI channel
[dim]t[/]                       Change theme
[dim]?[/]                       Show this help"""

    HELP_TEXT_HORIZONTAL = """[bold]Selection[/]
[dim]1-8[/]                     Select fader directly
[dim]j / k[/]                   Move selection up/down
[dim]Esc[/]                     Deselect

[bold]Adjustment[/]
[dim]l / h[/]                   Increase/decrease value
[dim]Space[/]                   Reset to 0

[bold]Modifiers[/]
[dim]Shift + h/l[/]             Fine adjustment (+/- 1)
[dim]Ctrl + h/l[/]              Coarse adjustment (+/- 16)
[dim]No modifier[/]             Normal adjustment (+/- 4)

[bold]Settings[/]
[dim]v[/]                       Switch to vertical mode
[dim]o[/]                       Select MIDI output
[dim]c[/]                       Select MIDI channel
[dim]t[/]                       Change theme
[dim]?[/]                       Show this help"""

    def __init__(self, display_mode: str = MODE_VERTICAL) -> None:
        super().__init__()
        self.display_mode = display_mode

    @property
    def HELP_TEXT(self) -> str:
        if self.display_mode == MODE_HORIZONTAL:
            return self.HELP_TEXT_HORIZONTAL
        return self.HELP_TEXT_VERTICAL


class OutputPickerScreen(ModalScreen[tuple[str, bool] | None]):
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

    VIRTUAL_PORT_PREFIX = ">> Create Virtual: "

    def __init__(self, outputs: list[str], current: Optional[str] = None, virtual_name: str = DEFAULT_PORT_NAME) -> None:
        super().__init__()
        self.outputs = outputs
        self.current = current
        self.virtual_name = virtual_name

    def compose(self) -> ComposeResult:
        with Vertical(id="output-dialog"):
            yield Static("[bold]Select MIDI Output[/]", id="output-title")
            # Always show virtual port option first, then existing outputs
            options = [Option(f"{self.VIRTUAL_PORT_PREFIX}{self.virtual_name}", id="__virtual__")]
            # Filter out any None or empty outputs
            for o in self.outputs:
                if o:
                    options.append(Option(o, id=o))
            yield OptionList(*options, id="output-list")
            yield Static("[dim]enter[/] select  [dim]esc[/] cancel", id="output-hint")

    def on_mount(self) -> None:
        option_list = self.query_one("#output-list", OptionList)
        option_list.focus()
        # Default to virtual port (index 0)
        option_list.highlighted = 0

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_select(self) -> None:
        try:
            option_list = self.query_one("#output-list", OptionList)
            if option_list.highlighted is not None:
                option = option_list.get_option_at_index(option_list.highlighted)
                if option:
                    if option.id == "__virtual__":
                        self.dismiss((self.virtual_name, True))
                    else:
                        self.dismiss((option.id, False))
                    return
        except Exception:
            pass
        self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option:
            if event.option.id == "__virtual__":
                self.dismiss((self.virtual_name, True))
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


class FaderScreen(Screen):
    """Main fader screen."""

    BINDINGS = [
        Binding("v", "toggle_mode", "Toggle Mode", show=False),
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
    is_virtual_port: reactive[bool] = reactive(False)
    display_mode: reactive[str] = reactive(MODE_VERTICAL)

    def __init__(self, midi_engine: MidiEngine, initial_mode: str = MODE_VERTICAL) -> None:
        super().__init__()
        self.midi = midi_engine
        self._faders: list[FaderWidget] = []
        self._horizontal_faders: list[HorizontalFaderWidget] = []
        self._initial_mode = initial_mode

    def compose(self) -> ComposeResult:
        yield StatusBar(self._make_status())
        yield MainContent(id="main-content")
        yield ControlsFooter(self._initial_mode)

    def on_mount(self) -> None:
        """Build initial fader display after mount."""
        self.display_mode = self._initial_mode
        self._rebuild_fader_display()

    def _rebuild_fader_display(self) -> None:
        """Rebuild the fader display for current mode."""
        try:
            main_content = self.query_one("#main-content", MainContent)
            # Clear existing content
            main_content.remove_children()

            # Store current values if we have faders
            values = []
            if self._faders:
                values = [f.value for f in self._faders]
            elif self._horizontal_faders:
                values = [f.value for f in self._horizontal_faders]

            self._faders = []
            self._horizontal_faders = []

            if self.display_mode == MODE_HORIZONTAL:
                # Build horizontal layout
                container = HorizontalFaderContainer()
                main_content.mount(container)
                for i in range(8):
                    fader = HorizontalFaderWidget(
                        fader_index=i,
                        cc_number=DEFAULT_CC_NUMBERS[i],
                        label=DEFAULT_FADER_LABELS[i],
                        id=f"hfader-{i}",
                    )
                    if i < len(values):
                        fader.value = values[i]
                    if i == self.selected_fader:
                        fader.selected = True
                    self._horizontal_faders.append(fader)
                    container.mount(fader)
            else:
                # Build vertical layout
                fader_container = FaderContainer()
                main_content.mount(fader_container)
                for i in range(8):
                    fader = FaderWidget(
                        fader_index=i,
                        cc_number=DEFAULT_CC_NUMBERS[i],
                        label=DEFAULT_FADER_LABELS[i],
                        key_up=FADER_LABELS_UP[i],
                        key_down=FADER_LABELS_DOWN[i],
                        id=f"fader-{i}",
                    )
                    if i < len(values):
                        fader.value = values[i]
                    if i == self.selected_fader:
                        fader.selected = True
                    self._faders.append(fader)
                    fader_container.mount(fader)
                # Add side panel for vertical mode
                main_content.mount(SidePanel())
                self._update_side_panel()

            # Update footer
            try:
                footer = self.query_one(ControlsFooter)
                footer.set_mode(self.display_mode)
            except Exception:
                pass

        except Exception:
            pass

    def _get_active_faders(self):
        """Get the currently active fader list based on mode."""
        if self.display_mode == MODE_HORIZONTAL:
            return self._horizontal_faders
        return self._faders

    def _make_status(self) -> str:
        """Generate status bar content."""
        if self.midi_output:
            if self.is_virtual_port:
                output = f"[bold]{self.midi_output}[/] (virtual)"
            else:
                output = self.midi_output
        else:
            output = "[dim]None[/]"
        mode_indicator = "H" if self.display_mode == MODE_HORIZONTAL else "V"
        return (
            f"[bold]FADERCAT[/] [{mode_indicator}]  │  "
            f"Ch: {self.midi_channel + 1}  │  "
            f"Out: {output}"
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

    def watch_is_virtual_port(self, is_virtual: bool) -> None:
        """React to virtual port changes."""
        self._update_status()

    def watch_selected_fader(self, index: int) -> None:
        """React to fader selection changes."""
        faders = self._get_active_faders()
        for i, fader in enumerate(faders):
            fader.selected = (i == index)
        self._update_status()
        if self.display_mode == MODE_VERTICAL:
            self._update_side_panel()

    def _update_side_panel(self) -> None:
        """Update the side panel with selected fader info (vertical mode only)."""
        if self.display_mode != MODE_VERTICAL:
            return
        try:
            panel = self.query_one(SidePanel)
            faders = self._get_active_faders()
            if 0 <= self.selected_fader < len(faders):
                panel.update_fader(faders[self.selected_fader])
            else:
                panel.update_fader(None)
        except Exception:
            pass

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
        faders = self._get_active_faders()
        if 0 <= index < len(faders):
            fader = faders[index]
            new_value = max(0, min(127, fader.value + delta))
            if new_value != fader.value:
                fader.value = new_value
                self.midi.cc(fader.cc_number, new_value)
                # Update side panel if this is the selected fader (vertical mode)
                if index == self.selected_fader and self.display_mode == MODE_VERTICAL:
                    self._update_side_panel()

    def on_key(self, event) -> None:
        """Handle key press for fader control."""
        key = event.key

        # Check for modifier keys
        # Shift+letter comes through as uppercase, not "shift+letter"
        has_ctrl = key.startswith("ctrl+")

        # Extract base key
        base_key = key
        if has_ctrl:
            base_key = key[5:]  # Remove "ctrl+"

        # Detect shift by checking if key is uppercase letter
        has_shift = len(base_key) == 1 and base_key.isupper()
        if has_shift:
            base_key = base_key.lower()

        # Number keys 1-8 for fader selection
        if base_key in "12345678":
            self.selected_fader = int(base_key) - 1
            return

        # Mode-specific key bindings
        # Vertical: h/l = select, j/k = adjust
        # Horizontal: j/k = select, h/l = adjust
        if self.display_mode == MODE_HORIZONTAL:
            # Horizontal mode: j/k select, h/l adjust
            if base_key == "j":
                self._select_next()
                return
            if base_key == "k":
                self._select_prev()
                return
            if base_key == "h" and self.selected_fader >= 0:
                step = self._get_step(has_shift, has_ctrl)
                self._adjust_fader(self.selected_fader, -step)
                return
            if base_key == "l" and self.selected_fader >= 0:
                step = self._get_step(has_shift, has_ctrl)
                self._adjust_fader(self.selected_fader, step)
                return
        else:
            # Vertical mode: h/l select, j/k adjust
            if base_key == "h":
                self._select_prev()
                return
            if base_key == "l":
                self._select_next()
                return
            if base_key == "j" and self.selected_fader >= 0:
                step = self._get_step(has_shift, has_ctrl)
                self._adjust_fader(self.selected_fader, -step)
                return
            if base_key == "k" and self.selected_fader >= 0:
                step = self._get_step(has_shift, has_ctrl)
                self._adjust_fader(self.selected_fader, step)
                return

    def action_select_output(self) -> None:
        """Open output selection dialog."""
        # Filter out any None or empty outputs
        outputs = [o for o in self.midi.list_outputs() if o]

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
            OutputPickerScreen(outputs, self.midi_output or None, DEFAULT_PORT_NAME),
            handle_output
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
        self.app.push_screen(HelpScreen(self.display_mode))

    def action_reset_fader(self) -> None:
        """Reset selected fader to 0."""
        faders = self._get_active_faders()
        if 0 <= self.selected_fader < len(faders):
            fader = faders[self.selected_fader]
            fader.value = 0
            self.midi.cc(fader.cc_number, 0)
            if self.display_mode == MODE_VERTICAL:
                self._update_side_panel()

    def action_deselect(self) -> None:
        """Deselect current fader."""
        self.selected_fader = -1

    def action_toggle_mode(self) -> None:
        """Toggle between vertical and horizontal display modes."""
        if self.display_mode == MODE_VERTICAL:
            self.display_mode = MODE_HORIZONTAL
        else:
            self.display_mode = MODE_VERTICAL
        self._rebuild_fader_display()
        self._update_status()
        # Persist mode preference
        config_path = get_config_path("fadercat")
        set_display_mode(self.display_mode, config_path)

    def _select_prev(self) -> None:
        """Move selection to previous fader."""
        if self.selected_fader < 0:
            self.selected_fader = 0
        elif self.selected_fader > 0:
            self.selected_fader -= 1

    def _select_next(self) -> None:
        """Move selection to next fader."""
        if self.selected_fader < 0:
            self.selected_fader = 0
        elif self.selected_fader < 7:
            self.selected_fader += 1


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

        # Load display mode preference
        display_mode = get_display_mode(config_path)

        # Push the fader screen with saved mode
        fader_screen = FaderScreen(self.midi, initial_mode=display_mode)
        self.push_screen(fader_screen)

        # Open virtual MIDI port after screen is ready
        self.call_after_refresh(self._open_virtual_port)

    def _open_virtual_port(self) -> None:
        """Open virtual MIDI port."""
        if self.midi.open_virtual(DEFAULT_PORT_NAME):
            try:
                fader_screen = self.query_one(FaderScreen)
                fader_screen.midi_output = DEFAULT_PORT_NAME
                fader_screen.is_virtual_port = True
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
