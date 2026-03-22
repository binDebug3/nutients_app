"""Unit tests for compare.py."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def test_list_dataset_folders_filters_backup_and_sorts(
    load_backend_module: object,
    tmp_path: Path,
) -> None:
    """Return only dataset directories that are not ignored."""
    module = load_backend_module("compare")
    (tmp_path / "beta").mkdir()
    (tmp_path / "backup").mkdir()
    (tmp_path / "Alpha").mkdir()
    (tmp_path / "notes.csv").write_text("ignored", encoding="utf-8")

    folders = module.list_dataset_folders(tmp_path, ["backup"])

    assert [folder.name for folder in folders] == ["Alpha", "beta"]


def test_list_dataset_folders_raises_for_missing_root(
    load_backend_module: object,
    tmp_path: Path,
) -> None:
    """Raise FileNotFoundError when the nutrients root does not exist."""
    module = load_backend_module("compare")

    with pytest.raises(FileNotFoundError):
        module.list_dataset_folders(tmp_path / "missing", ["backup"])


def test_normalize_map_df_cleans_values_and_removes_duplicate_columns(
    load_backend_module: object,
) -> None:
    """Normalize ids, strip whitespace, and keep the first nutrient column row."""
    module = load_backend_module("compare")
    frame = pd.DataFrame(
        {
            "nutrient_id": ["10.0", " 10 ", None],
            "nutrient_name": [" Protein ", "Protein", "Fiber"],
            "nutrient_column": [" Protein ", "Protein", None],
            "unit_name": [" g ", "g", "g"],
        }
    )

    normalized = module.normalize_map_df(frame)

    assert normalized.to_dict("records") == [
        {
            "nutrient_id": "10",
            "nutrient_name": "Protein",
            "nutrient_column": "Protein",
            "unit_name": "g",
        }
    ]


def test_load_or_build_map_creates_missing_map_file(
    load_backend_module: object,
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    """Build and persist a map file when nutrient.csv exists but the map is missing."""
    module = load_backend_module("compare")
    dataset_folder = tmp_path / "dataset"
    dataset_folder.mkdir()
    nutrient_csv_path = dataset_folder / "nutrient.csv"
    nutrient_csv_path.write_text("id,name,unit_name\n1,Protein,g\n", encoding="utf-8")

    generated_frame = pd.DataFrame(
        {
            "nutrient_id": ["1"],
            "nutrient_name": ["Protein"],
            "nutrient_column": ["Protein"],
            "unit_name": ["g"],
        }
    )
    monkeypatch.setattr(
        module, "build_map_from_nutrient_csv", lambda _: generated_frame
    )

    result = module.load_or_build_map(dataset_folder, "_nutrient_unit_map.csv", False)

    assert result.equals(generated_frame)
    assert (dataset_folder / "_nutrient_unit_map.csv").exists()


def test_choose_consensus_value_prefers_first_tied_value(
    load_backend_module: object,
) -> None:
    """Resolve ties by the first value encountered among the tied candidates."""
    module = load_backend_module("compare")

    value = module.choose_consensus_value(
        [("g", "folder_b"), ("mg", "folder_a"), ("mg", "folder_c"), ("g", "folder_d")]
    )

    assert value == "g"


def test_resolve_discrepancies_builds_consensus_and_report(
    load_backend_module: object,
) -> None:
    """Resolve conflicting maps and report the conflicting nutrient columns."""
    module = load_backend_module("compare")
    folder_maps = {
        "a": pd.DataFrame(
            {
                "nutrient_id": ["1", "2"],
                "nutrient_name": ["Protein", "Fiber"],
                "nutrient_column": ["Protein", "Fiber"],
                "unit_name": ["g", "g"],
            }
        ),
        "b": pd.DataFrame(
            {
                "nutrient_id": ["1", "2"],
                "nutrient_name": ["Protein", "Fiber"],
                "nutrient_column": ["Protein", "Fiber"],
                "unit_name": ["mg", "g"],
            }
        ),
    }

    resolved, report = module.resolve_discrepancies(folder_maps)

    protein_row = resolved.loc[resolved["nutrient_column"] == "Protein"].iloc[0]
    assert protein_row["unit_name"] == "g"
    assert report["nutrient_column"].tolist() == ["Protein"]
