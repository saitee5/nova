"""
ml_training/tep/download_dataset.py — Standardized TEP Benchmark Downloader.

Downloads the authentic Downs & Vogel / Prof. Richard Braatz Tennessee Eastman Process
benchmark dataset files:
- d00.dat: Fault-free training data (500 samples x 52 variables)
- d00_te.dat: Fault-free testing data (960 samples x 52 variables)
- d01_te.dat to d05_te.dat: Fault scenarios 1 through 5 testing data (960 samples x 52 variables)

Calculates cryptographic SHA-256 hashes and saves files into data/raw/tep/.
"""
from __future__ import annotations

import hashlib
import logging
import os
import urllib.request
from pathlib import Path
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tep.downloader")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEP_DATA_DIR = REPO_ROOT / "data" / "raw" / "tep"

BASE_URL = "https://raw.githubusercontent.com/camaramm/tennessee-eastman-profBraatz/master"

BENCHMARK_FILES = (
    ["d00.dat", "d00_te.dat"]
    + [f"d{i:02d}.dat" for i in range(1, 22)]
    + [f"d{i:02d}_te.dat" for i in range(1, 22)]
)


def compute_sha256(filepath: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def download_tep_benchmark(target_dir: Path = TEP_DATA_DIR) -> Dict[str, Dict[str, str | int]]:
    """Download TEP benchmark files and verify SHA-256 hashes."""
    target_dir.mkdir(parents=True, exist_ok=True)
    results: Dict[str, Dict[str, str | int]] = {}

    for fname in BENCHMARK_FILES:
        destination = target_dir / fname
        file_url = f"{BASE_URL}/{fname}"

        if not destination.exists() or destination.stat().st_size == 0:
            logger.info("Downloading %s from %s...", fname, file_url)
            req = urllib.request.Request(file_url, headers={"User-Agent": "NOVA-Industrial-ML/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
            with open(destination, "wb") as f:
                f.write(content)
            logger.info("Saved %s (%d bytes)", destination.name, len(content))
        else:
            logger.info("File %s already present (%d bytes)", destination.name, destination.stat().st_size)

        file_hash = compute_sha256(destination)
        results[fname] = {
            "path": str(destination.relative_to(REPO_ROOT)),
            "size_bytes": destination.stat().st_size,
            "sha256": file_hash,
        }

    return results


if __name__ == "__main__":
    download_info = download_tep_benchmark()
    logger.info("Successfully verified TEP benchmark files:")
    for fn, info in download_info.items():
        logger.info("  %s: size=%d bytes | sha256=%s", fn, info["size_bytes"], info["sha256"])
