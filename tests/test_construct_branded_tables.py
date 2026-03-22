"""Unit tests for construct_branded_tables.py."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def test_read_field_descriptions_and_validate_schema(
    load_backend_module: object,
    monkeypatch: object,
    capsys: object,
) -> None:
    """Parse workbook definitions and warn for missing required fields."""
    module = load_backend_module("construct_branded_tables")
    workbook_frame = pd.DataFrame(
        [
            ["food", "", "Food table"],
            ["", "fdc_id", "id"],
            ["", "description", "desc"],
        ]
    )
    monkeypatch.setattr(module.pd, "read_excel", lambda *args, **kwargs: workbook_frame)

    definitions = module.read_field_descriptions(Path("dummy.xlsx"))
    module.validate_schema(definitions, {"food": {"fdc_id", "description", "brand"}})
    captured = capsys.readouterr()

    assert definitions == {"food": {"fdc_id", "description"}}
    assert "missing fields" in captured.err.lower()


def test_format_serving_size_prefers_household_text(
    load_backend_module: object,
) -> None:
    """Use household serving text before reconstructing serving size from parts."""
    module = load_backend_module("construct_branded_tables")
    row = pd.Series(
        {
            "household_serving_fulltext": "2 cookies",
            "serving_size": 30,
            "serving_size_unit": "g",
        }
    )

    assert module.format_serving_size(row) == "2 cookies"


def test_load_serving_sizes_formats_rows(
    load_backend_module: object, monkeypatch: object
) -> None:
    """Load branded food serving size columns and return the expected projection."""
    module = load_backend_module("construct_branded_tables")
    branded_frame = pd.DataFrame(
        {
            "fdc_id": [1],
            "brand_owner": ["Owner"],
            "brand_name": ["Brand"],
            "branded_food_category": ["Snacks"],
            "ingredients": ["Salt"],
            "serving_size": [30.0],
            "serving_size_unit": ["g"],
            "household_serving_fulltext": [None],
        }
    )
    monkeypatch.setattr(module.pd, "read_csv", lambda *args, **kwargs: branded_frame)

    result = module.load_serving_sizes(Path("branded_food.csv"))

    assert result.to_dict("records") == [
        {
            "fdc_id": 1,
            "brand_owner": "Owner",
            "brand_name": "Brand",
            "branded_food_category": "Snacks",
            "ingredients": "Salt",
            "serving_size": "30 g",
        }
    ]


def test_load_nutrient_lookup_adds_unique_names(
    load_backend_module: object,
    monkeypatch: object,
) -> None:
    """Load nutrient lookup rows and disambiguate duplicate nutrient names."""
    module = load_backend_module("construct_branded_tables")
    nutrient_frame = pd.DataFrame(
        {
            "id": [1, 2],
            "name": ["Protein", "Protein"],
            "unit_name": ["g", "g"],
        }
    )
    monkeypatch.setattr(module.pd, "read_csv", lambda *args, **kwargs: nutrient_frame)

    result = module.load_nutrient_lookup(Path("nutrient.csv"))

    assert result["nutrient_column"].tolist() == ["Protein [id:1]", "Protein [id:2]"]


def test_build_nutrient_wide_aggregates_duplicate_pairs(
    load_backend_module: object,
) -> None:
    """Average duplicate nutrient rows before pivoting into wide format."""
    module = load_backend_module("construct_branded_tables")
    nutrient_lookup = pd.DataFrame(
        {
            "nutrient_id": [1, 2],
            "nutrient_column": ["Protein", "Fiber"],
        }
    )
    food_nutrient_frame = pd.DataFrame(
        {
            "fdc_id": [100, 100, 100, 200],
            "nutrient_id": [1, 1, 2, 1],
            "amount": [10.0, 14.0, 5.0, 7.0],
        }
    )

    original_read_csv = module.pd.read_csv
    module.pd.read_csv = lambda *args, **kwargs: food_nutrient_frame
    try:
        result = module.build_nutrient_wide(Path("food_nutrient.csv"), nutrient_lookup)
    finally:
        module.pd.read_csv = original_read_csv

    protein_for_first_food = result.loc[result["fdc_id"] == 100, "Protein"].iloc[0]
    assert protein_for_first_food == 12.0
