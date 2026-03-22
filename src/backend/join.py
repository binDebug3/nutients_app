"""
Join processed food nutrient tables across FoodData Central dataset folders.

This script discovers `_processed_food_nutrients.csv` files under `data/nutrients`,
ignores the `backup` folder, merges rows, removes duplicate foods, and writes a
single consolidated CSV file.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import pandas as pd

from logging_setup import configure_backend_logging

log = configure_backend_logging("join")

_SCRIPT_PATH = Path(__file__).resolve()
_DEFAULT_DATA_ROOT = _SCRIPT_PATH.parents[3] / "data" / "nutrients"
_DEFAULT_OUTPUT_PATH = _DEFAULT_DATA_ROOT / "food_nutrients.csv"
_SOURCE_FILE_NAME = "_processed_food_nutrients.csv"


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed CLI namespace.
    """
    log.info("Parsing command-line arguments")
    parser = argparse.ArgumentParser(
        description=(
            "Join processed nutrient tables from data/nutrients/* folders into one CSV "
            "without duplicate foods."
        )
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=_DEFAULT_DATA_ROOT,
        help="Root nutrients directory containing FoodData_Central_* folders.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT_PATH,
        help="Output CSV path for the merged food nutrients table.",
    )
    parser.add_argument(
        "--expected-files",
        type=int,
        default=3,
        help="Expected count of source files to join.",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow running when fewer than --expected-files sources are found.",
    )
    return parser.parse_args()


def list_dataset_dirs(data_root: Path) -> List[Path]:
    """
    Return dataset folders under data_root, excluding backup directories.

    Args:
        data_root: Root folder containing nutrient dataset subfolders.

    Returns:
        Sorted list of dataset directories to inspect.
    """
    log.info("Listing dataset directories under %s", data_root)
    if not data_root.exists():
        raise FileNotFoundError(f"Data root not found: {data_root}")

    dataset_dirs = [
        folder
        for folder in data_root.iterdir()
        if folder.is_dir() and folder.name.lower() != "backup"
    ]
    dataset_dirs.sort(key=lambda path: path.name.lower())
    return dataset_dirs


def discover_source_files(data_root: Path) -> List[Path]:
    """
    Discover `_processed_food_nutrients.csv` in each dataset directory.

    Args:
        data_root: Root folder containing nutrient dataset subfolders.

    Returns:
        Sorted list of source CSV file paths.
    """
    log.info("Discovering source files named %s", _SOURCE_FILE_NAME)
    source_files: List[Path] = []
    for dataset_dir in list_dataset_dirs(data_root):
        candidate = dataset_dir / _SOURCE_FILE_NAME
        if candidate.exists():
            source_files.append(candidate)

    source_files.sort(key=lambda path: path.as_posix().lower())
    log.info("Discovered %d source file(s)", len(source_files))
    return source_files


def load_tables(source_files: List[Path]) -> List[pd.DataFrame]:
    """
    Read source CSV files into DataFrames.

    Args:
        source_files: Paths of source CSV files to read.

    Returns:
        List of loaded DataFrames.
    """
    log.info("Loading %d source table(s)", len(source_files))
    tables: List[pd.DataFrame] = []
    for source_path in source_files:
        table = pd.read_csv(source_path, low_memory=False)
        table["_source_dataset"] = source_path.parent.name
        log.info("Loaded %s with %d row(s)", source_path, len(table))
        tables.append(table)
    return tables


def deduplicate_rows(merged: pd.DataFrame) -> pd.DataFrame:
    """
    Remove duplicate foods while preserving the richest row per food id.

    Args:
        merged: Concatenated food nutrients DataFrame.

    Returns:
        Deduplicated DataFrame.
    """
    log.info("Deduplicating merged table with %d row(s)", len(merged))
    if "fdc_id" in merged.columns:
        enriched = merged.copy()
        enriched["_non_null_count"] = enriched.notna().sum(axis=1)
        enriched = enriched.sort_values(
            ["fdc_id", "_non_null_count"], ascending=[True, False]
        )
        deduplicated = enriched.drop_duplicates(subset=["fdc_id"], keep="first")
        deduplicated = deduplicated.drop(columns=["_non_null_count"])
        deduplicated = deduplicated.sort_values("fdc_id")
    else:
        deduplicated = merged.drop_duplicates().copy()

    deduplicated = deduplicated.drop(columns=["_source_dataset"], errors="ignore")
    deduplicated = deduplicated.reset_index(drop=True)
    log.info("Deduplicated row count: %d", len(deduplicated))
    return deduplicated


def clean_output_table(table: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize missing values and drop sparse rows.

    Rows with 4 or fewer nonempty values are removed. Remaining missing values,
    including string values such as "nan", are converted to 0.

    Args:
        table: Table to clean.

    Returns:
        Cleaned table ready for output.
    """
    log.info("Cleaning output table with %d row(s)", len(table))

    cleaned = table.copy()
    cleaned = cleaned.replace(to_replace=r"^\s*nan\s*$", value=pd.NA, regex=True)
    cleaned = cleaned.replace(to_replace=r"^\s*$", value=pd.NA, regex=True)

    nonempty_counts = cleaned.notna().sum(axis=1)
    filtered = cleaned.loc[nonempty_counts > 4].copy()
    removed_rows = len(cleaned) - len(filtered)
    log.info("Dropped %d sparse row(s) with <= 4 nonempty columns", removed_rows)

    filtered = filtered.fillna(0)
    log.info("Converted remaining NaN values to 0")
    return filtered


def validate_source_count(
    source_files: List[Path], expected_files: int, allow_partial: bool
) -> None:
    """
    Validate number of discovered source files.

    Args:
        source_files: Discovered source file paths.
        expected_files: Required source count.
        allow_partial: Whether to proceed with fewer files.
    """
    log.info("Validating source file count")
    if len(source_files) >= expected_files:
        return

    message = (
        f"Expected at least {expected_files} source files named "
        f"'{_SOURCE_FILE_NAME}', found {len(source_files)}."
    )
    if allow_partial:
        log.warning("%s Proceeding due to --allow-partial.", message)
        return

    raise FileNotFoundError(message)


def main() -> None:
    """
    Join processed food nutrient files and write the consolidated CSV.
    """
    log.info("Starting join workflow")
    args = parse_args()
    data_root = args.data_root.resolve()
    output_path = args.output.resolve()

    source_files = discover_source_files(data_root)
    validate_source_count(
        source_files=source_files,
        expected_files=args.expected_files,
        allow_partial=args.allow_partial,
    )

    if not source_files:
        raise FileNotFoundError(
            f"No source files named '{_SOURCE_FILE_NAME}' were found in {data_root}."
        )

    merged = pd.concat(load_tables(source_files), ignore_index=True, sort=False)
    deduplicated = deduplicate_rows(merged)
    cleaned = clean_output_table(deduplicated)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(output_path, index=False, encoding="utf-8")

    log.info("Wrote merged food nutrients file: %s", output_path)
    log.info("Input rows: %d", len(merged))
    log.info("Output rows after dedupe: %d", len(deduplicated))
    log.info("Output rows after filtering/cleanup: %d", len(cleaned))


if __name__ == "__main__":
    main()
