"""Pydantic models for loopcat."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TrackAnalysis(BaseModel):
    """AI analysis for a single track within a patch."""

    suggested_name: str  # LLM-generated name (e.g., "Funky Bass Line")
    role: str  # Role in patch (e.g., "rhythm", "lead", "bass", "drums")
    instruments: list[str]  # Detected instruments
    description: str  # What this track contributes to the patch
    energy_level: int = Field(ge=1, le=10)


class PatchAnalysis(BaseModel):
    """AI analysis for a patch (all tracks analyzed together for context)."""

    raw_response: str  # Full LLM response text for reference/debugging
    suggested_name: str  # LLM-generated name for the patch
    description: str  # How the tracks work together
    mood: list[str]  # Overall mood/vibe (e.g., ["mellow", "groovy"])
    musical_style: str  # Genre/style (e.g., "funk", "ambient", "rock")
    energy_level: int = Field(ge=1, le=10)  # Overall energy
    tags: list[str]  # Searchable tags
    use_case: Optional[str] = None  # e.g., "practice backing track", "song idea"


class Track(BaseModel):
    """A single track within a patch."""

    id: str  # UUID
    patch_id: str  # Foreign key to Patch
    track_number: int  # 1, 2, or 3
    filename: str
    original_path: str  # Where it came from (e.g., /Volumes/BOSS_RC-300/...)
    wav_path: str  # Managed WAV location
    xxhash: str  # Full xxhash64 of WAV
    quick_hash: str  # Partial hash for fast dedup

    # File timestamps (from original WAV)
    file_created_at: datetime  # Birth time - when recorded
    file_modified_at: datetime  # Last modification time

    # Technical metadata (populated on import)
    duration_seconds: float
    sample_rate: int
    channels: int

    # Populated by 'convert' command
    mp3_path: Optional[str] = None

    # Populated by 'analyze' command (local analysis)
    bpm: Optional[float] = None
    detected_key: Optional[str] = None

    # Populated by 'analyze' command (Gemini analysis)
    analysis: Optional[TrackAnalysis] = None


class Patch(BaseModel):
    """A patch containing up to 3 tracks recorded together."""

    id: str  # UUID (internal primary key)
    catalog_number: int  # Auto-assigned sequential: 1, 2, 3, ... (user-facing)
    original_bank: int  # RC-300 bank at import time (1-99)
    source_device: str = "Boss RC-300"
    source_path: str  # Import source (e.g., "/Volumes/BOSS_RC-300")

    tracks: list[Track] = []  # 1-3 tracks

    # Catalog metadata
    created_at: datetime
    analyzed_at: Optional[datetime] = None
    user_tags: list[str] = []
    user_notes: str = ""
    rating: Optional[int] = Field(default=None, ge=1, le=5)  # 1-5 stars

    # Populated by 'analyze' command (Gemini analysis of all tracks together)
    analysis: Optional[PatchAnalysis] = None
