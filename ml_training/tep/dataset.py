"""
ml_training/tep/dataset.py — Tennessee Eastman Process Dataset Loader & Validator.

Loads, validates, and splits the authentic Downs & Vogel / Prof. Richard Braatz TEP benchmark.
- d00.dat: 52 variables x 500 samples (transposed to 500 x 52)
- d00_te.dat: 960 samples x 52 variables (fault-free test)
- d01_te.dat to d05_te.dat: 960 samples x 52 variables (faults 1-5, introduced at sample 160)
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger("tep.dataset")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEP_DATA_DIR = REPO_ROOT / "data" / "raw" / "tep"

# 41 Continuous Process Measurements + 11 Manipulated Variables
MEASURED_VARS = [f"xmeas_{i}" for i in range(1, 42)]
MANIPULATED_VARS = [f"xmv_{j}" for j in range(1, 12)]
CANONICAL_FEATURES: List[str] = MEASURED_VARS + MANIPULATED_VARS  # Total: 52

# Expected SHA-256 hashes for integrity gating (all 44 TEP benchmark files)
VERIFIED_HASHES: Dict[str, str] = {
    "d00.dat": "4c3c0b11eefacf93e5d2529e2866d7a625e37aa9153d0f95fae17a6c9e560deb",
    "d00_te.dat": "57d56da4199e3d73582855d810be1d13d931386fd728bf1694798c7b0a03678c",
    "d01.dat": "b0da22ac7561d82b0ba0b48bf87d2b3a8655cb23a3dc37330dd03cdd126c387c",
    "d01_te.dat": "e7e6992fb39664e739fccbc001a1c5d5f7cb21829544f734ca3f282c26f680e5",
    "d02.dat": "af1a46ba3a5482be3e7b143606f22ae509138544af2a2d0eb7389459257f8179",
    "d02_te.dat": "a34bd9c3693fa96bd3ee533fb7fbe29a9d226a4e3250b585ef1308e1136dbfb0",
    "d03.dat": "df39c57bdac7ea476ee236c289e0f59b0cbf868adfbbbaf213f692d8cd96e52a",
    "d03_te.dat": "b7bf6f2ed7cff0a5577898b009edd252b9bdf6ee9ff7dbeacf9af9aa4c6abace",
    "d04.dat": "346702fce33d9707f0b4ec5b8f533ccb08be60313607d5156d7e237b80a87b3f",
    "d04_te.dat": "1ccb488dd5feac11aad54623451168abef066229e685872597897800363916f9",
    "d05.dat": "3a47bfce4010ce0c634ae828409cce657ecd03bf0c4d59f8dd4a3d4f792f493f",
    "d05_te.dat": "1def7258a2865aeead699d52c8cf926fbf34c1467aaf298121987ab858fd0888",
    "d06.dat": "ff0882a44bb74f5d2d1a864425ac7e5ae82420391c7060232cefc08ad5bf7331",
    "d06_te.dat": "8a3adc7121eaa9b9300c27f9c57a8ab356315401cb964310a4a8244dd34bf79d",
    "d07.dat": "e3fd272ed53f899ab0c8278c7eede55418b01a2339b5fcff14a87fefaa3d181d",
    "d07_te.dat": "e01b7c81daf9fccc4495cbde5658296918276b3c078044893f6e945dd91d3446",
    "d08.dat": "4817735e339449bec909d1cbe77e421acc79c7357b8c6b5bb82c6e5788b72449",
    "d08_te.dat": "c0637f02f23b79890b43cfee9604818ad6d7f81532223d76acf1da0d6e2a2cc1",
    "d09.dat": "cb9146da760cdd52cad575d745413a5cfb4b447af2db9fb6a424cf6881ff0fcd",
    "d09_te.dat": "513df6c3a4fd48e0eaddb0002cd8cdab3a78a5c83c47883bb52d2dc6c2472428",
    "d10.dat": "e08697b5d074aea2345434bc4d26296f5dbdbb7efbf37a1bbee292b2ce765e8f",
    "d10_te.dat": "3a278be79d8d111fc60be3cfb4f961c28e2dc632f17eb519886aa0f95864ffc6",
    "d11.dat": "8294734d6f6e8f6b8643b9dc72f38ce40afd868d30dee9368a0d26b963a0af9f",
    "d11_te.dat": "6d60a4c932d918e1ab26ae5d16320936a665f3aad3f05482d23f5c4550b9f29a",
    "d12.dat": "62fcb3c71c0eda8eaaaf707f35296e60b17baaf9a9aef588687532cf4c560d38",
    "d12_te.dat": "2180fcecb01d1b110b429ba2969d6b18dcc625599e3640e54f69afa32dccbe50",
    "d13.dat": "f755d4ab6dc1d30e36c2e4604eeb0baff4b91032f487398b97fb1220eda861dd",
    "d13_te.dat": "2e34e0c427d6e41d77d6cae76550b7e95004f9f13bc093278ecf5c282a1c9f03",
    "d14.dat": "29fda7d5cae58cb7240e569e2d2d436371d077d282187d9205c7dc01df8755af",
    "d14_te.dat": "e8976d056c0769cebbcec3bcba89d2468040ccae7acbea55ebc3b2e56b217396",
    "d15.dat": "4c82fe0864cce2521e91a2c3e59d8630627c5e633cffe83f5e34ebc9901b5bca",
    "d15_te.dat": "a7242b956837bec8ca7f224d01805247f2aea6ea868eaa064e068b5c0761b1e5",
    "d16.dat": "ca1dfc5e31292052e83dcf6b4f60a73da197eb8a47e65d908ed7ac3cbcccb007",
    "d16_te.dat": "8381d7371aac49b498e7bf93149b77a0a6bbeffe73520881dcbe8ae96277244d",
    "d17.dat": "596aad6421a64d257bfa098cd5c4664d46dc49d88d1bad86cbc9518e6cd69e42",
    "d17_te.dat": "27d2d72052064e3cbb7a45df8073f15bb83b77403f532616e73c8869b043e7c9",
    "d18.dat": "b4d182c070036104cf150bc33f7aa879805f19943eb298bc05bdc8647dc70291",
    "d18_te.dat": "1db5b93a7daa58ed1b641845b58ad818546ced7f3de866c086da18a7ebef5041",
    "d19.dat": "ee3d2a50285cb3ba5e52ec05ea7cb39dc2b574bec592af9d44c192be132aeea6",
    "d19_te.dat": "c24dd77f787f89347273addc8a453d79f0b99edd64d43be11a5e0907bd515c5f",
    "d20.dat": "acdfe6c256fa6de74a811d6c7df1b710a9f0ed60f48242be92f3fa30db3df6b3",
    "d20_te.dat": "e54035eda95311f13dd095f87607d97a89b7541afa2a3f68af098f33a5e2e6e5",
    "d21.dat": "f34a9fefffef04ef1f49b3fb74e3def0010cda27a8577d814dd50604e2f8dc09",
    "d21_te.dat": "b6823aa09638cd59cb168bc24f991b6d4d557d8aea62b0b2a87ee67c21ba5a83",
}

# Downs & Vogel (1993) TEP Fault Definitions (22 Classes: 0 = Normal, 1..21 = Faults)
FAULT_DESCRIPTIONS: Dict[int, Dict[str, str]] = {
    0: {"code": "NORMAL", "description": "Normal Steady-State Operation", "type": "Normal"},
    1: {"code": "IDV(1)", "description": "A/C Feed Ratio, B Composition Constant (Stream 4) - Step", "type": "Step"},
    2: {"code": "IDV(2)", "description": "B Composition, A/C Ratio Constant (Stream 4) - Step", "type": "Step"},
    3: {"code": "IDV(3)", "description": "D Feed Temp (Stream 2) - Step", "type": "Step"},
    4: {"code": "IDV(4)", "description": "Reactor Cooling Water Inlet Temp - Step", "type": "Step"},
    5: {"code": "IDV(5)", "description": "Condenser Cooling Water Inlet Temp - Step", "type": "Step"},
    6: {"code": "IDV(6)", "description": "A Feed Loss (Stream 1) - Step", "type": "Step"},
    7: {"code": "IDV(7)", "description": "C Header Pressure Loss - Reduced Availability (Stream 4) - Step", "type": "Step"},
    8: {"code": "IDV(8)", "description": "A, B, C Feed Composition (Stream 4) - Random Variation", "type": "Random"},
    9: {"code": "IDV(9)", "description": "D Feed Temp (Stream 2) - Random Variation", "type": "Random"},
    10: {"code": "IDV(10)", "description": "C Feed Temp (Stream 4) - Random Variation", "type": "Random"},
    11: {"code": "IDV(11)", "description": "Reactor Cooling Water Inlet Temp - Random Variation", "type": "Random"},
    12: {"code": "IDV(12)", "description": "Condenser Cooling Water Inlet Temp - Random Variation", "type": "Random"},
    13: {"code": "IDV(13)", "description": "Reaction Kinetics - Slow Drift", "type": "Drift"},
    14: {"code": "IDV(14)", "description": "Reactor Cooling Water Valve - Sticking", "type": "Sticking"},
    15: {"code": "IDV(15)", "description": "Condenser Cooling Water Valve - Sticking", "type": "Sticking"},
    16: {"code": "IDV(16)", "description": "Unknown Disturbance A", "type": "Unknown"},
    17: {"code": "IDV(17)", "description": "Unknown Disturbance B", "type": "Unknown"},
    18: {"code": "IDV(18)", "description": "Unknown Disturbance C", "type": "Unknown"},
    19: {"code": "IDV(19)", "description": "Unknown Disturbance D", "type": "Unknown"},
    20: {"code": "IDV(20)", "description": "Unknown Disturbance E", "type": "Unknown"},
    21: {"code": "IDV(21)", "description": "Stream 4 Valve Fixed Position", "type": "Valve Position"},
}

# 156 Canonical Fault Feature Schema (52 variables x 3 feature families: raw, mean, delta)
RAW_FAULT_FEATURES: List[str] = [f"{v}_raw" for v in CANONICAL_FEATURES]
MEAN_FAULT_FEATURES: List[str] = [f"{v}_mean" for v in CANONICAL_FEATURES]
DELTA_FAULT_FEATURES: List[str] = [f"{v}_delta" for v in CANONICAL_FEATURES]
CANONICAL_FAULT_FEATURES: List[str] = RAW_FAULT_FEATURES + MEAN_FAULT_FEATURES + DELTA_FAULT_FEATURES  # Total: 156


def compute_file_sha256(filepath: Path) -> str:
    """Calculate SHA-256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


@dataclass
class TEPDatasetSplit:
    """Container for training, validation, and testing dataset splits."""
    x_train: pd.DataFrame        # 400 normal samples (80% of d00.dat)
    x_val: pd.DataFrame          # 100 normal samples (20% of d00.dat)
    y_train: np.ndarray          # 400 zeros
    y_val: np.ndarray            # 100 zeros
    test_sets: Dict[str, Tuple[pd.DataFrame, np.ndarray]]  # dict of (X_test, y_test)
    feature_names: List[str]
    metadata: Dict[str, Any]


@dataclass
class TEPMulticlassSplit:
    """Container for 22-class multiclass fault diagnosis dataset."""
    x_train: pd.DataFrame        # 156 features
    y_train: np.ndarray          # integer labels 0..21
    x_val: pd.DataFrame          # 156 features
    y_val: np.ndarray            # integer labels 0..21
    x_test: pd.DataFrame         # 156 features
    y_test: np.ndarray           # integer labels 0..21
    feature_names: List[str]     # 156 feature names in frozen order
    class_mapping: Dict[int, Dict[str, str]]
    metadata: Dict[str, Any]


def load_raw_matrix(filepath: Path, expected_transposed: bool = False) -> np.ndarray:
    """
    Load whitespace-separated ASCII matrix from file.
    Validates dimensions against TEP 52-variable specification.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"TEP benchmark file not found: {filepath}")

    actual_hash = compute_file_sha256(filepath)
    expected_hash = VERIFIED_HASHES.get(filepath.name)
    if expected_hash and actual_hash != expected_hash:
        raise ValueError(
            f"Integrity check failed for {filepath.name}. Expected {expected_hash}, got {actual_hash}"
        )

    # d00.dat is 52 lines of 500 floats (variables x samples)
    # d01.dat to d21.dat is 480 lines of 52 floats (samples x variables)
    # d*_te.dat is 960 lines of 52 floats (samples x variables)
    data = np.loadtxt(filepath)
    if expected_transposed:
        if data.shape != (52, 500):
            raise ValueError(f"Expected shape (52, 500) for {filepath.name}, got {data.shape}")
        data = data.T  # Transpose to (500, 52) (samples x variables)
    else:
        if data.ndim != 2 or data.shape[1] != 52:
            raise ValueError(f"Expected (?, 52) for {filepath.name}, got {data.shape}")

    return data


def construct_run_window_features(mat: np.ndarray, window_size: int = 3) -> np.ndarray:
    """
    Construct 156 deterministic window features for a single simulation run.
    Leakage protection: Window buffer is strictly confined within this run (uses only t-2, t-1, t).
    Feature layout:
      [raw (52), mean (52), delta (52)] = 156 features.
    Startup handling (t=0): mean = x[0], delta = 0.0.
    t=1: mean = mean(x[0], x[1]), delta = x[1] - x[0].
    t>=2: mean = mean(x[t-2:t+1]), delta = x[t] - x[t-2].
    """
    n_samples, n_vars = mat.shape
    if n_vars != 52:
        raise ValueError(f"Expected 52 variables, got {n_vars}")

    features = np.zeros((n_samples, n_vars * 3), dtype=np.float64)
    for t in range(n_samples):
        raw = mat[t]
        if t == 0:
            mean = raw.copy()
            delta = np.zeros_like(raw)
        elif t == 1:
            mean = np.mean(mat[0:2], axis=0)
            delta = mat[1] - mat[0]
        else:
            mean = np.mean(mat[t - window_size + 1 : t + 1], axis=0)
            delta = mat[t] - mat[t - window_size + 1]

        # Order: raw (52) then mean (52) then delta (52)
        features[t] = np.concatenate([raw, mean, delta])

    return features


def load_tep_splits(data_dir: Path = TEP_DATA_DIR, train_ratio: float = 0.8) -> TEPDatasetSplit:
    """
    Load TEP benchmark and generate leakage-safe chronological splits:
    - d00.dat: 500 normal samples -> 400 train (80%), 100 val (20%)
    - d00_te.dat: 960 normal test samples (label 0)
    - d01_te.dat to d05_te.dat: 960 test samples each (0 for samples 0-159, 1 for samples 160-959)
    """
    d00_path = data_dir / "d00.dat"
    d00_data = load_raw_matrix(d00_path, expected_transposed=True)

    n_samples = len(d00_data)
    split_idx = int(n_samples * train_ratio)

    x_train_raw = d00_data[:split_idx, :]
    x_val_raw = d00_data[split_idx:, :]

    df_train = pd.DataFrame(x_train_raw, columns=CANONICAL_FEATURES)
    df_val = pd.DataFrame(x_val_raw, columns=CANONICAL_FEATURES)

    y_train = np.zeros(len(df_train), dtype=int)
    y_val = np.zeros(len(df_val), dtype=int)

    # Load test sets
    test_sets: Dict[str, Tuple[pd.DataFrame, np.ndarray]] = {}

    d00_te_path = data_dir / "d00_te.dat"
    d00_te_data = load_raw_matrix(d00_te_path, expected_transposed=False)
    test_sets["normal_d00_te"] = (
        pd.DataFrame(d00_te_data, columns=CANONICAL_FEATURES),
        np.zeros(len(d00_te_data), dtype=int),
    )

    fault_names = {
        "d01_te.dat": "fault_01_ac_feed_ratio",
        "d02_te.dat": "fault_02_b_composition",
        "d03_te.dat": "fault_03_d_feed_temp",
        "d04_te.dat": "fault_04_reactor_cooling_temp",
        "d05_te.dat": "fault_05_condenser_cooling_temp",
    }

    for fname, desc in fault_names.items():
        fpath = data_dir / fname
        fdata = load_raw_matrix(fpath, expected_transposed=False)
        y_test = np.zeros(len(fdata), dtype=int)
        y_test[160:] = 1  # Fault starts at sample 160
        test_sets[desc] = (pd.DataFrame(fdata, columns=CANONICAL_FEATURES), y_test)

    metadata = {
        "dataset_name": "Tennessee Eastman Process (TEP) Benchmark",
        "origin": "Prof. Richard Braatz (UIUC/MIT) / Downs & Vogel (1993)",
        "train_samples": len(df_train),
        "val_samples": len(df_val),
        "variables_count": len(CANONICAL_FEATURES),
        "sampling_interval_minutes": 3.0,
        "fault_injection_sample": 160,
    }

    logger.info(
        "Loaded TEP dataset: train=%d samples, val=%d samples, test_scenarios=%d",
        len(df_train),
        len(df_val),
        len(test_sets),
    )

    return TEPDatasetSplit(
        x_train=df_train,
        x_val=df_val,
        y_train=y_train,
        y_val=y_val,
        test_sets=test_sets,
        feature_names=CANONICAL_FEATURES,
        metadata=metadata,
    )


def load_tep_multiclass_splits(
    data_dir: Path = TEP_DATA_DIR,
    train_ratio: float = 0.75,
    window_size: int = 3,
) -> TEPMulticlassSplit:
    """
    Load authentic 22-class TEP benchmark with rigorous leakage-safe chronological splitting:
    - Training runs: d00.dat (500 samples) and d01.dat through d21.dat (480 samples each).
    - Transition window handling:
      In d01..d21, disturbance is introduced at sample 20.
      For W=3:
        t < 20: pure NORMAL windows (Class 0).
        t = 20 (window: 18, 19, 20) and t = 21 (window: 19, 20, 21): EXCLUDED transition windows.
        t >= 22: pure FAULT windows (Class f_id).
    - Chronological split:
      For each run, first 75% -> Train, final 25% -> Validation.
    - Independent test runs: d00_te.dat (all NORMAL) and d01_te.dat..d21_te.dat (960 samples each).
      Samples 0..159 -> NORMAL (Class 0), samples 160..959 -> FAULT (Class f_id).
    """
    x_train_parts: List[np.ndarray] = []
    y_train_parts: List[np.ndarray] = []
    x_val_parts: List[np.ndarray] = []
    y_val_parts: List[np.ndarray] = []
    x_test_parts: List[np.ndarray] = []
    y_test_parts: List[np.ndarray] = []

    total_excluded_transitions = 0

    # 1. Normal Training Run: d00.dat (500 samples, all Class 0)
    d00_path = data_dir / "d00.dat"
    d00_raw = load_raw_matrix(d00_path, expected_transposed=True)
    d00_feats = construct_run_window_features(d00_raw, window_size=window_size)
    d00_labels = np.zeros(len(d00_feats), dtype=int)

    n_d00 = len(d00_feats)
    split_d00 = int(n_d00 * train_ratio)
    x_train_parts.append(d00_feats[:split_d00])
    y_train_parts.append(d00_labels[:split_d00])
    x_val_parts.append(d00_feats[split_d00:])
    y_val_parts.append(d00_labels[split_d00:])

    # 2. Fault Training Runs: d01.dat to d21.dat (480 samples each)
    for f_id in range(1, 22):
        f_path = data_dir / f"d{f_id:02d}.dat"
        f_raw = load_raw_matrix(f_path, expected_transposed=False)
        f_feats = construct_run_window_features(f_raw, window_size=window_size)

        # Separate pre-fault (normal) and post-injection fault windows
        # t < 20: pure normal
        # t = 20, 21: transition windows (EXCLUDED)
        # t >= 22: pure fault
        pre_normal = f_feats[:20]
        pre_labels = np.zeros(len(pre_normal), dtype=int)

        # Transition windows: indices 20 and 21 (2 windows excluded per fault run)
        total_excluded_transitions += 2

        pure_fault = f_feats[22:]
        pure_labels = np.full(len(pure_fault), f_id, dtype=int)

        # Split pre_normal chronologically (75% train, 25% val)
        n_pre = len(pre_normal)
        s_pre = int(n_pre * train_ratio)
        x_train_parts.append(pre_normal[:s_pre])
        y_train_parts.append(pre_labels[:s_pre])
        x_val_parts.append(pre_normal[s_pre:])
        y_val_parts.append(pre_labels[s_pre:])

        # Split pure_fault chronologically (75% train, 25% val)
        n_fault = len(pure_fault)
        s_fault = int(n_fault * train_ratio)
        x_train_parts.append(pure_fault[:s_fault])
        y_train_parts.append(pure_labels[:s_fault])
        x_val_parts.append(pure_fault[s_fault:])
        y_val_parts.append(pure_labels[s_fault:])

    # 3. Independent Test Runs: d00_te.dat (all normal) + d01_te.dat to d21_te.dat
    d00_te_path = data_dir / "d00_te.dat"
    d00_te_raw = load_raw_matrix(d00_te_path, expected_transposed=False)
    d00_te_feats = construct_run_window_features(d00_te_raw, window_size=window_size)
    d00_te_labels = np.zeros(len(d00_te_feats), dtype=int)
    x_test_parts.append(d00_te_feats)
    y_test_parts.append(d00_te_labels)

    for f_id in range(1, 22):
        te_path = data_dir / f"d{f_id:02d}_te.dat"
        te_raw = load_raw_matrix(te_path, expected_transposed=False)
        te_feats = construct_run_window_features(te_raw, window_size=window_size)
        te_labels = np.zeros(len(te_feats), dtype=int)
        te_labels[160:] = f_id  # Fault introduced at sample 160
        x_test_parts.append(te_feats)
        y_test_parts.append(te_labels)

    # Assemble DataFrames
    x_train = pd.DataFrame(np.vstack(x_train_parts), columns=CANONICAL_FAULT_FEATURES)
    y_train = np.concatenate(y_train_parts)
    x_val = pd.DataFrame(np.vstack(x_val_parts), columns=CANONICAL_FAULT_FEATURES)
    y_val = np.concatenate(y_val_parts)
    x_test = pd.DataFrame(np.vstack(x_test_parts), columns=CANONICAL_FAULT_FEATURES)
    y_test = np.concatenate(y_test_parts)

    metadata = {
        "dataset_name": "Tennessee Eastman Process (TEP) 22-Class Benchmark",
        "origin": "Prof. Richard Braatz (UIUC/MIT) / Downs & Vogel (1993)",
        "num_classes": 22,
        "features_count": len(CANONICAL_FAULT_FEATURES),
        "window_size": window_size,
        "sampling_interval_minutes": 3.0,
        "train_samples": len(x_train),
        "val_samples": len(x_val),
        "test_samples": len(x_test),
        "excluded_transition_windows": total_excluded_transitions,
        "fault_injection_train_sample": 20,
        "fault_injection_test_sample": 160,
    }

    logger.info(
        "Loaded TEP multiclass dataset: train=%d, val=%d, test=%d, features=%d, excluded_transitions=%d",
        len(x_train),
        len(x_val),
        len(x_test),
        len(CANONICAL_FAULT_FEATURES),
        total_excluded_transitions,
    )

    return TEPMulticlassSplit(
        x_train=x_train,
        y_train=y_train,
        x_val=x_val,
        y_val=y_val,
        x_test=x_test,
        y_test=y_test,
        feature_names=CANONICAL_FAULT_FEATURES,
        class_mapping=FAULT_DESCRIPTIONS,
        metadata=metadata,
    )

