"""Configuration management for loopcat."""

import os
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_CONFIG_PATH = Path.home() / ".loopcat" / "config.yaml"


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
