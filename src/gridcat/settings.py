"""Settings management for gridcat."""

from dataclasses import dataclass, field, asdict
from typing import Literal

from cat_common import get_config_path, load_config, save_config


# Play modes
PlayMode = Literal["hold", "trigger"]


@dataclass
class GridcatSettings:
    """Gridcat application settings."""

    # Note play mode: "hold" (sustain while key held) or "trigger" (instant on/off)
    play_mode: PlayMode = "hold"

    # Hold mode settings (in milliseconds)
    hold_initial_delay_ms: int = 300  # Wait for first key repeat
    hold_repeat_delay_ms: int = 120  # Wait between key repeats

    # Trigger mode settings (in milliseconds)
    trigger_duration_ms: int = 100  # Time between note on and note off

    @classmethod
    def load(cls) -> "GridcatSettings":
        """Load settings from config file."""
        config_path = get_config_path("gridcat")
        config = load_config(config_path)
        settings_dict = config.get("settings", {})

        return cls(
            play_mode=settings_dict.get("play_mode", "hold"),
            hold_initial_delay_ms=settings_dict.get("hold_initial_delay_ms", 300),
            hold_repeat_delay_ms=settings_dict.get("hold_repeat_delay_ms", 120),
            trigger_duration_ms=settings_dict.get("trigger_duration_ms", 100),
        )

    def save(self) -> None:
        """Save settings to config file."""
        config_path = get_config_path("gridcat")
        config = load_config(config_path)
        config["settings"] = asdict(self)
        save_config(config, config_path)


# Global settings instance (loaded on import, can be reloaded)
_settings: GridcatSettings | None = None


def get_settings() -> GridcatSettings:
    """Get the current settings (loads from disk if not cached)."""
    global _settings
    if _settings is None:
        _settings = GridcatSettings.load()
    return _settings


def save_settings(settings: GridcatSettings) -> None:
    """Save settings and update the cache."""
    global _settings
    settings.save()
    _settings = settings


def reload_settings() -> GridcatSettings:
    """Force reload settings from disk."""
    global _settings
    _settings = GridcatSettings.load()
    return _settings
