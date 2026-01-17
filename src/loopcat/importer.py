"""Import WAV files from RC-300 or backup folders."""

import re
import shutil
from datetime import datetime
from pathlib import Path

import soundfile as sf
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from loopcat.database import Database
from loopcat.hasher import compute_full_hash, compute_quick_hash

# RC-300 file pattern: {bank}_{track}/{bank}_{track}.WAV
# bank: 001-099 (3-digit zero-padded)
# track: 1, 2, or 3
RC300_PATTERN = re.compile(r"(\d{3})_(\d)/\1_\2\.WAV$", re.IGNORECASE)


def discover_wav_files(source: Path) -> list[tuple[Path, int, int]]:
    """Discover WAV files matching RC-300 pattern.

    Args:
        source: Root directory to search.

    Returns:
        List of (file_path, bank_number, track_number) tuples.
    """
    results = []

    # Look for ROLAND/WAVE subdirectory (standard RC-300 structure)
    roland_wave = source / "ROLAND" / "WAVE"
    search_dir = roland_wave if roland_wave.exists() else source

    for wav_file in search_dir.rglob("*.WAV"):
        # Try to match the RC-300 pattern
        rel_path = str(wav_file.relative_to(search_dir))
        match = RC300_PATTERN.search(rel_path)
        if match:
            bank = int(match.group(1))
            track = int(match.group(2))
            results.append((wav_file, bank, track))

    # Sort by bank, then track
    results.sort(key=lambda x: (x[1], x[2]))
    return results


def get_file_timestamps(file_path: Path) -> tuple[datetime, datetime]:
    """Get file creation and modification timestamps.

    Args:
        file_path: Path to the file.

    Returns:
        Tuple of (created_at, modified_at) datetimes.
    """
    stat = file_path.stat()

    # Try to get birth time (creation time), fall back to mtime
    try:
        created_at = datetime.fromtimestamp(stat.st_birthtime)
    except AttributeError:
        # st_birthtime not available on all platforms
        created_at = datetime.fromtimestamp(stat.st_mtime)

    modified_at = datetime.fromtimestamp(stat.st_mtime)
    return created_at, modified_at


def get_audio_metadata(file_path: Path) -> tuple[float, int, int]:
    """Extract audio metadata from a WAV file.

    Args:
        file_path: Path to the WAV file.

    Returns:
        Tuple of (duration_seconds, sample_rate, channels).
    """
    info = sf.info(file_path)
    return info.duration, info.samplerate, info.channels


def import_from_source(
    source: Path,
    db: Database,
    wav_dir: Path,
    console: Console,
) -> None:
    """Import WAV files from a source directory.

    Args:
        source: Source directory containing RC-300 WAV files.
        db: Database instance.
        wav_dir: Directory to store managed WAV files.
        console: Rich console for output.
    """
    wav_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Scanning[/bold] {source}")
    discovered = discover_wav_files(source)

    if not discovered:
        console.print("[yellow]No RC-300 WAV files found.[/yellow]")
        return

    console.print(f"Found [cyan]{len(discovered)}[/cyan] WAV file(s)")

    # Group by bank for patch creation
    banks: dict[int, list[tuple[Path, int]]] = {}
    for file_path, bank, track in discovered:
        if bank not in banks:
            banks[bank] = []
        banks[bank].append((file_path, track))

    imported_count = 0
    skipped_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Importing...", total=len(banks))

        for bank, tracks in banks.items():
            progress.update(task, description=f"Bank {bank:03d}")

            # Check if any tracks are new (not already in DB)
            new_tracks = []
            for file_path, track_num in tracks:
                quick_hash = compute_quick_hash(file_path)
                if not db.quick_hash_exists(quick_hash):
                    new_tracks.append((file_path, track_num, quick_hash))

            if not new_tracks:
                skipped_count += len(tracks)
                progress.advance(task)
                continue

            # Create patch for this bank
            patch = db.create_patch(
                original_bank=bank,
                source_path=str(source),
            )

            # Import each new track
            for file_path, track_num, quick_hash in new_tracks:
                # Copy WAV to managed storage
                dest_filename = f"{patch.catalog_number:03d}_{track_num}.wav"
                dest_path = wav_dir / dest_filename
                shutil.copy2(file_path, dest_path)

                # Compute full hash of copied file
                full_hash = compute_full_hash(dest_path)

                # Check for duplicate by full hash
                if db.full_hash_exists(full_hash):
                    # Remove the copy and skip
                    dest_path.unlink()
                    skipped_count += 1
                    continue

                # Get file timestamps from original
                created_at, modified_at = get_file_timestamps(file_path)

                # Get audio metadata
                duration, sample_rate, channels = get_audio_metadata(dest_path)

                # Create track record
                db.create_track(
                    patch_id=patch.id,
                    track_number=track_num,
                    filename=dest_filename,
                    original_path=str(file_path),
                    wav_path=str(dest_path),
                    xxhash=full_hash,
                    quick_hash=quick_hash,
                    file_created_at=created_at,
                    file_modified_at=modified_at,
                    duration_seconds=duration,
                    sample_rate=sample_rate,
                    channels=channels,
                )
                imported_count += 1

            progress.advance(task)

    console.print()
    console.print(f"[green]Imported:[/green] {imported_count} track(s)")
    if skipped_count:
        console.print(f"[yellow]Skipped:[/yellow] {skipped_count} duplicate(s)")
