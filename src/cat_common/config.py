"""Shared configuration management for cat_* apps."""

import os
from pathlib import Path

import yaml


def get_config_dir(app_name: str = "loopcat") -> Path:
    """Get the config directory following XDG standard.

    Uses $XDG_CONFIG_HOME/{app_name} if set, otherwise ~/.config/{app_name}.

    Args:
        app_name: Application name for the config subdirectory.

    Returns:
        Path to the config directory.
    """
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / app_name
    return Path.home() / ".config" / app_name


def get_data_dir(app_name: str = "loopcat") -> Path:
    """Get the data directory following XDG standard.

    Uses $XDG_DATA_HOME/{app_name} if set, otherwise ~/.local/share/{app_name}.

    Args:
        app_name: Application name for the data subdirectory.

    Returns:
        Path to the data directory.
    """
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / app_name
    return Path.home() / ".local" / "share" / app_name


def get_config_path(app_name: str = "loopcat") -> Path:
    """Get the default config file path for an app.

    Args:
        app_name: Application name.

    Returns:
        Path to config.yaml for the app.
    """
    return get_config_dir(app_name) / "config.yaml"


def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Path to the config file.

    Returns:
        Configuration dictionary (empty if file doesn't exist).
    """
    if not config_path.exists():
        return {}

    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def save_config(config: dict, config_path: Path) -> None:
    """Save configuration to YAML file.

    Args:
        config: Configuration dictionary.
        config_path: Path to the config file.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


# Default theme for all cat_* apps
DEFAULT_THEME = "textual-dark"


def get_theme(config_path: Path) -> str:
    """Get the current theme from config.

    Args:
        config_path: Path to the config file.

    Returns:
        Theme name (defaults to textual-dark).
    """
    config = load_config(config_path)
    return config.get("theme", DEFAULT_THEME)


def set_theme(theme: str, config_path: Path) -> None:
    """Store theme in config file.

    Args:
        theme: The theme name to store.
        config_path: Path to the config file.
    """
    config = load_config(config_path)
    config["theme"] = theme
    save_config(config, config_path)
