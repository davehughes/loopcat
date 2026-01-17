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
