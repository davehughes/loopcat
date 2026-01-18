"""CLI interface for loopcat."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from loopcat import __version__
from loopcat.config import DEFAULT_DB_PATH, DEFAULT_MP3_DIR, DEFAULT_WAV_DIR
from loopcat.database import Database

# ASCII logo
LOGO = """
    ∞╱╲_╱╲∞
    (=◕ᴥ◕=)  LOOPCAT
    ╰─────╯  ═══════○
"""

# Default import source
DEFAULT_SOURCE = Path("/Volumes/BOSS_RC-300")

app = typer.Typer(
    name="loopcat",
    help="Catalog WAV files from Boss RC-300 with AI-powered audio analysis.",
    invoke_without_command=True,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(LOGO)
        console.print(f"Version: {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """Loopcat - Catalog your RC-300 loops with AI-powered analysis."""
    if ctx.invoked_subcommand is None:
        # Default to play command
        ctx.invoke(play)


@app.command()
def auth(
    api_key: str = typer.Option(
        None,
        "--key",
        "-k",
        help="Gemini API key to store.",
        prompt="Enter your Gemini API key",
        hide_input=True,
    ),
) -> None:
    """Configure Gemini API key for audio analysis."""
    from loopcat.config import get_gemini_api_key, set_gemini_api_key

    from loopcat.config import DEFAULT_CONFIG_PATH

    set_gemini_api_key(api_key)
    console.print(f"[green]API key saved[/green] to {DEFAULT_CONFIG_PATH}")

    # Verify it works
    stored_key = get_gemini_api_key()
    if stored_key:
        masked = stored_key[:4] + "..." + stored_key[-4:]
        console.print(f"Key: {masked}")


# Import themes from tui.py to stay in sync
from loopcat.tui import THEMES, BASE16_THEMES

# Terminal colors available in simple-term-menu
# Using typical bright terminal colors (not full saturation gray which pulls everything)
TERM_COLORS = {
    "red": (205, 49, 49),
    "green": (13, 188, 121),
    "yellow": (229, 229, 16),
    "blue": (36, 114, 200),
    "purple": (188, 63, 188),
    "cyan": (17, 168, 205),
}


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def closest_term_color(hex_color: str) -> str:
    """Find the closest terminal color to a hex color."""
    try:
        r, g, b = hex_to_rgb(hex_color)
    except (ValueError, IndexError):
        return "cyan"  # Default fallback

    min_dist = float("inf")
    closest = "cyan"

    for name, (tr, tg, tb) in TERM_COLORS.items():
        # Weighted Euclidean distance (human eye is more sensitive to green)
        dist = (2 * (r - tr) ** 2) + (4 * (g - tg) ** 2) + (3 * (b - tb) ** 2)
        if dist < min_dist:
            min_dist = dist
            closest = name

    return closest


def get_menu_style_from_theme() -> dict:
    """Get menu style based on current TUI theme."""
    from loopcat.config import get_theme

    theme_name = get_theme()

    # Try to find the theme's primary color
    primary_color = None

    # Check base16 themes first
    for theme in BASE16_THEMES:
        if theme.name == theme_name:
            primary_color = theme.primary
            break

    # Built-in theme color mappings (approximate)
    builtin_primaries = {
        "textual-dark": "#00ff00",
        "textual-light": "#004400",
        "nord": "#88c0d0",
        "gruvbox": "#fabd2f",
        "dracula": "#bd93f9",
        "tokyo-night": "#7aa2f7",
        "monokai": "#a6e22e",
        "catppuccin-mocha": "#cba6f7",
        "catppuccin-latte": "#8839ef",
        "solarized-dark": "#268bd2",
        "solarized-light": "#268bd2",
        "rose-pine": "#c4a7e7",
        "rose-pine-moon": "#c4a7e7",
        "rose-pine-dawn": "#907aa9",
        "atom-one-dark": "#61afef",
        "atom-one-light": "#4078f2",
        "flexoki": "#ce5d97",
        "textual-ansi": "#00ffff",
    }

    if primary_color is None:
        primary_color = builtin_primaries.get(theme_name, "#00ffff")

    color = closest_term_color(primary_color)

    return {
        "menu_cursor_style": (f"fg_{color}", "bold"),
        "menu_highlight_style": ("fg_black", f"bg_{color}"),
    }


def get_menu_style() -> dict:
    """Get menu style kwargs - uses theme colors or manual override."""
    from loopcat.config import load_config
    config = load_config()

    # Check for manual override first
    if "menu_style" in config:
        style_name = config["menu_style"]
        # Manual color presets
        presets = {
            "cyan": {"menu_cursor_style": ("fg_cyan", "bold"), "menu_highlight_style": ("fg_black", "bg_cyan")},
            "yellow": {"menu_cursor_style": ("fg_yellow", "bold"), "menu_highlight_style": ("fg_black", "bg_yellow")},
            "green": {"menu_cursor_style": ("fg_green", "bold"), "menu_highlight_style": ("fg_black", "bg_green")},
            "purple": {"menu_cursor_style": ("fg_purple", "bold"), "menu_highlight_style": ("fg_black", "bg_purple")},
            "red": {"menu_cursor_style": ("fg_red", "bold"), "menu_highlight_style": ("fg_black", "bg_red")},
            "blue": {"menu_cursor_style": ("fg_blue", "bold"), "menu_highlight_style": ("fg_black", "bg_blue")},
        }
        if style_name in presets:
            return presets[style_name]

    # Default: derive from current theme
    return get_menu_style_from_theme()


@app.command()
def theme(
    name: Optional[str] = typer.Argument(
        None,
        help="Theme name to set. If omitted, shows an interactive picker.",
    ),
) -> None:
    """Set the TUI color theme."""
    from simple_term_menu import TerminalMenu

    from loopcat.config import DEFAULT_CONFIG_PATH, get_theme, set_theme

    current = get_theme()

    if name:
        # Direct set
        if name not in THEMES:
            console.print(f"[red]Error:[/red] Unknown theme '{name}'")
            console.print(f"Available: {', '.join(THEMES)}")
            raise typer.Exit(1)
        set_theme(name)
        console.print(f"[green]Theme set to:[/green] {name}")
        return

    # Interactive picker
    current_index = THEMES.index(current) if current in THEMES else 0
    menu_entries = [f"{'● ' if t == current else '  '}{t}" for t in THEMES]

    menu = TerminalMenu(
        menu_entries,
        title="  Select a theme (current marked with ●):\n",
        cursor_index=current_index,
        **get_menu_style(),
    )

    selected = menu.show()
    if selected is None:
        console.print("[yellow]Cancelled[/yellow]")
        return

    selected_theme = THEMES[selected]
    set_theme(selected_theme)
    console.print(f"[green]Theme set to:[/green] {selected_theme}")
    console.print(f"Saved to {DEFAULT_CONFIG_PATH}")


@app.command()
def menu_style(
    style: Optional[str] = typer.Argument(
        None,
        help="Menu style: 'auto' (match theme), or a color (cyan, yellow, green, purple, red, blue).",
    ),
) -> None:
    """Set the terminal menu color style."""
    from simple_term_menu import TerminalMenu

    from loopcat.config import DEFAULT_CONFIG_PATH, get_theme, load_config, save_config

    config = load_config()
    current = config.get("menu_style", "auto")
    available = ["auto", "cyan", "yellow", "green", "purple", "red", "blue"]

    if style:
        # Direct set
        if style not in available:
            console.print(f"[red]Error:[/red] Unknown style '{style}'")
            console.print(f"Available: {', '.join(available)}")
            raise typer.Exit(1)
        if style == "auto":
            # Remove override to use theme-derived colors
            config.pop("menu_style", None)
        else:
            config["menu_style"] = style
        save_config(config)
        console.print(f"[green]Menu style set to:[/green] {style}")
        return

    # Get current theme info for auto preview
    theme_name = get_theme()
    auto_style = get_menu_style_from_theme()
    auto_color = auto_style["menu_cursor_style"][0].replace("fg_", "")

    # Show preview of all styles
    console.print("\n  [bold]Menu Style Preview:[/bold]\n")
    console.print(f"  [dim]Current theme: {theme_name}[/dim]\n")

    for name in available:
        if name == "auto":
            color = auto_color
            label = f"auto ({color})"
        else:
            color = name
            label = name
        marker = "●" if name == current else " "
        console.print(f"  {marker} [{color}]{label:16}[/] │ [black on {color}] Selected Item [/] [dim]unselected[/]")
    console.print()

    # Interactive picker
    current_index = available.index(current) if current in available else 0

    menu_entries = [f"{'● ' if s == current else '  '}{s}" for s in available]

    menu = TerminalMenu(
        menu_entries,
        title="  Select a menu style:\n",
        cursor_index=current_index,
        **get_menu_style(),
    )

    selected = menu.show()
    if selected is None:
        console.print("[yellow]Cancelled[/yellow]")
        return

    selected_style = available[selected]
    if selected_style == "auto":
        config.pop("menu_style", None)
    else:
        config["menu_style"] = selected_style
    save_config(config)
    console.print(f"[green]Menu style set to:[/green] {selected_style}")
    console.print(f"Saved to {DEFAULT_CONFIG_PATH}")


@app.command("import")
def import_(
    source: Path = typer.Argument(
        DEFAULT_SOURCE,
        help="Source directory containing RC-300 WAV files.",
        exists=False,  # Don't require existence at parse time
    ),
    db_path: Path = typer.Option(
        DEFAULT_DB_PATH,
        "--db",
        help="Path to the SQLite database.",
    ),
    wav_dir: Path = typer.Option(
        DEFAULT_WAV_DIR,
        "--wav-dir",
        help="Directory to store managed WAV files.",
    ),
) -> None:
    """Import WAV files from RC-300 or backup folder."""
    from loopcat.importer import import_from_source

    if not source.exists():
        console.print(f"[red]Error:[/red] Source directory not found: {source}")
        raise typer.Exit(1)

    db = Database(db_path)
    import_from_source(source, db, wav_dir, console)


@app.command()
def convert(
    patch: Optional[int] = typer.Option(
        None,
        "--patch",
        "-p",
        help="Convert only a specific patch (by catalog number).",
    ),
    db_path: Path = typer.Option(
        DEFAULT_DB_PATH,
        "--db",
        help="Path to the SQLite database.",
    ),
    mp3_dir: Path = typer.Option(
        DEFAULT_MP3_DIR,
        "--mp3-dir",
        help="Directory to store converted MP3 files.",
    ),
) -> None:
    """Convert WAV files to MP3 for analysis."""
    from loopcat.converter import convert_tracks

    db = Database(db_path)
    convert_tracks(db, mp3_dir, console, patch_number=patch)


@app.command()
def analyze(
    patch: Optional[int] = typer.Option(
        None,
        "--patch",
        "-p",
        help="Analyze only a specific patch (by catalog number).",
    ),
    db_path: Path = typer.Option(
        DEFAULT_DB_PATH,
        "--db",
        help="Path to the SQLite database.",
    ),
) -> None:
    """Analyze patches with Gemini AI and librosa."""
    from loopcat.analyzer import analyze_patches

    db = Database(db_path)
    analyze_patches(db, console, patch_number=patch)


@app.command("list")
@app.command("ls", hidden=True)
def list_patches(
    patch: Optional[int] = typer.Option(
        None,
        "--patch",
        "-p",
        help="Show only a specific patch (by catalog number).",
    ),
    bank: Optional[int] = typer.Option(
        None,
        "--bank",
        "-b",
        help="Filter by original RC-300 bank number.",
    ),
    db_path: Path = typer.Option(
        DEFAULT_DB_PATH,
        "--db",
        help="Path to the SQLite database.",
    ),
) -> None:
    """List all patches and tracks in the catalog."""
    db = Database(db_path)

    if patch is not None:
        patches = [db.get_patch(patch)] if db.get_patch(patch) else []
    elif bank is not None:
        patches = db.get_patches_by_bank(bank)
    else:
        patches = db.get_all_patches()

    if not patches:
        console.print("[yellow]No patches found.[/yellow]")
        return

    for p in patches:
        _print_patch(p)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query."),
    db_path: Path = typer.Option(
        DEFAULT_DB_PATH,
        "--db",
        help="Path to the SQLite database.",
    ),
) -> None:
    """Search the catalog using full-text search."""
    db = Database(db_path)
    patches = db.search(query)

    if not patches:
        console.print(f"[yellow]No results for '{query}'.[/yellow]")
        return

    console.print(f"[green]Found {len(patches)} patch(es):[/green]\n")
    for p in patches:
        _print_patch(p)


@app.command()
def export(
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Export format: json, csv",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Output file or directory.",
    ),
    db_path: Path = typer.Option(
        DEFAULT_DB_PATH,
        "--db",
        help="Path to the SQLite database.",
    ),
) -> None:
    """Export catalog to various formats."""
    from loopcat.export import export_catalog

    db = Database(db_path)
    export_catalog(db, format, output, console)


@app.command()
def play(
    patch: Optional[int] = typer.Argument(
        None,
        help="Patch catalog number to play. If omitted, shows a selector.",
    ),
    db_path: Path = typer.Option(
        DEFAULT_DB_PATH,
        "--db",
        help="Path to the SQLite database.",
    ),
) -> None:
    """Play a patch with TUI controls (mimics RC-300)."""
    from loopcat.tui import run_app

    db = Database(db_path)
    all_patches = db.get_all_patches()

    if not all_patches:
        console.print("[yellow]No patches in catalog. Run 'loopcat import' first.[/yellow]")
        raise typer.Exit(1)

    # If patch specified on command line, start with it
    initial_patch = None
    if patch is not None:
        initial_patch = db.get_patch(patch)
        if not initial_patch:
            console.print(f"[red]Error:[/red] Patch #{patch} not found.")
            raise typer.Exit(1)

    # Run the TUI app
    run_app(all_patches, initial_patch)


def _print_patch(patch) -> None:
    """Print a patch with its tracks."""
    # Header
    name = patch.analysis.suggested_name if patch.analysis else f"Patch #{patch.catalog_number}"
    console.print(f"[bold cyan]#{patch.catalog_number}[/bold cyan] {name} [dim](bank {patch.original_bank})[/dim]")

    if patch.analysis:
        console.print(f"  [dim]{patch.analysis.description}[/dim]")
        console.print(f"  Style: {patch.analysis.musical_style} | Energy: {patch.analysis.energy_level}/10")
        if patch.analysis.mood:
            console.print(f"  Mood: {', '.join(patch.analysis.mood)}")
        if patch.analysis.tags:
            console.print(f"  Tags: {', '.join(patch.analysis.tags)}")

    # Tracks table
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("Track", style="cyan")
    table.add_column("Name")
    table.add_column("Role")
    table.add_column("Duration")
    table.add_column("BPM")
    table.add_column("Key")

    for track in patch.tracks:
        name = track.analysis.suggested_name if track.analysis else track.filename
        role = track.analysis.role if track.analysis else "-"
        duration = f"{track.duration_seconds:.1f}s"
        bpm = f"{track.bpm:.0f}" if track.bpm else "-"
        key = track.detected_key or "-"
        table.add_row(str(track.track_number), name, role, duration, bpm, key)

    console.print(table)
    console.print()
