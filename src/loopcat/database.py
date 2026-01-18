"""SQLite database layer for loopcat catalog."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from loopcat.models import Patch, PatchAnalysis, Track, TrackAnalysis

# SQL schema
SCHEMA = """
CREATE TABLE IF NOT EXISTS patches (
    id TEXT PRIMARY KEY,
    catalog_number INTEGER UNIQUE NOT NULL,
    original_bank INTEGER NOT NULL,
    source_device TEXT DEFAULT 'Boss RC-300',
    source_path TEXT,
    user_tags TEXT,
    user_notes TEXT,
    rating INTEGER,
    created_at TEXT,
    analyzed_at TEXT,
    analysis_raw_response TEXT,
    suggested_name TEXT,
    description TEXT,
    mood TEXT,
    musical_style TEXT,
    energy_level INTEGER,
    tags TEXT,
    use_case TEXT
);

CREATE TABLE IF NOT EXISTS tracks (
    id TEXT PRIMARY KEY,
    patch_id TEXT NOT NULL REFERENCES patches(id),
    track_number INTEGER NOT NULL,
    filename TEXT NOT NULL,
    original_path TEXT,
    wav_path TEXT NOT NULL,
    xxhash TEXT UNIQUE,
    quick_hash TEXT UNIQUE,
    file_created_at TEXT,
    file_modified_at TEXT,
    duration_seconds REAL,
    sample_rate INTEGER,
    channels INTEGER,
    mp3_path TEXT,
    bpm REAL,
    detected_key TEXT,
    suggested_name TEXT,
    role TEXT,
    instruments TEXT,
    description TEXT,
    energy_level INTEGER,
    UNIQUE(patch_id, track_number)
);

CREATE INDEX IF NOT EXISTS idx_tracks_xxhash ON tracks(xxhash);
CREATE INDEX IF NOT EXISTS idx_tracks_quick_hash ON tracks(quick_hash);
CREATE INDEX IF NOT EXISTS idx_patches_catalog_number ON patches(catalog_number);
CREATE INDEX IF NOT EXISTS idx_patches_original_bank ON patches(original_bank);

CREATE VIRTUAL TABLE IF NOT EXISTS patches_fts USING fts5(
    suggested_name, description, tags, mood,
    content='patches',
    content_rowid='rowid'
);

CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
    suggested_name, description, instruments, role,
    content='tracks',
    content_rowid='rowid'
);

-- Triggers to keep FTS tables in sync
CREATE TRIGGER IF NOT EXISTS patches_ai AFTER INSERT ON patches BEGIN
    INSERT INTO patches_fts(rowid, suggested_name, description, tags, mood)
    VALUES (NEW.rowid, NEW.suggested_name, NEW.description, NEW.tags, NEW.mood);
END;

CREATE TRIGGER IF NOT EXISTS patches_ad AFTER DELETE ON patches BEGIN
    INSERT INTO patches_fts(patches_fts, rowid, suggested_name, description, tags, mood)
    VALUES ('delete', OLD.rowid, OLD.suggested_name, OLD.description, OLD.tags, OLD.mood);
END;

CREATE TRIGGER IF NOT EXISTS patches_au AFTER UPDATE ON patches BEGIN
    INSERT INTO patches_fts(patches_fts, rowid, suggested_name, description, tags, mood)
    VALUES ('delete', OLD.rowid, OLD.suggested_name, OLD.description, OLD.tags, OLD.mood);
    INSERT INTO patches_fts(rowid, suggested_name, description, tags, mood)
    VALUES (NEW.rowid, NEW.suggested_name, NEW.description, NEW.tags, NEW.mood);
END;

CREATE TRIGGER IF NOT EXISTS tracks_ai AFTER INSERT ON tracks BEGIN
    INSERT INTO tracks_fts(rowid, suggested_name, description, instruments, role)
    VALUES (NEW.rowid, NEW.suggested_name, NEW.description, NEW.instruments, NEW.role);
END;

CREATE TRIGGER IF NOT EXISTS tracks_ad AFTER DELETE ON tracks BEGIN
    INSERT INTO tracks_fts(tracks_fts, rowid, suggested_name, description, instruments, role)
    VALUES ('delete', OLD.rowid, OLD.suggested_name, OLD.description, OLD.instruments, OLD.role);
END;

CREATE TRIGGER IF NOT EXISTS tracks_au AFTER UPDATE ON tracks BEGIN
    INSERT INTO tracks_fts(tracks_fts, rowid, suggested_name, description, instruments, role)
    VALUES ('delete', OLD.rowid, OLD.suggested_name, OLD.description, OLD.instruments, OLD.role);
    INSERT INTO tracks_fts(rowid, suggested_name, description, instruments, role)
    VALUES (NEW.rowid, NEW.suggested_name, NEW.description, NEW.instruments, NEW.role);
END;
"""


class Database:
    """SQLite database for loopcat catalog."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def get_next_catalog_number(self) -> int:
        """Get the next available catalog number."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(catalog_number) as max_num FROM patches"
            ).fetchone()
            return (row["max_num"] or 0) + 1

    def quick_hash_exists(self, quick_hash: str) -> bool:
        """Check if a quick hash already exists in the database."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM tracks WHERE quick_hash = ?", (quick_hash,)
            ).fetchone()
            return row is not None

    def full_hash_exists(self, xxhash: str) -> bool:
        """Check if a full hash already exists in the database."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM tracks WHERE xxhash = ?", (xxhash,)
            ).fetchone()
            return row is not None

    def create_patch(
        self,
        original_bank: int,
        source_path: str,
        source_device: str = "Boss RC-300",
    ) -> Patch:
        """Create a new patch record."""
        patch_id = str(uuid4())
        catalog_number = self.get_next_catalog_number()
        now = datetime.now()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO patches (id, catalog_number, original_bank, source_device, source_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (patch_id, catalog_number, original_bank, source_device, source_path, now.isoformat()),
            )

        return Patch(
            id=patch_id,
            catalog_number=catalog_number,
            original_bank=original_bank,
            source_device=source_device,
            source_path=source_path,
            created_at=now,
        )

    def create_track(
        self,
        patch_id: str,
        track_number: int,
        filename: str,
        original_path: str,
        wav_path: str,
        xxhash: str,
        quick_hash: str,
        file_created_at: datetime,
        file_modified_at: datetime,
        duration_seconds: float,
        sample_rate: int,
        channels: int,
    ) -> Track:
        """Create a new track record."""
        track_id = str(uuid4())

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tracks (
                    id, patch_id, track_number, filename, original_path, wav_path,
                    xxhash, quick_hash, file_created_at, file_modified_at,
                    duration_seconds, sample_rate, channels
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    track_id, patch_id, track_number, filename, original_path, wav_path,
                    xxhash, quick_hash, file_created_at.isoformat(), file_modified_at.isoformat(),
                    duration_seconds, sample_rate, channels,
                ),
            )

        return Track(
            id=track_id,
            patch_id=patch_id,
            track_number=track_number,
            filename=filename,
            original_path=original_path,
            wav_path=wav_path,
            xxhash=xxhash,
            quick_hash=quick_hash,
            file_created_at=file_created_at,
            file_modified_at=file_modified_at,
            duration_seconds=duration_seconds,
            sample_rate=sample_rate,
            channels=channels,
        )

    def update_track_mp3_path(self, track_id: str, mp3_path: str) -> None:
        """Update the MP3 path for a track."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE tracks SET mp3_path = ? WHERE id = ?",
                (mp3_path, track_id),
            )

    def update_track_local_analysis(
        self, track_id: str, bpm: Optional[float], detected_key: Optional[str]
    ) -> None:
        """Update the local analysis results for a track."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE tracks SET bpm = ?, detected_key = ? WHERE id = ?",
                (bpm, detected_key, track_id),
            )

    def update_track_analysis(self, track_id: str, analysis: TrackAnalysis) -> None:
        """Update the Gemini analysis results for a track."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tracks SET
                    suggested_name = ?,
                    role = ?,
                    instruments = ?,
                    description = ?,
                    energy_level = ?
                WHERE id = ?
                """,
                (
                    analysis.suggested_name,
                    analysis.role,
                    json.dumps(analysis.instruments),
                    analysis.description,
                    analysis.energy_level,
                    track_id,
                ),
            )

    def update_patch_analysis(self, patch_id: str, analysis: PatchAnalysis) -> None:
        """Update the Gemini analysis results for a patch."""
        now = datetime.now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE patches SET
                    analyzed_at = ?,
                    analysis_raw_response = ?,
                    suggested_name = ?,
                    description = ?,
                    mood = ?,
                    musical_style = ?,
                    energy_level = ?,
                    tags = ?,
                    use_case = ?
                WHERE id = ?
                """,
                (
                    now.isoformat(),
                    analysis.raw_response,
                    analysis.suggested_name,
                    analysis.description,
                    json.dumps(analysis.mood),
                    analysis.musical_style,
                    analysis.energy_level,
                    json.dumps(analysis.tags),
                    analysis.use_case,
                    patch_id,
                ),
            )

    def get_patch(self, catalog_number: int) -> Optional[Patch]:
        """Get a patch by catalog number."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM patches WHERE catalog_number = ?", (catalog_number,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_patch(row, conn)

    def get_patch_by_id(self, patch_id: str) -> Optional[Patch]:
        """Get a patch by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM patches WHERE id = ?", (patch_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_patch(row, conn)

    def get_all_patches(self) -> list[Patch]:
        """Get all patches."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM patches ORDER BY catalog_number"
            ).fetchall()
            return [self._row_to_patch(row, conn) for row in rows]

    def get_patches_by_bank(self, original_bank: int) -> list[Patch]:
        """Get all patches from a specific original RC-300 bank."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM patches WHERE original_bank = ? ORDER BY catalog_number",
                (original_bank,),
            ).fetchall()
            return [self._row_to_patch(row, conn) for row in rows]

    def get_unanalyzed_patches(self) -> list[Patch]:
        """Get all patches that have all tracks converted but not yet analyzed."""
        with self._connect() as conn:
            # Find patches where:
            # 1. analyzed_at is NULL
            # 2. All tracks have mp3_path set
            rows = conn.execute(
                """
                SELECT p.* FROM patches p
                WHERE p.analyzed_at IS NULL
                AND NOT EXISTS (
                    SELECT 1 FROM tracks t
                    WHERE t.patch_id = p.id AND t.mp3_path IS NULL
                )
                AND EXISTS (
                    SELECT 1 FROM tracks t WHERE t.patch_id = p.id
                )
                ORDER BY p.catalog_number
                """
            ).fetchall()
            return [self._row_to_patch(row, conn) for row in rows]

    def get_unconverted_tracks(self) -> list[Track]:
        """Get all tracks without MP3 files."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tracks WHERE mp3_path IS NULL ORDER BY patch_id, track_number"
            ).fetchall()
            return [self._row_to_track(row) for row in rows]

    def search(self, query: str) -> list[Patch]:
        """Full-text search across patches and tracks."""
        with self._connect() as conn:
            # Search patches
            patch_ids = set()

            # Search in patches_fts
            rows = conn.execute(
                """
                SELECT p.id FROM patches p
                JOIN patches_fts pf ON p.rowid = pf.rowid
                WHERE patches_fts MATCH ?
                """,
                (query,),
            ).fetchall()
            patch_ids.update(row["id"] for row in rows)

            # Search in tracks_fts
            rows = conn.execute(
                """
                SELECT DISTINCT t.patch_id FROM tracks t
                JOIN tracks_fts tf ON t.rowid = tf.rowid
                WHERE tracks_fts MATCH ?
                """,
                (query,),
            ).fetchall()
            patch_ids.update(row["patch_id"] for row in rows)

            if not patch_ids:
                return []

            # Fetch full patch objects
            placeholders = ",".join("?" * len(patch_ids))
            rows = conn.execute(
                f"SELECT * FROM patches WHERE id IN ({placeholders}) ORDER BY catalog_number",
                tuple(patch_ids),
            ).fetchall()
            return [self._row_to_patch(row, conn) for row in rows]

    def _row_to_patch(self, row: sqlite3.Row, conn: sqlite3.Connection) -> Patch:
        """Convert a database row to a Patch model."""
        # Fetch tracks for this patch
        track_rows = conn.execute(
            "SELECT * FROM tracks WHERE patch_id = ? ORDER BY track_number",
            (row["id"],),
        ).fetchall()
        tracks = [self._row_to_track(tr) for tr in track_rows]

        # Build patch analysis if present
        analysis = None
        if row["analysis_raw_response"]:
            analysis = PatchAnalysis(
                raw_response=row["analysis_raw_response"],
                suggested_name=row["suggested_name"] or "",
                description=row["description"] or "",
                mood=json.loads(row["mood"]) if row["mood"] else [],
                musical_style=row["musical_style"] or "",
                energy_level=row["energy_level"] or 5,
                tags=json.loads(row["tags"]) if row["tags"] else [],
                use_case=row["use_case"],
            )

        return Patch(
            id=row["id"],
            catalog_number=row["catalog_number"],
            original_bank=row["original_bank"],
            source_device=row["source_device"],
            source_path=row["source_path"],
            tracks=tracks,
            created_at=datetime.fromisoformat(row["created_at"]),
            analyzed_at=datetime.fromisoformat(row["analyzed_at"]) if row["analyzed_at"] else None,
            user_tags=json.loads(row["user_tags"]) if row["user_tags"] else [],
            user_notes=row["user_notes"] or "",
            rating=row["rating"],
            analysis=analysis,
        )

    def _row_to_track(self, row: sqlite3.Row) -> Track:
        """Convert a database row to a Track model."""
        # Build track analysis if present
        analysis = None
        if row["suggested_name"]:
            analysis = TrackAnalysis(
                suggested_name=row["suggested_name"],
                role=row["role"] or "",
                instruments=json.loads(row["instruments"]) if row["instruments"] else [],
                description=row["description"] or "",
                energy_level=row["energy_level"] or 5,
            )

        return Track(
            id=row["id"],
            patch_id=row["patch_id"],
            track_number=row["track_number"],
            filename=row["filename"],
            original_path=row["original_path"],
            wav_path=row["wav_path"],
            xxhash=row["xxhash"],
            quick_hash=row["quick_hash"],
            file_created_at=datetime.fromisoformat(row["file_created_at"]),
            file_modified_at=datetime.fromisoformat(row["file_modified_at"]),
            duration_seconds=row["duration_seconds"],
            sample_rate=row["sample_rate"],
            channels=row["channels"],
            mp3_path=row["mp3_path"],
            bpm=row["bpm"],
            detected_key=row["detected_key"],
            analysis=analysis,
        )

    def get_stats(self) -> dict:
        """Get catalog statistics.

        Returns:
            Dictionary with stats including:
            - patch_count: total patches
            - track_count: total tracks
            - total_duration_seconds: sum of all track durations
            - analyzed_count: patches with analysis
            - converted_count: tracks with MP3
            - styles: dict of style -> count
            - energy_distribution: dict of level -> count
            - bpm_min, bpm_max, bpm_avg: BPM statistics
        """
        with self._connect() as conn:
            # Basic counts
            patch_count = conn.execute("SELECT COUNT(*) FROM patches").fetchone()[0]
            track_count = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
            analyzed_count = conn.execute(
                "SELECT COUNT(*) FROM patches WHERE analyzed_at IS NOT NULL"
            ).fetchone()[0]
            converted_count = conn.execute(
                "SELECT COUNT(*) FROM tracks WHERE mp3_path IS NOT NULL"
            ).fetchone()[0]

            # Total duration
            total_duration = conn.execute(
                "SELECT COALESCE(SUM(duration_seconds), 0) FROM tracks"
            ).fetchone()[0]

            # BPM stats
            bpm_row = conn.execute(
                """
                SELECT MIN(bpm), MAX(bpm), AVG(bpm)
                FROM tracks WHERE bpm IS NOT NULL
                """
            ).fetchone()
            bpm_min = bpm_row[0]
            bpm_max = bpm_row[1]
            bpm_avg = bpm_row[2]

            # Style distribution
            styles: dict[str, int] = {}
            rows = conn.execute(
                "SELECT musical_style FROM patches WHERE musical_style IS NOT NULL AND musical_style != ''"
            ).fetchall()
            for row in rows:
                style = row[0].lower()
                styles[style] = styles.get(style, 0) + 1

            # Energy distribution (group into low/medium/high)
            energy_dist: dict[str, int] = {"low": 0, "medium": 0, "high": 0}
            rows = conn.execute(
                "SELECT energy_level FROM patches WHERE energy_level IS NOT NULL"
            ).fetchall()
            for row in rows:
                level = row[0]
                if level <= 3:
                    energy_dist["low"] += 1
                elif level <= 6:
                    energy_dist["medium"] += 1
                else:
                    energy_dist["high"] += 1

            return {
                "patch_count": patch_count,
                "track_count": track_count,
                "total_duration_seconds": total_duration,
                "analyzed_count": analyzed_count,
                "converted_count": converted_count,
                "styles": styles,
                "energy_distribution": energy_dist,
                "bpm_min": bpm_min,
                "bpm_max": bpm_max,
                "bpm_avg": bpm_avg,
            }
