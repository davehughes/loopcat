#!/usr/bin/env python3
"""Fetch base16 color schemes and convert to Textual themes."""

import json
import urllib.request
from pathlib import Path


# Base16 to Textual mapping:
# base00: darkest background -> background
# base01: lighter background -> surface
# base02: selection bg
# base03: comments -> (unused)
# base04: dark foreground
# base05: default foreground -> foreground
# base06-07: light foreground
# base08: red -> error
# base09: orange -> warning (alt)
# base0A: yellow -> warning
# base0B: green -> success
# base0C: cyan -> accent
# base0D: blue -> primary
# base0E: magenta -> secondary
# base0F: brown (unused)


def fetch_scheme_list():
    """Fetch list of available base16 schemes with download URLs."""
    url = "https://api.github.com/repos/tinted-theming/schemes/contents/base16"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def fetch_scheme(download_url: str) -> dict:
    """Fetch a single scheme YAML and parse it."""
    import yaml
    with urllib.request.urlopen(download_url) as resp:
        return yaml.safe_load(resp.read().decode())


def base16_to_textual(scheme: dict) -> dict:
    """Convert base16 scheme to Textual theme format."""
    palette = scheme["palette"]
    return {
        "name": scheme["name"].lower().replace(" ", "-"),
        "display_name": scheme["name"],
        "dark": scheme.get("variant", "dark") == "dark",
        "primary": palette["base0D"],
        "secondary": palette["base0E"],
        "accent": palette["base0C"],
        "background": palette["base00"],
        "surface": palette["base01"],
        "foreground": palette["base05"],
        "warning": palette["base0A"],
        "error": palette["base08"],
        "success": palette["base0B"],
    }


def generate_python_themes(themes: list[dict]) -> str:
    """Generate Python code for Textual themes."""
    lines = [
        '"""Auto-generated themes from base16 color schemes."""',
        "",
        "from textual.theme import Theme",
        "",
        "BASE16_THEMES = [",
    ]

    for t in themes:
        lines.append(f"    Theme(")
        lines.append(f'        name="{t["name"]}",')
        lines.append(f'        primary="{t["primary"]}",')
        lines.append(f'        secondary="{t["secondary"]}",')
        lines.append(f'        accent="{t["accent"]}",')
        lines.append(f'        background="{t["background"]}",')
        lines.append(f'        surface="{t["surface"]}",')
        lines.append(f'        warning="{t["warning"]}",')
        lines.append(f'        error="{t["error"]}",')
        lines.append(f'        success="{t["success"]}",')
        lines.append(f'        dark={t["dark"]},')
        lines.append(f"    ),")

    lines.append("]")
    lines.append("")
    lines.append("")
    lines.append("def register_base16_themes(app):")
    lines.append('    """Register all base16 themes with a Textual app."""')
    lines.append("    for theme in BASE16_THEMES:")
    lines.append("        app.register_theme(theme)")
    lines.append("")

    return "\n".join(lines)


def main():
    import yaml  # Check if pyyaml is available

    print("Fetching base16 scheme list...")
    files = fetch_scheme_list()
    yaml_files = [(f["name"], f["download_url"]) for f in files if f["name"].endswith(".yaml")]

    print(f"Found {len(yaml_files)} schemes, fetching...")

    themes = []
    for i, (name, url) in enumerate(yaml_files):
        try:
            scheme = fetch_scheme(url)
            theme = base16_to_textual(scheme)
            themes.append(theme)
            print(f"  [{i+1}/{len(yaml_files)}] {theme['display_name']}")
        except Exception as e:
            print(f"  [{i+1}/{len(yaml_files)}] SKIP {name}: {e}")

    print(f"\nConverted {len(themes)} themes")

    # Generate Python file
    output = Path(__file__).parent.parent / "src" / "loopcat" / "base16_themes.py"
    output.write_text(generate_python_themes(themes))
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
