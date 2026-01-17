"""Convert WAV files to MP3 for Gemini analysis."""

import subprocess
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .database import Database


def check_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def convert_to_mp3(wav_path: Path, output_path: Path, bitrate: int = 192) -> Path:
    """Convert a WAV file to MP3.

    Args:
        wav_path: Path to the input WAV file.
        output_path: Path for the output MP3 file.
        bitrate: MP3 bitrate in kbps (default 192).

    Returns:
        Path to the created MP3 file.

    Raises:
        subprocess.CalledProcessError: If ffmpeg fails.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "ffmpeg",
            "-i", str(wav_path),
            "-codec:a", "libmp3lame",
            "-b:a", f"{bitrate}k",
            "-y",  # Overwrite output file
            "-loglevel", "error",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )

    return output_path


def convert_tracks(
    db: Database,
    mp3_dir: Path,
    console: Console,
    patch_number: Optional[int] = None,
    bitrate: int = 192,
) -> None:
    """Convert unconverted tracks to MP3.

    Args:
        db: Database instance.
        mp3_dir: Directory to store MP3 files.
        console: Rich console for output.
        patch_number: Optional specific patch to convert.
        bitrate: MP3 bitrate in kbps.
    """
    if not check_ffmpeg():
        console.print("[red]Error:[/red] ffmpeg not found. Install with: brew install ffmpeg")
        return

    mp3_dir.mkdir(parents=True, exist_ok=True)

    # Get tracks to convert
    if patch_number is not None:
        patch = db.get_patch(patch_number)
        if not patch:
            console.print(f"[red]Error:[/red] Patch #{patch_number} not found.")
            return
        tracks = [t for t in patch.tracks if t.mp3_path is None]
    else:
        tracks = db.get_unconverted_tracks()

    if not tracks:
        console.print("[yellow]No tracks need conversion.[/yellow]")
        return

    console.print(f"Converting [cyan]{len(tracks)}[/cyan] track(s)...")

    converted_count = 0
    error_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Converting...", total=len(tracks))

        for track in tracks:
            # Get the patch to find catalog number
            patch = db.get_patch_by_id(track.patch_id)
            if not patch:
                error_count += 1
                progress.advance(task)
                continue

            progress.update(
                task,
                description=f"#{patch.catalog_number} track {track.track_number}",
            )

            # Output path: {catalog_number:03d}_{track_number}.mp3
            output_filename = f"{patch.catalog_number:03d}_{track.track_number}.mp3"
            output_path = mp3_dir / output_filename

            try:
                convert_to_mp3(Path(track.wav_path), output_path, bitrate)
                db.update_track_mp3_path(track.id, str(output_path))
                converted_count += 1
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Error converting {track.filename}:[/red] {e.stderr.decode()}")
                error_count += 1

            progress.advance(task)

    console.print()
    console.print(f"[green]Converted:[/green] {converted_count} track(s)")
    if error_count:
        console.print(f"[red]Errors:[/red] {error_count}")
