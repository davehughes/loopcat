"""Shared widgets for cat_* apps."""

from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static


class ControlsFooter(Static):
    """Custom footer widget with grouped controls.

    A simple footer that docks at the bottom and displays key hints.
    Pass custom content to customize for each app.
    """

    DEFAULT_CSS = """
    ControlsFooter {
        dock: bottom;
        height: 1;
        background: $primary;
        padding: 0 1;
    }
    """

    def __init__(self, content: Optional[str] = None, **kwargs) -> None:
        """Initialize the footer.

        Args:
            content: Rich text content to display. If None, shows placeholder.
            **kwargs: Additional arguments passed to Static.
        """
        if content is None:
            content = "[dim]No controls defined[/]"
        super().__init__(content, **kwargs)


class HelpScreenBase(ModalScreen):
    """Base class for help screens showing keyboard shortcuts.

    Subclass and override HELP_TEXT to customize the help content.
    """

    CSS = """
    HelpScreenBase {
        align: center middle;
    }

    #help-dialog {
        width: 60;
        height: auto;
        max-height: 80%;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    #help-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #help-content {
        height: auto;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    # Override this in subclasses
    HELP_TEXT = "[dim]No help available.[/]"
    TITLE = "Keyboard Shortcuts"

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help-dialog"):
            yield Static(f"[bold]{self.TITLE}[/]", id="help-title")
            yield Static(self.HELP_TEXT, id="help-content")
            yield Static("\n[dim]Press ? or esc to close[/]", id="help-hint")
