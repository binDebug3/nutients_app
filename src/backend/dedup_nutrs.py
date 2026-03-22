"""
Deduplicate nutrient unit map files by the first column value.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import pandas as pd

from logging_setup import configure_backend_logging


LOGGER = configure_backend_logging("dedup_nutrs")
TARGET_SUFFIX = "_nutrients_unit_map.csv"


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed argument values.
    """
    script_path = Path(__file__).resolve()
    project_root = script_path.parents[2]
    default_data_root = project_root.parent / "data" / "nutrients"

    parser = argparse.ArgumentParser(
        description=(
            "Recursively find *_nutrients_unit_map.csv files and remove duplicate "
            "rows by first-column value in place."
        )
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=default_data_root,
        help="Root directory to recursively search for nutrient unit map CSV files.",
    )
    return parser.parse_args()


def find_target_files(data_root: Path) -> List[Path]:
    """
    Recursively find all target CSV files under a root directory.

    Args:
        data_root: Root directory to search.

    Returns:
        List[Path]: Matching CSV file paths.
    """
    LOGGER.info("Searching for target CSV files under: %s", data_root)
    return sorted(
        path for path in data_root.rglob(f"*{TARGET_SUFFIX}") if path.is_file()
    )


def clear(file_path: Path) -> int:
    """
    Remove duplicate rows using the first column as the uniqueness key.

    Args:
        file_path: CSV file path to process.

    Returns:
        int: Number of duplicate rows removed.
    """
    LOGGER.info("Processing file: %s", file_path)
    frame = pd.read_csv(file_path, encoding="utf-8")

    if frame.empty or len(frame.columns) == 0:
        LOGGER.info("Skipping empty file or file without columns: %s", file_path)
        return 0

    first_column_name = frame.columns[0]
    original_count = len(frame)
    deduplicated = frame.drop_duplicates(subset=[first_column_name], keep="first")
    removed_count = original_count - len(deduplicated)

    deduplicated.to_csv(file_path, index=False, encoding="utf-8")
    LOGGER.info("Removed %d duplicate rows from %s", removed_count, file_path)
    return removed_count


def main() -> None:
    """
    Execute recursive deduplication for matching nutrient unit map CSV files.
    """
    LOGGER.info("Starting nutrient unit map deduplication")

    args = parse_args()
    data_root = args.data_root.resolve()

    if not data_root.exists() or not data_root.is_dir():
        raise FileNotFoundError(
            f"Data root does not exist or is not a directory: {data_root}"
        )

    target_files = find_target_files(data_root)
    total_removed = 0

    for file_path in target_files:
        total_removed += clear(file_path)

    LOGGER.info("Finished. Files processed: %d", len(target_files))
    LOGGER.info("Total duplicates removed: %d", total_removed)


if __name__ == "__main__":
    main()
