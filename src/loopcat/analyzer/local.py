"""Local audio analysis using librosa."""

from pathlib import Path
from typing import Optional

import librosa
import numpy as np


def detect_bpm(audio_path: Path) -> Optional[float]:
    """Detect BPM of an audio file.

    Args:
        audio_path: Path to the audio file (WAV or MP3).

    Returns:
        Detected BPM, or None if detection fails.
    """
    try:
        y, sr = librosa.load(audio_path, sr=None)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        # tempo can be an array, get scalar value
        if isinstance(tempo, np.ndarray):
            tempo = float(tempo[0]) if len(tempo) > 0 else None
        return float(tempo) if tempo else None
    except Exception:
        return None


def detect_key(audio_path: Path) -> Optional[str]:
    """Detect musical key of an audio file.

    Uses chroma features to estimate the most likely key.

    Args:
        audio_path: Path to the audio file (WAV or MP3).

    Returns:
        Detected key (e.g., "C major", "A minor"), or None if detection fails.
    """
    try:
        y, sr = librosa.load(audio_path, sr=None)

        # Compute chroma features
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

        # Average chroma across time
        chroma_avg = np.mean(chroma, axis=1)

        # Key names
        key_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

        # Major and minor profiles (Krumhansl-Schmuckler)
        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

        # Normalize profiles
        major_profile = major_profile / np.linalg.norm(major_profile)
        minor_profile = minor_profile / np.linalg.norm(minor_profile)
        chroma_norm = chroma_avg / np.linalg.norm(chroma_avg)

        # Correlate with all rotations of major/minor profiles
        best_corr = -1
        best_key = "C major"

        for i in range(12):
            # Rotate profiles
            maj_rot = np.roll(major_profile, i)
            min_rot = np.roll(minor_profile, i)

            # Compute correlations
            maj_corr = np.corrcoef(chroma_norm, maj_rot)[0, 1]
            min_corr = np.corrcoef(chroma_norm, min_rot)[0, 1]

            if maj_corr > best_corr:
                best_corr = maj_corr
                best_key = f"{key_names[i]} major"

            if min_corr > best_corr:
                best_corr = min_corr
                best_key = f"{key_names[i]} minor"

        return best_key
    except Exception:
        return None
