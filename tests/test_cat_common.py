"""Tests for cat_common shared infrastructure."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from cat_common import (
    BASE16_THEMES,
    BUILTIN_THEMES,
    THEMES,
    ThemePickerScreen,
    ControlsFooter,
    HelpScreenBase,
    get_config_dir,
    get_data_dir,
    get_config_path,
    load_config,
    save_config,
    get_theme,
    set_theme,
    DEFAULT_THEME,
)


class TestConfigXdgPaths:
    """Tests for XDG-compliant config paths."""

    def test_config_dir_uses_xdg_when_set(self):
        """Config respects XDG_CONFIG_HOME."""
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}):
            result = get_config_dir("testapp")
            assert result == Path("/custom/config/testapp")

    def test_config_dir_uses_home_fallback(self):
        """Config falls back to ~/.config when XDG not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove XDG_CONFIG_HOME if present
            os.environ.pop("XDG_CONFIG_HOME", None)
            result = get_config_dir("testapp")
            assert result == Path.home() / ".config" / "testapp"

    def test_data_dir_uses_xdg_when_set(self):
        """Data dir respects XDG_DATA_HOME."""
        with patch.dict(os.environ, {"XDG_DATA_HOME": "/custom/data"}):
            result = get_data_dir("testapp")
            assert result == Path("/custom/data/testapp")

    def test_data_dir_uses_home_fallback(self):
        """Data dir falls back to ~/.local/share when XDG not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("XDG_DATA_HOME", None)
            result = get_data_dir("testapp")
            assert result == Path.home() / ".local" / "share" / "testapp"

    def test_config_path_returns_file_path(self):
        """get_config_path returns a file path in the config dir."""
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}):
            result = get_config_path("testapp")
            assert result == Path("/custom/config/testapp/config.yaml")

    def test_different_app_names_get_different_paths(self):
        """Different app names result in different config directories."""
        dir1 = get_config_dir("app1")
        dir2 = get_config_dir("app2")
        assert dir1 != dir2
        assert "app1" in str(dir1)
        assert "app2" in str(dir2)


class TestThemePersistence:
    """Tests for theme get/set functionality."""

    def test_theme_persistence_round_trip(self):
        """get_theme/set_theme round-trips correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Set a theme
            set_theme("dracula", config_path)

            # Get it back
            result = get_theme(config_path)
            assert result == "dracula"

    def test_get_theme_returns_default_when_missing(self):
        """get_theme returns default when config doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent" / "config.json"
            result = get_theme(config_path)
            assert result == DEFAULT_THEME

    def test_set_theme_creates_config_dir(self):
        """set_theme creates the config directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "subdir" / "config.json"
            set_theme("nord", config_path)

            assert config_path.exists()

    def test_config_load_save_round_trip(self):
        """load_config/save_config preserve data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            test_config = {"theme": "gruvbox", "custom_key": "value"}
            save_config(test_config, config_path)

            loaded = load_config(config_path)
            assert loaded == test_config


class TestThemesList:
    """Tests for the themes list."""

    def test_themes_list_not_empty(self):
        """THEMES list contains builtin + base16 themes."""
        assert len(THEMES) > 0

    def test_themes_contains_builtin_themes(self):
        """THEMES includes all builtin Textual themes."""
        for theme in BUILTIN_THEMES:
            assert theme in THEMES, f"Missing builtin theme: {theme}"

    def test_themes_contains_textual_dark(self):
        """THEMES includes textual-dark (common default)."""
        assert "textual-dark" in THEMES

    def test_themes_has_no_duplicates(self):
        """THEMES list has no duplicate entries."""
        assert len(THEMES) == len(set(THEMES))

    def test_builtin_themes_count(self):
        """Builtin themes list has expected count."""
        # Based on the current implementation
        assert len(BUILTIN_THEMES) >= 15


class TestBase16Themes:
    """Tests for base16 themes."""

    def test_base16_themes_not_empty(self):
        """BASE16_THEMES contains themes."""
        assert len(BASE16_THEMES) > 0

    def test_base16_themes_are_valid_theme_objects(self):
        """All BASE16_THEMES are valid Theme objects."""
        from textual.theme import Theme

        for theme in BASE16_THEMES:
            assert isinstance(theme, Theme), f"{theme} is not a Theme instance"
            assert hasattr(theme, "name"), f"Theme missing 'name' attribute"
            assert theme.name, f"Theme has empty name"

    def test_base16_themes_have_unique_names(self):
        """All BASE16_THEMES have unique names."""
        names = [t.name for t in BASE16_THEMES]
        assert len(names) == len(set(names)), "Duplicate theme names found"


class TestThemePickerScreen:
    """Tests for ThemePickerScreen."""

    def test_theme_picker_creation(self):
        """Test that ThemePickerScreen can be instantiated."""
        screen = ThemePickerScreen("textual-dark")
        assert screen.current_theme == "textual-dark"
        assert screen.filter_text == ""

    def test_theme_picker_with_different_theme(self):
        """ThemePickerScreen stores the provided current theme."""
        screen = ThemePickerScreen("dracula")
        assert screen.current_theme == "dracula"


class TestControlsFooter:
    """Tests for ControlsFooter widget."""

    def test_controls_footer_with_content(self):
        """ControlsFooter accepts custom content."""
        footer = ControlsFooter("[bold]Test[/]")
        # Widget should be created successfully
        assert footer is not None

    def test_controls_footer_default_content(self):
        """ControlsFooter has default content when none provided."""
        footer = ControlsFooter()
        # Widget should be created with default content
        assert footer is not None

    def test_controls_footer_has_expected_css(self):
        """ControlsFooter has dock: bottom CSS."""
        assert "dock: bottom" in ControlsFooter.DEFAULT_CSS


class TestHelpScreenBase:
    """Tests for HelpScreenBase."""

    def test_help_screen_base_defaults(self):
        """HelpScreenBase has default HELP_TEXT and TITLE."""
        assert HelpScreenBase.HELP_TEXT is not None
        assert HelpScreenBase.TITLE is not None

    def test_help_screen_base_bindings(self):
        """HelpScreenBase has dismiss bindings."""
        binding_keys = [b.key for b in HelpScreenBase.BINDINGS]
        assert "escape" in binding_keys
        assert "q" in binding_keys
