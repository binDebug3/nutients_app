"""Unit tests for dedup_nutrs.py."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def test_find_target_files_returns_matching_csvs(
    load_backend_module: object,
    tmp_path: Path,
) -> None:
    """Find only files ending with the configured nutrient map suffix."""
    module = load_backend_module("dedup_nutrs")
    first_match = tmp_path / "a_nutrients_unit_map.csv"
    second_match = tmp_path / "nested" / "b_nutrients_unit_map.csv"
    second_match.parent.mkdir()
    first_match.write_text("id,name\n1,Protein\n", encoding="utf-8")
    second_match.write_text("id,name\n2,Fiber\n", encoding="utf-8")
    (tmp_path / "ignored.csv").write_text("id,name\n3,Fat\n", encoding="utf-8")

    result = module.find_target_files(tmp_path)

    assert result == [first_match, second_match]


def test_clear_removes_duplicate_rows_by_first_column(
    load_backend_module: object,
    tmp_path: Path,
) -> None:
    """Drop duplicate rows while preserving the first row for each key."""
    module = load_backend_module("dedup_nutrs")
    csv_path = tmp_path / "sample_nutrients_unit_map.csv"
    pd.DataFrame(
        {"id": [1, 1, 2], "name": ["Protein", "Protein duplicate", "Fiber"]}
    ).to_csv(csv_path, index=False, encoding="utf-8")

    removed = module.clear(csv_path)
    remaining = pd.read_csv(csv_path)

    assert removed == 1
    assert remaining["id"].tolist() == [1, 2]


def test_main_processes_all_matching_files(
    load_backend_module: object,
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    """Run main against a temporary data root and process each target file once."""
    module = load_backend_module("dedup_nutrs")
    first_match = tmp_path / "a_nutrients_unit_map.csv"
    second_match = tmp_path / "b_nutrients_unit_map.csv"
    first_match.write_text("id\n1\n", encoding="utf-8")
    second_match.write_text("id\n2\n", encoding="utf-8")
    monkeypatch.setattr(
        module, "parse_args", lambda: argparse.Namespace(data_root=tmp_path)
    )

    seen_files: list[Path] = []
    monkeypatch.setattr(
        module,
        "clear",
        lambda path: seen_files.append(path) or 0,
    )

    module.main()

    assert seen_files == [first_match, second_match]
