"""Shared theme management for cat_* apps."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from cat_common.base16_themes import BASE16_THEMES


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


def register_themes(app) -> None:
    """Register all base16 themes with a Textual app.

    Args:
        app: The Textual App instance.
    """
    for theme in BASE16_THEMES:
        app.register_theme(theme)
