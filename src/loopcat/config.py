"""Configuration management for loopcat."""

import os
from pathlib import Path
from typing import Optional

import yaml


def get_config_dir() -> Path:
    """Get the config directory following XDG standard.

    Uses $XDG_CONFIG_HOME/loopcat if set, otherwise ~/.config/loopcat.
    """
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "loopcat"
    return Path.home() / ".config" / "loopcat"


def get_data_dir() -> Path:
    """Get the data directory following XDG standard.

    Uses $XDG_DATA_HOME/loopcat if set, otherwise ~/.local/share/loopcat.
    """
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "loopcat"
    return Path.home() / ".local" / "share" / "loopcat"


DEFAULT_CONFIG_PATH = get_config_dir() / "config.yaml"
DEFAULT_DATA_DIR = get_data_dir()
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "catalog.db"
DEFAULT_WAV_DIR = DEFAULT_DATA_DIR / "wav"
DEFAULT_MP3_DIR = DEFAULT_DATA_DIR / "mp3"


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
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


def save_config(config: dict, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Save configuration to YAML file.

    Args:
        config: Configuration dictionary.
        config_path: Path to the config file.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def get_gemini_api_key(config_path: Path = DEFAULT_CONFIG_PATH) -> Optional[str]:
    """Get Gemini API key from config or environment.

    Priority:
    1. GOOGLE_API_KEY environment variable
    2. Config file

    Args:
        config_path: Path to the config file.

    Returns:
        API key or None if not configured.
    """
    # Environment variable takes priority
    env_key = os.environ.get("GOOGLE_API_KEY")
    if env_key:
        return env_key

    # Fall back to config file
    config = load_config(config_path)
    return config.get("gemini_api_key")


def set_gemini_api_key(api_key: str, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Store Gemini API key in config file.

    Args:
        api_key: The API key to store.
        config_path: Path to the config file.
    """
    config = load_config(config_path)
    config["gemini_api_key"] = api_key
    save_config(config, config_path)


# Default theme
DEFAULT_THEME = "textual-dark"


def get_theme(config_path: Path = DEFAULT_CONFIG_PATH) -> str:
    """Get the current theme from config.

    Args:
        config_path: Path to the config file.

    Returns:
        Theme name (defaults to textual-dark).
    """
    config = load_config(config_path)
    return config.get("theme", DEFAULT_THEME)


def set_theme(theme: str, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Store theme in config file.

    Args:
        theme: The theme name to store.
        config_path: Path to the config file.
    """
    config = load_config(config_path)
    config["theme"] = theme
    save_config(config, config_path)
