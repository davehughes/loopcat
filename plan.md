# loopcat

A tool to catalog WAV files from a Boss RC-300 looper pedal using AI-powered audio analysis, with export capabilities for Bitwig Studio and other DAWs.

## Goals

1. **Manual import**: CLI-driven import from RC-300 USB or local folders
2. **AI-powered analysis**: Use Gemini to analyze MP3s and generate metadata (mood, BPM, key, instruments, tags)
3. **Searchable catalog**: Store analysis results in a queryable SQLite database
4. **DAW integration**: Export metadata in formats compatible with Bitwig, Ableton, etc.

---

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   RC-300 USB    │────▶│   import         │────▶│  Managed Storage│
│  (WAV files)    │     │  (dedup + copy)  │     │  (WAV + DB)     │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                         │
                        ┌────────────────────────────────┼────────────────────────────────┐
                        │                                │                                │
                        ▼                                ▼                                ▼
               ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
               │   convert       │              │   analyze       │              │   export        │
               │  (WAV → MP3)    │              │  (Gemini + BPM) │              │  (Bitwig, CSV)  │
               └─────────────────┘              └─────────────────┘              └─────────────────┘
```

**Pipeline stages:**
1. `import` - Copy WAVs to managed storage, compute hashes, write DB records
2. `convert` - Generate MP3s from managed WAVs
3. `analyze` - Run Gemini analysis (requires MP3) + librosa BPM/key detection
4. `export` - Export to DAW formats

---

## RC-300 File Structure

```
ROLAND/WAVE/{bank}_{track}/{bank}_{track}.WAV
- bank: 001-099 (3-digit zero-padded)
- track: 1, 2, or 3
- Example: 040_2/040_2.WAV = Bank 40, Track 2
```

Current data: 159 WAV files across 96 patches (16-bit stereo 44.1kHz PCM)

---

## Components

### 1. Fast Duplicate Detection (for slow USB)

To avoid re-processing files on the slow RC-300 USB storage, use a **partial hash** strategy:

1. Read first 64KB of each WAV file on USB
2. Compute xxhash of (first 64KB + file size)
3. Check if this "quick hash" exists in DB
4. Only copy files with unknown quick hashes

After copying to local storage, compute full xxhash for permanent dedup.

```python
def compute_quick_hash(file_path: Path) -> str:
    """Fast hash using first 64KB + file size."""
    size = file_path.stat().st_size
    h = xxhash.xxh64()
    h.update(size.to_bytes(8, 'little'))
    with open(file_path, "rb") as f:
        h.update(f.read(65536))  # First 64KB only
    return h.hexdigest()
```

### 2. Import Pipeline

1. Scan source directory for WAV files matching RC-300 pattern
2. Compute quick hash for each, skip files already in DB
3. Copy new WAVs to managed storage (`~/.loopcat/wav/`)
4. Compute full xxhash of copied WAV
5. Extract audio metadata (duration, sample rate, channels) via soundfile
6. Insert patch/track records into DB

**Result**: WAV files under management, DB records created, ready for convert/analyze/export

### 3. Audio Analyzer

**Primary analysis (Gemini)** - analyzes all tracks in a patch together for context:
- Upload all MP3s for a patch in a single request
- **Patch-level**: suggested name, overall description, mood, musical style, energy, tags, use case
- **Track-level**: suggested name, role in patch, instruments, description, energy

**Secondary analysis (local)**:
- BPM detection via `librosa` (per track)
- Key detection via `librosa` (per track)

```python
# Key dependencies
langchain-google-genai>=1.0.0
librosa>=0.10.0
soundfile>=0.12.0
```

### 4. Data Models

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class TrackAnalysis(BaseModel):
    """AI analysis for a single track within a patch."""
    suggested_name: str              # LLM-generated name (e.g., "Funky Bass Line")
    role: str                        # Role in patch (e.g., "rhythm", "lead", "bass", "drums")
    instruments: list[str]           # Detected instruments
    description: str                 # What this track contributes to the patch
    energy_level: int = Field(ge=1, le=10)

class PatchAnalysis(BaseModel):
    """AI analysis for a patch (all tracks analyzed together for context)."""
    raw_response: str                # Full LLM response text for reference/debugging
    suggested_name: str              # LLM-generated name for the patch
    description: str                 # How the tracks work together
    mood: list[str]                  # Overall mood/vibe (e.g., ["mellow", "groovy"])
    musical_style: str               # Genre/style (e.g., "funk", "ambient", "rock")
    energy_level: int = Field(ge=1, le=10)  # Overall energy
    tags: list[str]                  # Searchable tags
    use_case: Optional[str] = None   # e.g., "practice backing track", "song idea"

class Track(BaseModel):
    """A single track within a patch."""
    track_number: int  # 1, 2, or 3
    filename: str
    original_path: str  # Where it came from (e.g., /Volumes/BOSS_RC-300/...)
    wav_path: str       # Managed WAV location
    xxhash: str         # Full xxhash64 of WAV
    quick_hash: str     # Partial hash for fast dedup

    # File timestamps (from original WAV)
    file_created_at: datetime   # Birth time - when recorded
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
    id: str                        # UUID (internal primary key)
    catalog_number: int            # Auto-assigned sequential: 1, 2, 3, ... (user-facing)
    original_bank: int             # RC-300 bank at import time (1-99)
    source_device: str = "Boss RC-300"
    source_path: str               # Import source (e.g., "/Volumes/BOSS_RC-300")

    tracks: list[Track]  # 1-3 tracks

    # Catalog metadata
    created_at: datetime
    analyzed_at: Optional[datetime] = None
    user_tags: list[str] = []
    user_notes: str = ""
    rating: Optional[int] = None  # 1-5 stars

    # Populated by 'analyze' command (Gemini analysis of all tracks together)
    analysis: Optional[PatchAnalysis] = None
```

### 5. Catalog Storage

**SQLite database** for queryable storage with full-text search.

**Schema**:
```sql
CREATE TABLE patches (
    id TEXT PRIMARY KEY,
    catalog_number INTEGER UNIQUE NOT NULL,  -- Auto-assigned: 1, 2, 3, ... (user-facing)
    original_bank INTEGER NOT NULL,          -- RC-300 bank at import time (1-99)
    source_device TEXT DEFAULT 'Boss RC-300',
    source_path TEXT,                        -- Import source path
    user_tags TEXT,  -- JSON array
    user_notes TEXT,
    rating INTEGER,
    created_at TEXT,
    analyzed_at TEXT,

    -- Populated by 'analyze' command (PatchAnalysis from Gemini)
    analysis_raw_response TEXT,     -- Full LLM response for reference
    suggested_name TEXT,            -- LLM-generated patch name
    description TEXT,               -- How tracks work together
    mood TEXT,                      -- JSON array
    musical_style TEXT,             -- Genre/style
    energy_level INTEGER,           -- 1-10
    tags TEXT,                      -- JSON array
    use_case TEXT                   -- e.g., "practice backing track"
);

CREATE TABLE tracks (
    id TEXT PRIMARY KEY,
    patch_id TEXT NOT NULL REFERENCES patches(id),
    track_number INTEGER NOT NULL,  -- 1, 2, or 3
    filename TEXT NOT NULL,
    original_path TEXT,             -- Source location
    wav_path TEXT NOT NULL,         -- Managed WAV location
    xxhash TEXT UNIQUE,             -- Full hash of WAV
    quick_hash TEXT UNIQUE,         -- Partial hash for fast dedup

    file_created_at TEXT,           -- Birth time from original WAV
    file_modified_at TEXT,          -- Modification time from original WAV

    -- Technical metadata (populated on import)
    duration_seconds REAL,
    sample_rate INTEGER,
    channels INTEGER,

    -- Populated by 'convert' command
    mp3_path TEXT,

    -- Populated by 'analyze' command (local librosa analysis)
    bpm REAL,
    detected_key TEXT,

    -- Populated by 'analyze' command (TrackAnalysis from Gemini)
    suggested_name TEXT,            -- LLM-generated track name
    role TEXT,                      -- Role in patch (rhythm, lead, bass, drums)
    instruments TEXT,               -- JSON array
    description TEXT,               -- What this track contributes
    energy_level INTEGER,           -- 1-10

    UNIQUE(patch_id, track_number)
);

CREATE INDEX idx_tracks_xxhash ON tracks(xxhash);
CREATE INDEX idx_tracks_quick_hash ON tracks(quick_hash);
CREATE INDEX idx_patches_catalog_number ON patches(catalog_number);
CREATE INDEX idx_patches_original_bank ON patches(original_bank);

-- Full-text search across patches and tracks
CREATE VIRTUAL TABLE patches_fts USING fts5(
    suggested_name, description, tags, mood,
    content='patches',
    content_rowid='rowid'
);

CREATE VIRTUAL TABLE tracks_fts USING fts5(
    suggested_name, description, instruments, role,
    content='tracks',
    content_rowid='rowid'
);
```

### 6. MP3 Conversion

**Tool**: `ffmpeg`

**Settings**:
- Bitrate: 192 kbps
- Output: `~/.loopcat/mp3/{patch_number:03d}_{track_number}.mp3`

```python
def convert_to_mp3(wav_path: Path, output_path: Path, bitrate: int = 192) -> Path:
    subprocess.run([
        "ffmpeg", "-i", str(wav_path),
        "-codec:a", "libmp3lame",
        "-b:a", f"{bitrate}k",
        "-y",
        str(output_path)
    ], check=True, capture_output=True)
    return output_path
```

### 7. DAW Export Formats

#### Bitwig Studio
- Generate folder structure with tagged subfolders
- Create `.bwclip` files with tempo/key metadata

#### Generic DAW Support
- **Metadata sidecar files**: `loop.mp3.json`
- **CSV export**: For import into sample managers
- **Folder organization**: Auto-organize by mood/key

```python
class ExportFormat(Enum):
    JSON_SIDECAR = "json"
    CSV = "csv"
    BITWIG_FOLDER = "bitwig"
```

---

## CLI Interface

**ASCII Logo** (shown on `--version` and errors):
```
    ∞╱╲_╱╲∞
    (=◕ᴥ◕=)  LOOPCAT
    ╰─────╯  ═══════○
```

**Commands**:
```bash
# 1. IMPORT - Copy WAVs to managed storage, create DB records
loopcat import                                    # Default: /Volumes/BOSS_RC-300
loopcat import ~/Documents/BOSS_RC-300/2026-01-17 # Or specify a path

# 2. CONVERT - Generate MP3s from managed WAVs
loopcat convert                # Convert all unconverted tracks
loopcat convert --patch 42     # Convert specific patch (by catalog number)

# 3. ANALYZE - Run Gemini + librosa analysis (requires MP3)
loopcat analyze                # Analyze all unanalyzed patches
loopcat analyze --patch 42     # Analyze specific patch (by catalog number)

# 4. EXPORT - Export to DAW formats
loopcat export --format bitwig --output ./bitwig-library
loopcat export --format csv --output catalog.csv

# UTILITY COMMANDS
loopcat list                   # List all patches/tracks
loopcat list --patch 42        # Show specific patch (by catalog number)
loopcat list --bank 40         # Filter by original RC-300 bank
loopcat search "funky guitar"  # Full-text search
loopcat search --bpm-range 90-110 --key "A minor"
```

---

## Implementation Plan

### Phase 1: Core Setup
1. Initialize project with `uv`
2. Create Pydantic models (`Patch`, `Track`, `TrackAnalysis`, `PatchAnalysis`)
3. Implement xxhash (full and quick/partial)
4. Create SQLite schema and database layer
5. CLI scaffolding with Typer

### Phase 2: Import Command
1. Parse RC-300 folder structure to discover patches/tracks
2. Compute quick hash on source, skip files already in DB
3. Copy new WAVs to managed storage (`~/.loopcat/wav/`)
4. Compute full xxhash of copied WAV
5. Extract audio metadata (duration, sample rate, channels) via soundfile
6. Insert patch/track records into DB

### Phase 3: Convert Command
1. Find tracks with no mp3_path
2. Convert WAV to MP3 using ffmpeg
3. Store MP3 in `~/.loopcat/mp3/`
4. Update track record with mp3_path

### Phase 4: Analyze Command
1. Find patches where all tracks have mp3_path but patch lacks analysis
2. Implement Gemini audio analysis:
   - Upload all MP3s for a patch together (provides context)
   - Get structured response with PatchAnalysis + TrackAnalysis for each track
   - Store raw_response for reference/debugging
3. Add librosa-based BPM/key detection (per track)
4. Update patch and track records with analysis results

### Phase 5: Search & Export
1. Full-text search across tracks
2. Query by patch, BPM range, key, etc.
3. JSON sidecar export
4. CSV export

---

## Configuration

```yaml
# config.yaml
storage:
  database_path: ~/.loopcat/catalog.db
  wav_storage: ~/.loopcat/wav      # Managed WAV files
  mp3_storage: ~/.loopcat/mp3      # Converted MP3 files

import:
  default_source: /Volumes/BOSS_RC-300  # Default for 'loopcat import'

analysis:
  gemini_model: "gemini-2.0-flash"
  local_bpm_detection: true
  local_key_detection: true

export:
  default_format: json_sidecar
  bitwig_library_path: ~/Documents/Bitwig Studio/Library
```

---

## Project Structure

```
loopcat/
├── pyproject.toml
├── src/loopcat/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                  # Typer CLI
│   ├── models.py               # Patch, Track, TrackAnalysis, PatchAnalysis
│   ├── database.py             # SQLite operations
│   ├── importer.py             # RC-300 folder parsing, import logic
│   ├── hasher.py               # xxhash (full and quick)
│   ├── converter.py            # WAV to MP3 conversion
│   ├── analyzer/
│   │   ├── __init__.py
│   │   ├── gemini.py           # Gemini analysis (from MP3)
│   │   └── local.py            # librosa BPM/key
│   └── export/
│       ├── __init__.py
│       └── sidecar.py          # JSON/CSV export
└── tests/
    └── ...
```

---

## Dependencies

```toml
[project]
dependencies = [
    "langchain-google-genai>=1.0.0",
    "langchain-core>=0.2.0",
    "pydantic>=2.0.0",
    "librosa>=0.10.0",
    "soundfile>=0.12.0",
    "typer>=0.9.0",
    "rich>=13.0.0",
    "pyyaml>=6.0.0",
    "xxhash>=3.0.0",
]
```

**External dependency**: `ffmpeg` must be installed (`brew install ffmpeg`)

---

## Decisions Made

1. **No file watcher** - CLI-driven import only
2. **Separate pipeline stages** - import → convert → analyze → export (each independent)
3. **WAVs under management** - Original WAVs copied to `~/.loopcat/wav/` on import
4. **MP3 for Gemini** - Convert command creates MP3s, analyze uses them for upload
5. **Partial hash for USB** - Read first 64KB + file size for quick duplicate detection on slow USB
6. **No genre/sub_genres** - Analysis focuses on mood, instruments, tags
7. **Patch terminology** - RC-300 "banks" renamed to "patches" in our model
8. **Patch-level analysis** - All tracks in a patch analyzed together so LLM understands context (e.g., track roles, how they complement each other)
9. **LLM-generated names** - Gemini suggests names for patches and individual tracks
10. **Default import source** - `/Volumes/BOSS_RC-300` so `loopcat import` works without arguments when pedal is connected
11. **Catalog numbers** - Auto-assigned sequential IDs (1, 2, 3, ...) for user-facing patch references; original RC-300 bank (1-99) preserved as `original_bank` metadata

---

## Future Enhancements

- **Similarity search**: Find loops similar to a given loop (using audio embeddings)
- **TUI browser**: Interactive catalog browsing with `textual`
- **Batch re-analysis**: Re-analyze all tracks with improved prompts
- **Waveform previews**: Generate thumbnail images for visual browsing
