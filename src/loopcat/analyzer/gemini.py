"""Gemini-based audio analysis."""

import json
from pathlib import Path

from google import genai
from google.genai import types

from loopcat.config import get_gemini_api_key
from loopcat.models import PatchAnalysis, TrackAnalysis

# Analysis prompt template
ANALYSIS_PROMPT = """You are analyzing audio loops from a Boss RC-300 looper pedal.
I'm uploading {track_count} track(s) that belong to the same patch (recorded together as a musical unit).

Please analyze these tracks and provide:

1. **Patch-level analysis** (how the tracks work together):
   - suggested_name: A creative, descriptive name for this patch (e.g., "Midnight Funk Groove", "Ambient Dreamscape")
   - description: How the tracks complement each other (2-3 sentences)
   - mood: List of mood descriptors (e.g., ["mellow", "groovy", "contemplative"])
   - musical_style: Primary genre/style (e.g., "funk", "ambient", "blues rock")
   - energy_level: Overall energy from 1-10
   - tags: Searchable tags for the catalog (e.g., ["guitar", "lofi", "practice"])
   - use_case: Suggested use (e.g., "practice backing track", "song idea", "ambient background")

2. **Track-level analysis** (for each track):
   - suggested_name: A name for this specific track (e.g., "Funky Bass Line", "Shimmering Pad")
   - role: The track's role in the patch (e.g., "rhythm", "lead", "bass", "drums", "pad", "texture")
   - instruments: List of instruments/sounds detected
   - description: What this track contributes (1-2 sentences)
   - energy_level: Energy level from 1-10

Respond with valid JSON in this exact format:
{{
  "patch": {{
    "suggested_name": "string",
    "description": "string",
    "mood": ["string"],
    "musical_style": "string",
    "energy_level": 1-10,
    "tags": ["string"],
    "use_case": "string or null"
  }},
  "tracks": [
    {{
      "track_number": 1,
      "suggested_name": "string",
      "role": "string",
      "instruments": ["string"],
      "description": "string",
      "energy_level": 1-10
    }}
  ]
}}

The tracks array should have one entry per track, in order (track 1, track 2, track 3).
"""


def analyze_patch_with_gemini(
    mp3_paths: list[tuple[int, Path]],
    model_name: str = "gemini-2.0-flash",
) -> tuple[PatchAnalysis, dict[int, TrackAnalysis]]:
    """Analyze a patch using Gemini.

    Args:
        mp3_paths: List of (track_number, mp3_path) tuples.
        model_name: Gemini model to use.

    Returns:
        Tuple of (PatchAnalysis, dict mapping track_number to TrackAnalysis).

    Raises:
        ValueError: If GOOGLE_API_KEY is not set.
        Exception: If Gemini API call fails.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError("Gemini API key not configured. Run 'loopcat auth' to set it.")

    client = genai.Client(api_key=api_key)

    # Upload audio files
    uploaded_files = []
    for track_num, mp3_path in sorted(mp3_paths):
        uploaded = client.files.upload(file=mp3_path)
        uploaded_files.append((track_num, uploaded))

    # Build the prompt
    prompt = ANALYSIS_PROMPT.format(track_count=len(mp3_paths))

    # Build content with audio files
    contents = []
    for track_num, uploaded in uploaded_files:
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part(text=f"Track {track_num}:"),
                    types.Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type),
                ],
            )
        )

    contents.append(
        types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        )
    )

    # Call Gemini
    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.7,
            response_mime_type="application/json",
        ),
    )

    raw_response = response.text

    # Parse JSON response
    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse Gemini response as JSON: {e}\nResponse: {raw_response}")

    # Build PatchAnalysis
    patch_data = data.get("patch", {})
    patch_analysis = PatchAnalysis(
        raw_response=raw_response,
        suggested_name=patch_data.get("suggested_name", "Untitled Patch"),
        description=patch_data.get("description", ""),
        mood=patch_data.get("mood", []),
        musical_style=patch_data.get("musical_style", ""),
        energy_level=patch_data.get("energy_level", 5),
        tags=patch_data.get("tags", []),
        use_case=patch_data.get("use_case"),
    )

    # Build TrackAnalysis for each track
    track_analyses = {}
    for track_data in data.get("tracks", []):
        track_num = track_data.get("track_number", 1)
        track_analyses[track_num] = TrackAnalysis(
            suggested_name=track_data.get("suggested_name", f"Track {track_num}"),
            role=track_data.get("role", ""),
            instruments=track_data.get("instruments", []),
            description=track_data.get("description", ""),
            energy_level=track_data.get("energy_level", 5),
        )

    # Clean up uploaded files
    for _, uploaded in uploaded_files:
        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass  # Ignore cleanup errors

    return patch_analysis, track_analyses
