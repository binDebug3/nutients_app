"""Unit tests for join.py."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def test_discover_source_files_ignores_backup(
    load_backend_module: object,
    tmp_path: Path,
) -> None:
    """Discover only processed nutrient files that are outside backup folders."""
    module = load_backend_module("join")
    first_dir = tmp_path / "FoodData_A"
    second_dir = tmp_path / "backup"
    first_dir.mkdir()
    second_dir.mkdir()
    (first_dir / "_processed_food_nutrients.csv").write_text(
        "fdc_id\n1\n", encoding="utf-8"
    )
    (second_dir / "_processed_food_nutrients.csv").write_text(
        "fdc_id\n2\n", encoding="utf-8"
    )

    files = module.discover_source_files(tmp_path)

    assert files == [first_dir / "_processed_food_nutrients.csv"]


def test_deduplicate_rows_keeps_richest_row_per_food(
    load_backend_module: object,
) -> None:
    """Keep the row with the highest non-null count for each fdc_id."""
    module = load_backend_module("join")
    merged = pd.DataFrame(
        {
            "fdc_id": [1, 1, 2],
            "food_name": ["Apple", "Apple", "Pear"],
            "protein": [1.0, 1.0, 2.0],
            "fiber": [pd.NA, 3.0, 4.0],
            "_source_dataset": ["a", "b", "b"],
        }
    )

    result = module.deduplicate_rows(merged)

    assert result["fdc_id"].tolist() == [1, 2]
    assert result.loc[result["fdc_id"] == 1, "fiber"].iloc[0] == 3.0
    assert "_source_dataset" not in result.columns


def test_clean_output_table_drops_sparse_rows_and_fills_missing(
    load_backend_module: object,
) -> None:
    """Remove sparse rows and convert remaining missing values to zero."""
    module = load_backend_module("join")
    table = pd.DataFrame(
        {
            "fdc_id": [1, 2],
            "food_name": ["Apple", "Pear"],
            "serving_size": ["1 cup", "1 fruit"],
            "Protein": ["nan", 2.0],
            "Fiber": [1.0, pd.NA],
            "Fat": [1.0, pd.NA],
        }
    )

    cleaned = module.clean_output_table(table)

    assert cleaned["fdc_id"].tolist() == [1]
    assert cleaned["Protein"].iloc[0] == 0


def test_validate_source_count_rejects_missing_files(
    load_backend_module: object,
) -> None:
    """Fail when too few source files are found and partial execution is disabled."""
    module = load_backend_module("join")

    with pytest.raises(FileNotFoundError):
        module.validate_source_count([], expected_files=2, allow_partial=False)
