"""Check and resolve discrepancies across nutrient-unit map files.

This script compares `_nutrient_unit_map.csv` across each non-backup folder under
the nutrients data directory, then resolves differences by applying a consensus row
for each `nutrient_column`.
"""

from __future__ import annotations

import argparse
import logging
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

SCRIPT_PATH = Path(__file__).resolve()
DEFAULT_NUTRIENTS_ROOT = SCRIPT_PATH.parents[3] / "data" / "nutrients"
DEFAULT_MAP_FILENAME = "_nutrient_unit_map.csv"
REQUIRED_COLUMNS = ["nutrient_id", "nutrient_name", "nutrient_column", "unit_name"]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments for nutrients root discovery and write behavior.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Compare nutrient-unit maps across nutrient dataset folders and "
            "resolve discrepancies."
        )
    )
    parser.add_argument(
        "--nutrients-root",
        type=Path,
        default=DEFAULT_NUTRIENTS_ROOT,
        help="Root path containing nutrient dataset folders.",
    )
    parser.add_argument(
        "--map-filename",
        type=str,
        default=DEFAULT_MAP_FILENAME,
        help="Map filename expected in each dataset folder.",
    )
    parser.add_argument(
        "--ignore-folders",
        nargs="*",
        default=["backup"],
        help="Folder names to skip (case-insensitive).",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only report discrepancies; do not write resolved files.",
    )
    return parser.parse_args()


def list_dataset_folders(nutrients_root: Path, ignore_folders: List[str]) -> List[Path]:
    """List nutrient dataset folders that should be included in comparison.

    Args:
        nutrients_root: Root folder containing nutrient dataset subfolders.
        ignore_folders: Folder names to skip.

    Returns:
        Sorted dataset folders to process.

    Raises:
        FileNotFoundError: If nutrients_root does not exist.
    """
    log.info("Discovering dataset folders under %s", nutrients_root)

    if not nutrients_root.exists():
        raise FileNotFoundError(f"Nutrients root does not exist: {nutrients_root}")

    ignored = {name.strip().lower() for name in ignore_folders}
    folders = [
        folder
        for folder in nutrients_root.iterdir()
        if folder.is_dir() and folder.name.lower() not in ignored
    ]
    folders = sorted(folders, key=lambda path: path.name.lower())

    log.info("Found %d dataset folders after filtering", len(folders))
    return folders


def make_unique_nutrient_column_names(nutrients_df: pd.DataFrame) -> pd.DataFrame:
    """Ensure nutrient column names are unique by appending id where needed.

    Args:
        nutrients_df: Nutrient DataFrame with `id` and `name` columns.

    Returns:
        Copy with `nutrient_column` added.
    """
    log.info("Generating unique nutrient column names")
    result = nutrients_df.copy()
    duplicate_mask = result["name"].duplicated(keep=False)
    result["nutrient_column"] = result["name"]
    result.loc[duplicate_mask, "nutrient_column"] = result.loc[duplicate_mask].apply(
        lambda row: f"{row['name']} [id:{int(row['id'])}]", axis=1
    )
    return result


def build_map_from_nutrient_csv(nutrient_csv_path: Path) -> pd.DataFrame:
    """Build a nutrient-unit map from nutrient.csv.

    Args:
        nutrient_csv_path: Path to nutrient.csv.

    Returns:
        DataFrame with required map columns.
    """
    log.info("Building map from %s", nutrient_csv_path)
    nutrient_df = pd.read_csv(
        nutrient_csv_path,
        usecols=lambda col: col in {"id", "name", "unit_name", "nutrient_nbr"},
        encoding="utf-8",
        low_memory=False,
    )

    if "nutrient_nbr" in nutrient_df.columns:
        nutrient_nbr_series = pd.to_numeric(
            nutrient_df["nutrient_nbr"], errors="coerce"
        )
        nutrient_df["nutrient_id"] = nutrient_nbr_series.fillna(nutrient_df["id"])
    else:
        nutrient_df["nutrient_id"] = nutrient_df["id"]

    nutrient_df = make_unique_nutrient_column_names(nutrient_df)

    map_df = nutrient_df.rename(columns={"name": "nutrient_name"})[REQUIRED_COLUMNS]
    map_df = normalize_map_df(map_df)
    map_df = map_df.sort_values("nutrient_column").reset_index(drop=True)

    log.info("Built %d nutrient map rows from nutrient.csv", len(map_df))
    return map_df


def normalize_map_df(map_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize map DataFrame values for reliable comparison.

    Args:
        map_df: Input map DataFrame.

    Returns:
        Normalized map DataFrame with consistent dtypes and whitespace.
    """
    log.info("Normalizing nutrient map DataFrame")

    normalized = map_df.copy()
    for column in REQUIRED_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = pd.NA

    normalized = normalized[REQUIRED_COLUMNS]
    normalized["nutrient_id"] = (
        normalized["nutrient_id"]
        .astype("string")
        .fillna("")
        .str.strip()
        .str.replace(r"\.0+$", "", regex=True)
        .replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "<NA>": pd.NA})
    )

    for column in ["nutrient_name", "nutrient_column", "unit_name"]:
        normalized[column] = (
            normalized[column]
            .astype("string")
            .fillna("")
            .str.strip()
            .replace({"": pd.NA})
        )

    normalized = normalized.dropna(subset=["nutrient_column"]).drop_duplicates(
        subset=["nutrient_column"], keep="first"
    )
    return normalized.reset_index(drop=True)


def load_or_build_map(
    dataset_folder: Path, map_filename: str, check_only: bool
) -> pd.DataFrame:
    """Load an existing map file or build one from nutrient.csv when missing.

    Args:
        dataset_folder: Folder containing nutrient files.
        map_filename: Expected nutrient map filename.
        check_only: If true, avoid writing generated missing map files.

    Returns:
        Loaded or generated nutrient map DataFrame.

    Raises:
        FileNotFoundError: If both map and nutrient.csv are missing.
    """
    log.info("Preparing nutrient map for folder: %s", dataset_folder.name)

    map_path = dataset_folder / map_filename
    if map_path.exists():
        map_df = pd.read_csv(map_path, encoding="utf-8", low_memory=False)
        return normalize_map_df(map_df)

    nutrient_csv_path = dataset_folder / "nutrient.csv"
    if not nutrient_csv_path.exists():
        raise FileNotFoundError(
            f"Neither map file nor nutrient.csv found in folder: {dataset_folder}"
        )

    generated_map = build_map_from_nutrient_csv(nutrient_csv_path)
    if not check_only:
        generated_map.to_csv(map_path, index=False, encoding="utf-8")
        log.info("Created missing map file: %s", map_path)
    else:
        log.info("Map file missing in %s (check-only mode)", dataset_folder.name)

    return generated_map


def choose_consensus_value(value_source_pairs: List[tuple[Any, str]]) -> Any:
    """Choose a deterministic consensus value from source values.

    Args:
        value_source_pairs: Candidate values paired with source folder names.

    Returns:
        Consensus value, or pandas.NA if no usable value exists.
    """
    cleaned_pairs = [
        (value, source)
        for value, source in value_source_pairs
        if pd.notna(value) and str(value).strip() != ""
    ]
    cleaned_values = [value for value, _ in cleaned_pairs]
    if not cleaned_values:
        return pd.NA

    counts = Counter(cleaned_values)
    max_count = max(counts.values())
    tied_values = {value for value, count in counts.items() if count == max_count}

    if len(tied_values) == 1:
        return next(iter(tied_values))

    for value, _source in cleaned_pairs:
        if value in tied_values:
            return value

    return sorted(tied_values, key=lambda value: str(value))[0]


def resolve_discrepancies(
    folder_maps: Dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Resolve discrepancies and produce a single consensus map.

    Args:
        folder_maps: Mapping of folder name to normalized nutrient map DataFrame.

    Returns:
        Tuple of:
        - Resolved nutrient map DataFrame.
        - Discrepancy report DataFrame.
    """
    log.info("Resolving discrepancies across %d folder maps", len(folder_maps))

    records: List[pd.DataFrame] = []
    source_order = list(folder_maps.keys())
    for source_name, map_df in folder_maps.items():
        with_source = map_df.copy()
        with_source["source"] = source_name
        records.append(with_source)

    combined = pd.concat(records, ignore_index=True)

    resolved_rows: List[dict[str, Any]] = []
    discrepancy_rows: List[dict[str, Any]] = []

    for nutrient_column, group in combined.groupby("nutrient_column", dropna=False):
        id_values = group["nutrient_id"].tolist()
        name_values = group["nutrient_name"].tolist()
        unit_values = group["unit_name"].tolist()
        sources = group["source"].tolist()

        resolved_id = choose_consensus_value(list(zip(id_values, sources)))
        resolved_name = choose_consensus_value(list(zip(name_values, sources)))
        resolved_unit = choose_consensus_value(list(zip(unit_values, sources)))

        resolved_rows.append(
            {
                "nutrient_id": resolved_id,
                "nutrient_name": resolved_name,
                "nutrient_column": nutrient_column,
                "unit_name": resolved_unit,
            }
        )

        unique_ids = sorted({value for value in id_values if pd.notna(value)})
        unique_names = sorted({value for value in name_values if pd.notna(value)})
        unique_units = sorted({value for value in unit_values if pd.notna(value)})
        present_sources = sorted(group["source"].dropna().unique().tolist())

        has_conflict = any(
            [
                len(unique_ids) > 1,
                len(unique_names) > 1,
                len(unique_units) > 1,
                len(present_sources) != len(source_order),
            ]
        )
        if has_conflict:
            discrepancy_rows.append(
                {
                    "nutrient_column": nutrient_column,
                    "present_sources": ", ".join(present_sources),
                    "id_values": " | ".join(str(value) for value in unique_ids),
                    "name_values": " | ".join(str(value) for value in unique_names),
                    "unit_values": " | ".join(str(value) for value in unique_units),
                }
            )

    resolved_df = pd.DataFrame(resolved_rows)
    resolved_df = normalize_map_df(resolved_df)
    resolved_df = resolved_df.sort_values("nutrient_column").reset_index(drop=True)

    discrepancy_df = pd.DataFrame(discrepancy_rows)
    if not discrepancy_df.empty:
        discrepancy_df = discrepancy_df.sort_values("nutrient_column").reset_index(
            drop=True
        )

    log.info("Resolved map rows: %d", len(resolved_df))
    log.info("Detected discrepancy rows: %d", len(discrepancy_df))
    return resolved_df, discrepancy_df


def write_resolved_maps(
    nutrients_root: Path,
    dataset_folders: List[Path],
    map_filename: str,
    resolved_df: pd.DataFrame,
) -> None:
    """Write the resolved map into each dataset folder.

    Args:
        nutrients_root: Nutrients root folder.
        dataset_folders: Dataset folders to update.
        map_filename: Target map filename.
        resolved_df: Consensus nutrient map to write.
    """
    log.info("Writing resolved maps under %s", nutrients_root)

    for folder in dataset_folders:
        output_path = folder / map_filename
        resolved_df.to_csv(output_path, index=False, encoding="utf-8")
        log.info("Wrote resolved map: %s", output_path)


def main() -> None:
    """Compare and resolve nutrient map discrepancies across dataset folders."""
    log.info("Starting nutrient map comparison")

    args = parse_args()
    nutrients_root = args.nutrients_root.resolve()

    dataset_folders = list_dataset_folders(nutrients_root, args.ignore_folders)
    if not dataset_folders:
        raise FileNotFoundError(
            "No dataset folders found after filtering ignored folders."
        )

    folder_maps: Dict[str, pd.DataFrame] = {}
    for folder in dataset_folders:
        folder_maps[folder.name] = load_or_build_map(
            folder, args.map_filename, args.check_only
        )

    resolved_df, discrepancy_df = resolve_discrepancies(folder_maps)

    if discrepancy_df.empty:
        log.info("No discrepancies found across compared folders")
    else:
        log.info("Discrepancies found and resolved with consensus values")

    if args.check_only:
        log.info("Check-only mode enabled; no files were modified")
    else:
        write_resolved_maps(
            nutrients_root, dataset_folders, args.map_filename, resolved_df
        )

    print("=== Comparison Summary ===")
    print(f"Nutrients root: {nutrients_root}")
    print(f"Dataset folders compared: {len(dataset_folders)}")
    print(f"Resolved map rows: {len(resolved_df)}")
    print(f"Discrepancy rows: {len(discrepancy_df)}")
    if not discrepancy_df.empty:
        print("\nFirst discrepancy examples:")
        print(discrepancy_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
