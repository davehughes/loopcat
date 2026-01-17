"""Export format modules."""

import csv
import json
from pathlib import Path

from rich.console import Console

from loopcat.database import Database


def export_catalog(
    db: Database,
    format: str,
    output: Path,
    console: Console,
) -> None:
    """Export catalog to various formats.

    Args:
        db: Database instance.
        format: Export format (json, csv).
        output: Output file or directory path.
        console: Rich console for output.
    """
    patches = db.get_all_patches()

    if not patches:
        console.print("[yellow]No patches to export.[/yellow]")
        return

    if format == "json":
        export_json_sidecars(patches, output, console)
    elif format == "csv":
        export_csv(patches, output, console)
    else:
        console.print(f"[red]Error:[/red] Unknown format: {format}")
        console.print("Supported formats: json, csv")


def export_json_sidecars(patches: list, output_dir: Path, console: Console) -> None:
    """Export JSON sidecar files for each track.

    Creates a .json file alongside each MP3 with metadata.

    Args:
        patches: List of Patch objects.
        output_dir: Directory to write sidecar files.
        console: Rich console for output.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    exported_count = 0

    for patch in patches:
        # Export patch-level metadata
        patch_data = {
            "catalog_number": patch.catalog_number,
            "original_bank": patch.original_bank,
            "source_device": patch.source_device,
            "created_at": patch.created_at.isoformat(),
            "analyzed_at": patch.analyzed_at.isoformat() if patch.analyzed_at else None,
        }

        if patch.analysis:
            patch_data["analysis"] = {
                "suggested_name": patch.analysis.suggested_name,
                "description": patch.analysis.description,
                "mood": patch.analysis.mood,
                "musical_style": patch.analysis.musical_style,
                "energy_level": patch.analysis.energy_level,
                "tags": patch.analysis.tags,
                "use_case": patch.analysis.use_case,
            }

        patch_data["tracks"] = []

        for track in patch.tracks:
            track_data = {
                "track_number": track.track_number,
                "filename": track.filename,
                "duration_seconds": track.duration_seconds,
                "sample_rate": track.sample_rate,
                "channels": track.channels,
                "bpm": track.bpm,
                "detected_key": track.detected_key,
            }

            if track.analysis:
                track_data["analysis"] = {
                    "suggested_name": track.analysis.suggested_name,
                    "role": track.analysis.role,
                    "instruments": track.analysis.instruments,
                    "description": track.analysis.description,
                    "energy_level": track.analysis.energy_level,
                }

            patch_data["tracks"].append(track_data)

            # Also create a per-track sidecar if MP3 exists
            if track.mp3_path:
                mp3_name = Path(track.mp3_path).stem
                sidecar_path = output_dir / f"{mp3_name}.json"

                sidecar_data = {
                    "patch": {
                        "catalog_number": patch.catalog_number,
                        "suggested_name": patch.analysis.suggested_name if patch.analysis else None,
                        "mood": patch.analysis.mood if patch.analysis else [],
                        "musical_style": patch.analysis.musical_style if patch.analysis else None,
                        "tags": patch.analysis.tags if patch.analysis else [],
                    },
                    "track": track_data,
                }

                with open(sidecar_path, "w") as f:
                    json.dump(sidecar_data, f, indent=2)
                exported_count += 1

        # Write patch-level JSON
        patch_path = output_dir / f"patch_{patch.catalog_number:03d}.json"
        with open(patch_path, "w") as f:
            json.dump(patch_data, f, indent=2)

    console.print(f"[green]Exported:[/green] {exported_count} track sidecar(s) + {len(patches)} patch file(s)")
    console.print(f"Output directory: {output_dir}")


def export_csv(patches: list, output_path: Path, console: Console) -> None:
    """Export catalog to a CSV file.

    Args:
        patches: List of Patch objects.
        output_path: Path to the output CSV file.
        console: Rich console for output.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for patch in patches:
        for track in patch.tracks:
            row = {
                "catalog_number": patch.catalog_number,
                "original_bank": patch.original_bank,
                "track_number": track.track_number,
                "filename": track.filename,
                "duration_seconds": f"{track.duration_seconds:.2f}",
                "bpm": f"{track.bpm:.1f}" if track.bpm else "",
                "detected_key": track.detected_key or "",
                "patch_name": patch.analysis.suggested_name if patch.analysis else "",
                "patch_mood": ", ".join(patch.analysis.mood) if patch.analysis else "",
                "patch_style": patch.analysis.musical_style if patch.analysis else "",
                "patch_tags": ", ".join(patch.analysis.tags) if patch.analysis else "",
                "track_name": track.analysis.suggested_name if track.analysis else "",
                "track_role": track.analysis.role if track.analysis else "",
                "track_instruments": ", ".join(track.analysis.instruments) if track.analysis else "",
                "wav_path": track.wav_path,
                "mp3_path": track.mp3_path or "",
            }
            rows.append(row)

    if not rows:
        console.print("[yellow]No tracks to export.[/yellow]")
        return

    fieldnames = list(rows[0].keys())

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    console.print(f"[green]Exported:[/green] {len(rows)} track(s) to CSV")
    console.print(f"Output file: {output_path}")
