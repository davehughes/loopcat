"""Tests for the database layer."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from loopcat.database import Database


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield Database(db_path)


class TestDatabase:
    """Tests for Database class."""

    def test_create_patch(self, db):
        """Test creating a patch."""
        patch = db.create_patch(
            original_bank=42,
            source_path="/test/path",
            source_device="Boss RC-300",
        )

        assert patch.catalog_number == 1
        assert patch.original_bank == 42
        assert patch.source_path == "/test/path"
        assert patch.id is not None

    def test_create_multiple_patches_increments_catalog_number(self, db):
        """Test that catalog numbers auto-increment."""
        patch1 = db.create_patch(original_bank=1, source_path="/test/1")
        patch2 = db.create_patch(original_bank=2, source_path="/test/2")
        patch3 = db.create_patch(original_bank=3, source_path="/test/3")

        assert patch1.catalog_number == 1
        assert patch2.catalog_number == 2
        assert patch3.catalog_number == 3

    def test_create_track(self, db):
        """Test creating a track."""
        patch = db.create_patch(original_bank=1, source_path="/test")
        track = db.create_track(
            patch_id=patch.id,
            track_number=1,
            filename="001_1.wav",
            original_path="/original/001_1.wav",
            wav_path="/managed/001_1.wav",
            xxhash="abc123",
            quick_hash="quick123",
            file_created_at=datetime.now(),
            file_modified_at=datetime.now(),
            duration_seconds=32.5,
            sample_rate=44100,
            channels=2,
        )

        assert track.track_number == 1
        assert track.filename == "001_1.wav"
        assert track.duration_seconds == 32.5

    def test_get_patch_includes_tracks(self, db):
        """Test that get_patch returns patch with all its tracks."""
        patch = db.create_patch(original_bank=1, source_path="/test")

        # Create 3 tracks
        for i in range(1, 4):
            db.create_track(
                patch_id=patch.id,
                track_number=i,
                filename=f"001_{i}.wav",
                original_path=f"/original/001_{i}.wav",
                wav_path=f"/managed/001_{i}.wav",
                xxhash=f"hash{i}",
                quick_hash=f"quick{i}",
                file_created_at=datetime.now(),
                file_modified_at=datetime.now(),
                duration_seconds=10.0 * i,
                sample_rate=44100,
                channels=2,
            )

        loaded_patch = db.get_patch(patch.catalog_number)

        assert loaded_patch is not None
        assert len(loaded_patch.tracks) == 3
        assert loaded_patch.tracks[0].track_number == 1
        assert loaded_patch.tracks[1].track_number == 2
        assert loaded_patch.tracks[2].track_number == 3

    def test_get_all_patches_includes_tracks(self, db):
        """Test that get_all_patches returns patches with tracks."""
        # Create 2 patches with different track counts
        patch1 = db.create_patch(original_bank=1, source_path="/test/1")
        patch2 = db.create_patch(original_bank=2, source_path="/test/2")

        # Patch 1 gets 2 tracks
        for i in range(1, 3):
            db.create_track(
                patch_id=patch1.id,
                track_number=i,
                filename=f"001_{i}.wav",
                original_path=f"/original/001_{i}.wav",
                wav_path=f"/managed/001_{i}.wav",
                xxhash=f"p1hash{i}",
                quick_hash=f"p1quick{i}",
                file_created_at=datetime.now(),
                file_modified_at=datetime.now(),
                duration_seconds=10.0,
                sample_rate=44100,
                channels=2,
            )

        # Patch 2 gets 1 track
        db.create_track(
            patch_id=patch2.id,
            track_number=1,
            filename="002_1.wav",
            original_path="/original/002_1.wav",
            wav_path="/managed/002_1.wav",
            xxhash="p2hash1",
            quick_hash="p2quick1",
            file_created_at=datetime.now(),
            file_modified_at=datetime.now(),
            duration_seconds=15.0,
            sample_rate=44100,
            channels=2,
        )

        patches = db.get_all_patches()

        assert len(patches) == 2
        assert len(patches[0].tracks) == 2
        assert len(patches[1].tracks) == 1

    def test_get_nonexistent_patch_returns_none(self, db):
        """Test that getting a nonexistent patch returns None."""
        result = db.get_patch(999)
        assert result is None

    def test_quick_hash_exists(self, db):
        """Test checking for duplicate quick hashes."""
        patch = db.create_patch(original_bank=1, source_path="/test")
        db.create_track(
            patch_id=patch.id,
            track_number=1,
            filename="test.wav",
            original_path="/original/test.wav",
            wav_path="/managed/test.wav",
            xxhash="fullhash",
            quick_hash="quickhash123",
            file_created_at=datetime.now(),
            file_modified_at=datetime.now(),
            duration_seconds=10.0,
            sample_rate=44100,
            channels=2,
        )

        assert db.quick_hash_exists("quickhash123") is True
        assert db.quick_hash_exists("nonexistent") is False
