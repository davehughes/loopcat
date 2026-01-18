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
    no_args_is_help=True,
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
    pass


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
from loopcat.tui import THEMES

# Menu color presets for simple-term-menu (limited to 8 basic colors)
MENU_STYLES = {
    "default": {
        "menu_cursor_style": ("fg_cyan", "bold"),
        "menu_highlight_style": ("fg_black", "bg_cyan"),
    },
    "yellow": {
        "menu_cursor_style": ("fg_yellow", "bold"),
        "menu_highlight_style": ("fg_black", "bg_yellow"),
    },
    "green": {
        "menu_cursor_style": ("fg_green", "bold"),
        "menu_highlight_style": ("fg_black", "bg_green"),
    },
    "purple": {
        "menu_cursor_style": ("fg_purple", "bold"),
        "menu_highlight_style": ("fg_black", "bg_purple"),
    },
    "red": {
        "menu_cursor_style": ("fg_red", "bold"),
        "menu_highlight_style": ("fg_black", "bg_red"),
    },
    "blue": {
        "menu_cursor_style": ("fg_blue", "bold"),
        "menu_highlight_style": ("fg_black", "bg_blue"),
    },
}


def get_menu_style() -> dict:
    """Get menu style kwargs based on config."""
    from loopcat.config import load_config
    config = load_config()
    style_name = config.get("menu_style", "default")
    return MENU_STYLES.get(style_name, MENU_STYLES["default"])


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
        help="Menu style to set. If omitted, shows an interactive picker.",
    ),
) -> None:
    """Set the terminal menu color style."""
    from simple_term_menu import TerminalMenu

    from loopcat.config import DEFAULT_CONFIG_PATH, load_config, save_config

    config = load_config()
    current = config.get("menu_style", "default")

    if style:
        # Direct set
        if style not in MENU_STYLES:
            console.print(f"[red]Error:[/red] Unknown style '{style}'")
            console.print(f"Available: {', '.join(MENU_STYLES.keys())}")
            raise typer.Exit(1)
        config["menu_style"] = style
        save_config(config)
        console.print(f"[green]Menu style set to:[/green] {style}")
        return

    # Show preview of all styles
    console.print("\n  [bold]Menu Style Preview:[/bold]\n")
    for name in MENU_STYLES:
        # Map simple-term-menu colors to Rich colors
        color = name if name != "default" else "cyan"
        marker = "●" if name == current else " "
        console.print(f"  {marker} [{color}]{name:10}[/] │ [black on {color}] Selected Item [/] [dim]unselected[/]")
    console.print()

    # Interactive picker
    style_names = list(MENU_STYLES.keys())
    current_index = style_names.index(current) if current in style_names else 0

    menu_entries = [f"{'● ' if s == current else '  '}{s}" for s in style_names]

    menu = TerminalMenu(
        menu_entries,
        title="  Select a menu style:\n",
        cursor_index=current_index,
        **MENU_STYLES.get(current, MENU_STYLES["default"]),
    )

    selected = menu.show()
    if selected is None:
        console.print("[yellow]Cancelled[/yellow]")
        return

    selected_style = style_names[selected]
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
    from simple_term_menu import TerminalMenu

    from loopcat.tui import run_player

    db = Database(db_path)
    all_patches = db.get_all_patches()

    if not all_patches:
        console.print("[yellow]No patches in catalog. Run 'loopcat import' first.[/yellow]")
        raise typer.Exit(1)

    # Build menu entries once
    menu_entries = []
    for p in all_patches:
        name = p.analysis.suggested_name if p.analysis else f"Patch #{p.catalog_number}"
        track_count = len(p.tracks)
        total_duration = sum(t.duration_seconds for t in p.tracks)
        menu_entries.append(
            f"#{p.catalog_number:3d}  {name[:40]:<40}  {track_count} track(s), {total_duration:.1f}s"
        )

    # If patch specified on command line, start with it
    selected_patch = None
    if patch is not None:
        selected_patch = db.get_patch(patch)
        if not selected_patch:
            console.print(f"[red]Error:[/red] Patch #{patch} not found.")
            raise typer.Exit(1)

    while True:
        # Show patch selector if no patch selected
        if selected_patch is None:
            menu = TerminalMenu(
                menu_entries,
                title="  Select a patch to play (/ to search, ↑↓ to navigate, ESC to quit)\n",
                search_key="/",
                show_search_hint=True,
                **get_menu_style(),
            )

            selected_index = menu.show()

            if selected_index is None:
                # User cancelled
                break

            selected_patch = all_patches[selected_index]

        # Check if WAV files exist
        missing_tracks = [t for t in selected_patch.tracks if not Path(t.wav_path).exists()]
        if missing_tracks:
            console.print(f"[red]Error:[/red] Missing WAV files for patch #{selected_patch.catalog_number}")
            for t in missing_tracks:
                console.print(f"  - {t.wav_path}")
            selected_patch = None
            continue

        # Run the TUI player
        result = run_player(selected_patch, all_patches)

        if result == "back":
            # User wants to go back to selector
            selected_patch = None
            continue
        else:
            # User quit
            break


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
