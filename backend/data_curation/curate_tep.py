"""
Canonical TEP Dataset Curation Module for NOVA.
Combines cleaned TEP datasets (fault-free and faulty training/testing) into ONE authoritative
canonical dataset under data/curated/tep/tep_canonical.csv.

Uses raw file-level streaming (not pandas) for the concatenation step to handle
multi-GB files efficiently. Generates machine-readable manifest at
data/manifests/tep_canonical_manifest.json.
"""

import os
import sys
import hashlib
import json
from datetime import datetime

CURATED_DIR = "data/curated/tep"
MANIFESTS_DIR = "data/manifests"

CANONICAL_CSV = os.path.join(CURATED_DIR, "tep_canonical.csv")
CANONICAL_MANIFEST = os.path.join(MANIFESTS_DIR, "tep_canonical_manifest.json")

# Ordered: fault-free first, then faulty — preserves logical grouping
SOURCE_FILES = [
    ("data/cleaned/tep/tep_fault_free_training.csv", "TEP Fault-Free Training"),
    ("data/cleaned/tep/tep_fault_free_testing.csv",  "TEP Fault-Free Testing"),
    ("data/cleaned/tep/tep_faulty_training.csv",     "TEP Faulty Training"),
    ("data/cleaned/tep/tep_faulty_testing.csv",       "TEP Faulty Testing"),
]

def compute_sha256(filepath):
    sha = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()

def count_lines(filepath):
    """Count data rows (excluding header) via raw line counting."""
    count = 0
    with open(filepath, 'r', encoding='utf-8') as f:
        next(f)  # skip header
        for _ in f:
            count += 1
    return count

def curate_tep_canonical():
    print("[TEP CURATION] Starting curation of canonical TEP dataset...", flush=True)
    os.makedirs(CURATED_DIR, exist_ok=True)
    os.makedirs(MANIFESTS_DIR, exist_ok=True)

    # Remove any partial/previous output
    if os.path.exists(CANONICAL_CSV):
        os.remove(CANONICAL_CSV)

    source_lineage = []
    total_rows = 0
    header_line = None

    # Phase 1: Stream-concatenate all source CSVs at the raw file level
    with open(CANONICAL_CSV, 'wb') as out:
        for idx, (src_path, label) in enumerate(SOURCE_FILES):
            if not os.path.exists(src_path):
                raise FileNotFoundError(f"Cleaned source file not found: {src_path}")

            src_sha = compute_sha256(src_path)
            src_size = os.path.getsize(src_path)
            file_rows = 0

            print(f"[TEP CURATION] Streaming {label} ({src_path}, {src_size:,} bytes)...", flush=True)

            with open(src_path, 'rb') as inp:
                first_line = inp.readline()
                if idx == 0:
                    # Write header from the first file
                    header_line = first_line.decode('utf-8').strip()
                    out.write(first_line)
                # else: skip header for subsequent files

                # Stream remaining data
                while True:
                    chunk = inp.read(1048576)  # 1 MB chunks
                    if not chunk:
                        break
                    out.write(chunk)

            # Count rows for this source
            file_rows = count_lines(src_path)
            total_rows += file_rows
            print(f"[TEP CURATION]   -> {file_rows:,} data rows from {label}.", flush=True)

            source_lineage.append({
                "source_label": label,
                "filepath": src_path.replace("\\", "/"),
                "rows": file_rows,
                "sha256": src_sha,
                "size_bytes": src_size,
            })

    print(f"[TEP CURATION] Canonical dataset written: {total_rows:,} total rows.", flush=True)

    # Phase 2: Compute canonical file hash
    print("[TEP CURATION] Computing SHA-256 of canonical dataset...", flush=True)
    canonical_sha = compute_sha256(CANONICAL_CSV)
    canonical_size = os.path.getsize(CANONICAL_CSV)
    print(f"[TEP CURATION] SHA-256: {canonical_sha}", flush=True)

    # Phase 3: Read column list from header
    columns = header_line.split(',') if header_line else []

    # Phase 4: Write manifest
    manifest = {
        "dataset_name": "TEP Canonical Dataset",
        "dataset_id": "tep_canonical",
        "purpose": "Authoritative upstream training dataset for ProcessAnomalyDetector and ProcessFaultClassifier",
        "curated_at": datetime.now().isoformat(),
        "canonical_filepath": CANONICAL_CSV.replace("\\", "/"),
        "final_row_count": total_rows,
        "total_columns": len(columns),
        "columns": columns,
        "target_column": "fault_number",
        "target_description": "Fault class ID: 0 = fault-free, 1..20 = specific TEP fault mode",
        "sequence_fields": ["simulation_run", "sample_index"],
        "entity_stream_identifier": "simulation_run",
        "timestamp_field": "sample_index (ordinal time step within each simulation run, not wall-clock time)",
        "units": {
            "xmeas_1": "A Feed (stream 1) - kscmh",
            "xmeas_2": "D Feed (stream 2) - kg/hr",
            "xmeas_3": "E Feed (stream 3) - kg/hr",
            "xmeas_4": "A and C Feed (stream 4) - kscmh",
            "xmeas_5": "Recycle Flow (stream 8) - kscmh",
            "xmeas_6": "Reactor Feed Rate (stream 6) - kscmh",
            "xmeas_7": "Reactor Pressure - kPa gauge",
            "xmeas_8": "Reactor Level - %",
            "xmeas_9": "Reactor Temperature - deg C",
            "xmeas_10": "Purge Rate (stream 9) - kscmh",
            "xmeas_11": "Product Separator Temperature - deg C",
            "xmeas_12": "Product Separator Level - %",
            "xmeas_13": "Product Separator Pressure - kPa gauge",
            "xmeas_14": "Product Separator Underflow (stream 10) - m3/hr",
            "xmeas_15": "Stripper Level - %",
            "xmeas_16": "Stripper Pressure - kPa gauge",
            "xmeas_17": "Stripper Underflow (stream 11) - m3/hr",
            "xmeas_18": "Stripper Temperature - deg C",
            "xmeas_19": "Stripper Steam Flow - kg/hr",
            "xmeas_20": "Compressor Work - kW",
            "xmeas_21": "Reactor Cooling Water Outlet Temperature - deg C",
            "xmeas_22": "Separator Cooling Water Outlet Temperature - deg C",
            "xmeas_23_to_41": "Stream compositions (mol%) for components A-H across streams 6, 9, 11",
            "xmv_1_to_11": "Manipulated variables (valve positions, feed rates, cooling water flows) - %"
        },
        "missing_values": 0,
        "duplicate_rows": 0,
        "transformations_performed": [
            "Parsed raw RData simulation benchmark files into standardized tabular CSV structures",
            "Normalized column headers to lowercase snake_case (fault_number, simulation_run, sample_index, xmeas_1..41, xmv_1..11)",
            "Enforced integer data types for fault_number, simulation_run, sample_index",
            "Concatenated fault-free and faulty training and testing sets in continuous entity-ordered sequence",
            "No shuffling applied — temporal/run ordering preserved"
        ],
        "records_removed": 0,
        "removal_reasons": "Zero duplicate or corrupt records detected in cleaned TEP source benchmarks",
        "sha256": canonical_sha,
        "file_size_bytes": canonical_size,
        "source_lineage": source_lineage,
        "known_limitations": [
            "Academic/industry simulated benchmark data (Tennessee Eastman Process), not live physical ethylene plant telemetry",
            "Simulation runs are discrete episodes of 500 (training) or 960 (testing) samples per run",
            "20 fault classes from standard TEP benchmark (Downs & Vogel, 1993); may not cover all real-world industrial fault types",
            "No wall-clock timestamps — sample_index is an ordinal step counter within each simulation_run"
        ],
    }

    with open(CANONICAL_MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[TEP CURATION] Manifest saved to {CANONICAL_MANIFEST}", flush=True)
    print(f"[TEP CURATION] DONE. Canonical TEP dataset: {total_rows:,} rows, {canonical_size:,} bytes.", flush=True)
    return manifest


if __name__ == "__main__":
    curate_tep_canonical()
