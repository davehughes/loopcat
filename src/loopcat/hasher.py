"""Hash utilities for file deduplication."""

from pathlib import Path

import xxhash

# Size of the chunk to read for quick hash (64KB)
QUICK_HASH_CHUNK_SIZE = 65536


def compute_quick_hash(file_path: Path) -> str:
    """Compute a fast hash using first 64KB + file size.

    This is used for quick duplicate detection on slow USB storage.
    The combination of file size and first 64KB provides a good
    balance between speed and collision resistance.

    Args:
        file_path: Path to the file to hash.

    Returns:
        Hex string of the xxhash64 digest.
    """
    size = file_path.stat().st_size
    h = xxhash.xxh64()
    h.update(size.to_bytes(8, "little"))
    with open(file_path, "rb") as f:
        h.update(f.read(QUICK_HASH_CHUNK_SIZE))
    return h.hexdigest()


def compute_full_hash(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute a full xxhash64 of the entire file.

    This is used for permanent deduplication after copying to local storage.

    Args:
        file_path: Path to the file to hash.
        chunk_size: Size of chunks to read (default 1MB).

    Returns:
        Hex string of the xxhash64 digest.
    """
    h = xxhash.xxh64()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()
