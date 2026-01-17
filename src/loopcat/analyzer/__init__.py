"""Audio analysis modules."""

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..database import Database
from .gemini import analyze_patch_with_gemini
from .local import detect_bpm, detect_key


def analyze_patches(
    db: Database,
    console: Console,
    patch_number: Optional[int] = None,
) -> None:
    """Analyze patches with Gemini and librosa.

    Args:
        db: Database instance.
        console: Rich console for output.
        patch_number: Optional specific patch to analyze.
    """
    # Get patches to analyze
    if patch_number is not None:
        patch = db.get_patch(patch_number)
        if not patch:
            console.print(f"[red]Error:[/red] Patch #{patch_number} not found.")
            return
        # Check if already analyzed
        if patch.analyzed_at:
            console.print(f"[yellow]Patch #{patch_number} already analyzed.[/yellow]")
            return
        # Check if all tracks have MP3s
        if any(t.mp3_path is None for t in patch.tracks):
            console.print(f"[red]Error:[/red] Patch #{patch_number} has unconverted tracks. Run 'loopcat convert' first.")
            return
        patches = [patch]
    else:
        patches = db.get_unanalyzed_patches()

    if not patches:
        console.print("[yellow]No patches need analysis.[/yellow]")
        return

    console.print(f"Analyzing [cyan]{len(patches)}[/cyan] patch(es)...")

    analyzed_count = 0
    error_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing...", total=len(patches))

        for patch in patches:
            progress.update(task, description=f"Patch #{patch.catalog_number}")

            try:
                # Run local analysis on each track
                for track in patch.tracks:
                    audio_path = Path(track.wav_path)

                    progress.update(
                        task,
                        description=f"#{patch.catalog_number} track {track.track_number} (BPM/key)",
                    )

                    bpm = detect_bpm(audio_path)
                    key = detect_key(audio_path)
                    db.update_track_local_analysis(track.id, bpm, key)

                # Run Gemini analysis on all tracks together
                progress.update(
                    task,
                    description=f"#{patch.catalog_number} (Gemini)",
                )

                mp3_paths = [(t.track_number, Path(t.mp3_path)) for t in patch.tracks]
                patch_analysis, track_analyses = analyze_patch_with_gemini(mp3_paths)

                # Update database
                db.update_patch_analysis(patch.id, patch_analysis)
                for track in patch.tracks:
                    if track.track_number in track_analyses:
                        db.update_track_analysis(track.id, track_analyses[track.track_number])

                analyzed_count += 1

            except Exception as e:
                console.print(f"[red]Error analyzing patch #{patch.catalog_number}:[/red] {e}")
                error_count += 1

            progress.advance(task)

    console.print()
    console.print(f"[green]Analyzed:[/green] {analyzed_count} patch(es)")
    if error_count:
        console.print(f"[red]Errors:[/red] {error_count}")
