# loopcat

```
    ∞╱╲_╱╲∞
    (=◕ᴥ◕=)  LOOPCAT
    ╰─────╯  ═══════○
```

A CLI tool to catalog WAV files from a Boss RC-300 looper pedal with AI-powered audio analysis.

## Features

- **Import** loops from RC-300 USB or backup folders with automatic deduplication
- **Analyze** patches using Gemini AI (mood, style, instruments) and librosa (BPM, key)
- **Search** your catalog with full-text search
- **Export** metadata to JSON or CSV for use in DAWs and sample managers

## Screencaps
<img width="860" height="417" alt="image" src="https://github.com/user-attachments/assets/8b0ee3ec-b11a-4349-b3a3-ef21c778d22a" />
<img width="862" height="411" alt="image" src="https://github.com/user-attachments/assets/dd9b219e-e043-4ca2-a34b-13eebafe4ced" />
<img width="858" height="413" alt="image" src="https://github.com/user-attachments/assets/b339054e-ca85-449c-aaa4-ab4caae83d46" />


## Installation

```bash
# Clone and install with uv
git clone <repo-url>
cd loopcat
uv sync

# Install ffmpeg (required for MP3 conversion)
brew install ffmpeg

# Set up Gemini API key (required for AI analysis)
loopcat auth
```

## Quick Start

```bash
# 1. Connect your RC-300 via USB, then import
loopcat import

# 2. Convert WAVs to MP3 (needed for Gemini analysis)
loopcat convert

# 3. Analyze with AI
loopcat analyze

# 4. Browse your catalog
loopcat list
loopcat search "funky guitar"

# 5. Play with TUI (RC-300 style controls)
loopcat                   # Launch TUI (default command)
loopcat play 42           # Play specific patch directly
```

## Commands

### `loopcat import [SOURCE]`

Import WAV files from an RC-300 or backup folder.

```bash
loopcat import                              # Default: /Volumes/BOSS_RC-300
loopcat import ~/Backups/RC-300/2026-01-17  # From a backup folder
```

- Parses RC-300 folder structure (`ROLAND/WAVE/{bank}_{track}/`)
- Fast duplicate detection using partial hashing (first 64KB)
- Copies WAVs to managed storage (`~/.loopcat/wav/`)
- Extracts duration, sample rate, and channel info

### `loopcat convert`

Convert WAV files to MP3 for Gemini analysis.

```bash
loopcat convert              # Convert all unconverted tracks
loopcat convert --patch 42   # Convert specific patch
```

- Requires `ffmpeg` to be installed
- Outputs to `~/.loopcat/mp3/` at 192 kbps

### `loopcat analyze`

Analyze patches with Gemini AI and librosa.

```bash
loopcat analyze              # Analyze all unanalyzed patches
loopcat analyze --patch 42   # Analyze specific patch
```

**Gemini analysis** (all tracks uploaded together for context):
- Patch: suggested name, description, mood, musical style, energy level, tags, use case
- Tracks: suggested name, role (rhythm/lead/bass/drums), instruments, description

**Local analysis** (per track):
- BPM detection via librosa
- Key detection via librosa

### `loopcat list`

List patches and tracks in the catalog.

```bash
loopcat list                 # List all patches
loopcat list --patch 42      # Show specific patch (by catalog number)
loopcat list --bank 40       # Filter by original RC-300 bank
```

### `loopcat search <QUERY>`

Full-text search across patches and tracks.

```bash
loopcat search "funky guitar"
loopcat search "ambient pad"
```

Searches patch names, descriptions, moods, tags, track names, roles, and instruments.

### `loopcat play [PATCH]`

Launch the TUI player with RC-300 style controls. This is the default command when running `loopcat` with no arguments.

```bash
loopcat                   # Shows patch picker (default command)
loopcat play              # Same as above
loopcat play 42           # Play specific patch directly
```

**Patch Picker Controls:**
| Key | Action |
|-----|--------|
| `j` `↓` `C-j` | Move down |
| `k` `↑` `C-k` | Move up |
| `Enter` | Play selected patch |
| `t` | Theme picker |
| `Esc` | Quit |

**Player Controls:**
| Key | Action |
|-----|--------|
| `Space` | Start/stop all tracks |
| `1` `2` `3` | Toggle individual tracks |
| `h` `←` | Previous patch |
| `l` `→` | Next patch |
| `t` | Theme picker |
| `q` `,` | Back to patch picker |
| `Esc` | Quit |

**Navigation flow:**
```
loopcat
    │
    ▼
┌─────────────────┐
│  Patch Picker   │◄────────┐
│ (type to filter)│         │
└────────┬────────┘         │
         │ Enter            │ q or ,
         ▼                  │
┌─────────────────┐         │
│   TUI Player    │─────────┘
│ (auto-plays)    │
└────────┬────────┘
         │ Esc
         ▼
       Exit
```

### `loopcat export`

Export catalog metadata to various formats.

```bash
loopcat export --format json --output ./metadata   # JSON sidecars
loopcat export --format csv --output catalog.csv   # CSV spreadsheet
```

**JSON format**: Creates per-patch and per-track sidecar files with full metadata.

**CSV format**: Flat export with all track metadata, suitable for spreadsheets or sample managers.

## Data Storage

Follows XDG Base Directory standard:

```
~/.config/loopcat/
└── config.yaml   # API keys and settings

~/.local/share/loopcat/
├── catalog.db    # SQLite database with full-text search
├── wav/          # Managed WAV files
└── mp3/          # Converted MP3 files
```

Respects `XDG_CONFIG_HOME` and `XDG_DATA_HOME` if set.

## Patch vs Catalog Numbers

- **Original bank** (`--bank`): The RC-300 bank number (1-99) at import time
- **Catalog number** (`--patch`): Auto-assigned sequential ID (1, 2, 3, ...) that supports unlimited patches

This allows you to import from the same RC-300 multiple times without conflicts.

## Example Output

```
$ loopcat list --patch 42

#42 Midnight Funk Groove (bank 40)
  Laid-back funk jam with a driving bass line and rhythmic guitar.
  Style: funk | Energy: 7/10
  Mood: groovy, mellow, late-night
  Tags: guitar, bass, practice

 Track  Name              Role    Duration  BPM  Key
 1      Pocket Bass Line  bass    32.5s     92   E minor
 2      Rhythm Guitar     rhythm  32.5s     92   E minor
 3      Wah Lead          lead    32.5s     92   E minor
```

### `loopcat theme [THEME]`

Set the TUI color theme. Over 300 themes available including built-in Textual themes and Base16 color schemes.

```bash
loopcat theme                 # List available themes
loopcat theme dracula         # Set theme
```

Press `t` in the TUI to open an interactive theme picker with live preview.

## Requirements

- Python 3.11+
- ffmpeg (for MP3 conversion)
- Google API key with Gemini access (for AI analysis) - run `loopcat auth` to configure
