"""Export format modules."""

import csv
import json
import os
import re
from pathlib import Path

from rich.console import Console

from loopcat.database import Database


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename.

    Args:
        name: The string to sanitize.

    Returns:
        A filesystem-safe version of the name.
    """
    # Replace problematic characters with underscores
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Replace multiple spaces/underscores with single underscore
    sanitized = re.sub(r'[\s_]+', '_', sanitized)
    # Remove leading/trailing underscores and spaces
    sanitized = sanitized.strip('_ ')
    # Limit length
    if len(sanitized) > 50:
        sanitized = sanitized[:50].rstrip('_')
    return sanitized or "unnamed"


def export_catalog(
    db: Database,
    format: str,
    output: Path,
    console: Console,
    use_wav: bool = False,
) -> None:
    """Export catalog to various formats.

    Args:
        db: Database instance.
        format: Export format (json, csv, folder).
        output: Output file or directory path.
        console: Rich console for output.
        use_wav: For folder export, use WAV files instead of MP3.
    """
    patches = db.get_all_patches()

    if not patches:
        console.print("[yellow]No patches to export.[/yellow]")
        return

    if format == "json":
        export_json_sidecars(patches, output, console)
    elif format == "csv":
        export_csv(patches, output, console)
    elif format == "folder":
        export_folder_symlinks(patches, output, console, use_wav=use_wav)
    else:
        console.print(f"[red]Error:[/red] Unknown format: {format}")
        console.print("Supported formats: json, csv, folder")


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


def export_folder_symlinks(
    patches: list,
    output_dir: Path,
    console: Console,
    use_wav: bool = False,
) -> None:
    """Export as organized folder structure with symlinks to audio files.

    Creates: {output_dir}/loopcat/{patch_idx}-{patch_name}/{track_idx}-{track_name}.{ext}

    Args:
        patches: List of Patch objects.
        output_dir: Base directory for export.
        console: Rich console for output.
        use_wav: If True, link to WAV files; otherwise link to MP3 files.
    """
    loopcat_dir = output_dir / "loopcat"

    # Remove existing loopcat dir if it exists (to clean up stale symlinks)
    if loopcat_dir.exists():
        import shutil
        shutil.rmtree(loopcat_dir)

    loopcat_dir.mkdir(parents=True, exist_ok=True)

    exported_count = 0
    skipped_count = 0

    for patch in patches:
        # Build patch folder name: {idx}-{name}
        patch_name = patch.analysis.suggested_name if patch.analysis else f"Patch {patch.catalog_number}"
        patch_folder_name = f"{patch.catalog_number:03d}-{sanitize_filename(patch_name)}"
        patch_dir = loopcat_dir / patch_folder_name
        patch_dir.mkdir(parents=True, exist_ok=True)

        for track in patch.tracks:
            # Determine source file
            if use_wav:
                source_path = Path(track.wav_path) if track.wav_path else None
                ext = "wav"
            else:
                source_path = Path(track.mp3_path) if track.mp3_path else None
                ext = "mp3"
                # Fall back to WAV if no MP3
                if not source_path or not source_path.exists():
                    source_path = Path(track.wav_path) if track.wav_path else None
                    ext = "wav"

            if not source_path or not source_path.exists():
                skipped_count += 1
                continue

            # Build track filename: {idx}-{name}.{ext}
            track_name = track.analysis.suggested_name if track.analysis else f"Track {track.track_number}"
            track_filename = f"{track.track_number}-{sanitize_filename(track_name)}.{ext}"
            link_path = patch_dir / track_filename

            # Create symlink
            try:
                link_path.symlink_to(source_path.resolve())
                exported_count += 1
            except OSError as e:
                console.print(f"[yellow]Warning:[/yellow] Could not create symlink for {track_filename}: {e}")
                skipped_count += 1

        # Also write a metadata JSON in each patch folder
        metadata_path = patch_dir / "_metadata.json"
        metadata = {
            "catalog_number": patch.catalog_number,
            "original_bank": patch.original_bank,
        }
        if patch.analysis:
            metadata.update({
                "name": patch.analysis.suggested_name,
                "description": patch.analysis.description,
                "style": patch.analysis.musical_style,
                "mood": patch.analysis.mood,
                "tags": patch.analysis.tags,
                "energy": patch.analysis.energy_level,
            })
        metadata["tracks"] = []
        for track in patch.tracks:
            track_meta = {
                "track_number": track.track_number,
                "duration_seconds": round(track.duration_seconds, 2),
                "bpm": round(track.bpm, 1) if track.bpm else None,
                "key": track.detected_key,
            }
            if track.analysis:
                track_meta.update({
                    "name": track.analysis.suggested_name,
                    "role": track.analysis.role,
                    "instruments": track.analysis.instruments,
                })
            metadata["tracks"].append(track_meta)

        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

    console.print(f"[green]Exported:[/green] {exported_count} track symlink(s) in {len(patches)} patch folder(s)")
    if skipped_count:
        console.print(f"[yellow]Skipped:[/yellow] {skipped_count} track(s) (missing audio files)")
    console.print(f"Output directory: {loopcat_dir}")
