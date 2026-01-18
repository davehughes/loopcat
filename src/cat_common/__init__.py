"""Shared infrastructure for cat_* TUI apps (loopcat, gridcat, fadercat)."""

from cat_common.base16_themes import BASE16_THEMES
from cat_common.config import (
    DEFAULT_THEME,
    get_config_dir,
    get_config_path,
    get_data_dir,
    get_theme,
    load_config,
    save_config,
    set_theme,
)
from cat_common.themes import BUILTIN_THEMES, THEMES, ThemePickerScreen, register_themes
from cat_common.widgets import ControlsFooter, HelpScreenBase

__all__ = [
    # Config
    "get_config_dir",
    "get_data_dir",
    "get_config_path",
    "load_config",
    "save_config",
    "get_theme",
    "set_theme",
    "DEFAULT_THEME",
    # Themes
    "BUILTIN_THEMES",
    "THEMES",
    "BASE16_THEMES",
    "ThemePickerScreen",
    "register_themes",
    # Widgets
    "ControlsFooter",
    "HelpScreenBase",
]
