"""Unit tests for construct_tables.py."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def test_read_field_descriptions_parses_table_groups(
    load_backend_module: object,
    monkeypatch: object,
) -> None:
    """Parse grouped workbook rows into a table-to-fields mapping."""
    module = load_backend_module("construct_tables")
    workbook_frame = pd.DataFrame(
        [
            ["food", "", "Food table"],
            ["", "fdc_id", "id"],
            ["", "description", "desc"],
        ]
    )
    monkeypatch.setattr(module.pd, "read_excel", lambda *args, **kwargs: workbook_frame)

    result = module.read_field_descriptions(Path("dummy.xlsx"))

    assert result == {"food": {"fdc_id", "description"}}


def test_format_serving_size_includes_modifier_and_gram_weight(
    load_backend_module: object,
) -> None:
    """Append modifier and gram weight details when they are available."""
    module = load_backend_module("construct_tables")
    row = pd.Series(
        {
            "portion_description": "1 cup",
            "measure_unit_name": "cup",
            "modifier": "chopped",
            "amount": 1.0,
            "gram_weight": 42.0,
        }
    )

    assert module.format_serving_size(row) == "1 cup, chopped (42 g)"


def test_make_unique_nutrient_column_names_appends_ids(
    load_backend_module: object,
) -> None:
    """Append ids to duplicate nutrient names while leaving unique names unchanged."""
    module = load_backend_module("construct_tables")
    nutrients = pd.DataFrame({"id": [1, 2, 3], "name": ["Protein", "Protein", "Fiber"]})

    result = module.make_unique_nutrient_column_names(nutrients)

    assert result["nutrient_column"].tolist() == [
        "Protein [id:1]",
        "Protein [id:2]",
        "Fiber",
    ]


def test_main_writes_food_and_unit_tables(
    load_backend_module: object,
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    """Run the main workflow with mocked inputs and capture both CSV outputs."""
    module = load_backend_module("construct_tables")
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    for file_name in [
        "Download API Field Descriptions.xlsx",
        "food.csv",
        "food_portion.csv",
        "food_nutrient.csv",
        "nutrient.csv",
        "measure_unit.csv",
    ]:
        (input_dir / file_name).touch()

    output_food_table = tmp_path / "out" / "food.csv"
    output_unit_map = tmp_path / "out" / "unit_map.csv"
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: argparse.Namespace(
            input_dir=input_dir,
            output_food_table=output_food_table,
            output_unit_map=output_unit_map,
        ),
    )
    monkeypatch.setattr(
        module,
        "read_field_descriptions",
        lambda _path: {
            "food": {"fdc_id", "description"},
            "food_portion": {
                "fdc_id",
                "seq_num",
                "amount",
                "measure_unit_id",
                "portion_description",
                "modifier",
                "gram_weight",
            },
            "food_nutrient": {"fdc_id", "nutrient_id", "amount"},
            "nutrient": {"id", "name", "unit_name", "nutrient_nbr"},
            "measure_unit": {"id", "name"},
        },
    )

    csv_lookup = {
        "food.csv": pd.DataFrame({"fdc_id": [1], "description": ["Apple"]}),
        "food_portion.csv": pd.DataFrame(
            {
                "fdc_id": [1],
                "seq_num": [1],
                "amount": [1.0],
                "measure_unit_id": [10],
                "portion_description": ["1 cup"],
                "modifier": [None],
                "gram_weight": [100.0],
            }
        ),
        "food_nutrient.csv": pd.DataFrame(
            {"fdc_id": [1], "nutrient_id": [100], "amount": [4.0]}
        ),
        "nutrient.csv": pd.DataFrame(
            {
                "id": [10],
                "name": ["Protein"],
                "unit_name": ["g"],
                "nutrient_nbr": [100],
            }
        ),
        "measure_unit.csv": pd.DataFrame({"id": [10], "name": ["cup"]}),
    }
    monkeypatch.setattr(
        module.pd,
        "read_csv",
        lambda path, *args, **kwargs: csv_lookup[Path(path).name].copy(),
    )

    written_frames: dict[str, pd.DataFrame] = {}
    original_to_csv = pd.DataFrame.to_csv

    def capture_to_csv(
        self: pd.DataFrame,
        path: Path,
        index: bool = False,
        encoding: str | None = None,
    ) -> None:
        """Capture DataFrame CSV writes for assertions.

        Args:
            self: DataFrame being written.
            path: Output path.
            index: Whether index output is enabled.
            encoding: Output encoding.
        """
        _ = (index, encoding)
        written_frames[Path(path).name] = self.copy()

    monkeypatch.setattr(pd.DataFrame, "to_csv", capture_to_csv)
    try:
        module.main()
    finally:
        monkeypatch.setattr(pd.DataFrame, "to_csv", original_to_csv)

    assert written_frames["food.csv"]["food_name"].tolist() == ["Apple"]
    assert written_frames["unit_map.csv"]["nutrient_column"].tolist() == ["Protein"]
