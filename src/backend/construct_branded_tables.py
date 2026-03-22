"""Build wide food-nutrient and nutrient-unit tables from FoodData Central branded food CSVs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from logging_setup import configure_backend_logging

log = configure_backend_logging("construct_branded_tables")

_SCRIPT_PATH = Path(__file__).resolve()
_PROJECT_ROOT = _SCRIPT_PATH.parents[2]
_DEFAULT_INPUT_DIR = (
    _SCRIPT_PATH.parents[3]
    / "data"
    / "nutrients"
    / ("FoodData_Central_branded_food_csv_2025-12-18")
)
_DEFAULT_FOOD_TABLE = _PROJECT_ROOT / "processed_branded_food_nutrients.csv"
_DEFAULT_UNIT_MAP = _PROJECT_ROOT / "branded_nutrient_unit_map.csv"

FIXED_COLS = [
    "fdc_id",
    "food_name",
    "brand_owner",
    "brand_name",
    "branded_food_category",
    "ingredients",
    "serving_size",
]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed namespace with input_dir, output_food_table, and output_unit_map paths.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Build (1) a wide food-nutrient table with one nutrient per column and "
            "(2) a nutrient-to-unit mapping table from FoodData Central branded food CSVs."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=_DEFAULT_INPUT_DIR,
        help="Directory containing branded food CSV files and the field descriptions workbook.",
    )
    parser.add_argument(
        "--output-food-table",
        type=Path,
        default=_DEFAULT_FOOD_TABLE,
        help="Output CSV path for the wide branded food-nutrient table.",
    )
    parser.add_argument(
        "--output-unit-map",
        type=Path,
        default=_DEFAULT_UNIT_MAP,
        help="Output CSV path for the nutrient-unit mapping table.",
    )
    return parser.parse_args()


def read_field_descriptions(xlsx_path: Path) -> dict[str, set[str]]:
    """Parse table/field definitions from the API field descriptions workbook.

    Args:
        xlsx_path: Path to the 'Download API Field Descriptions.xlsx' workbook.

    Returns:
        Mapping of table name to the set of field names defined for that table.
    """
    log.info("Reading field descriptions from %s", xlsx_path.name)
    raw = pd.read_excel(xlsx_path, sheet_name="Field Descriptions", header=None).fillna(
        ""
    )
    definitions: dict[str, set[str]] = {}
    current_table: str | None = None

    for _, row in raw.iterrows():
        table_name = str(row.iloc[0]).strip()
        field_name = str(row.iloc[1]).strip()
        definition = str(row.iloc[2]).strip()

        if table_name and not field_name and definition:
            current_table = table_name
            definitions.setdefault(current_table, set())
        elif current_table and not table_name and field_name:
            definitions[current_table].add(field_name)

    log.info("Parsed definitions for %d tables", len(definitions))
    return definitions


def validate_schema(
    definitions: dict[str, set[str]], required_fields: dict[str, set[str]]
) -> None:
    """Warn if any required field is absent from the workbook definitions.

    Args:
        definitions: Parsed field definitions keyed by table name.
        required_fields: Expected fields keyed by table name.
    """
    for table_name, fields in required_fields.items():
        missing = fields - definitions.get(table_name, set())
        if missing:
            log.warning(
                "Table '%s' missing fields in workbook definitions: %s",
                table_name,
                ", ".join(sorted(missing)),
            )


def format_serving_size(row: pd.Series) -> str:
    """Build a human-readable serving size string from branded food columns.

    Args:
        row: A row from the branded_food DataFrame containing serving size fields.

    Returns:
        A formatted serving size string.
    """
    household = str(row.get("household_serving_fulltext") or "").strip()
    if household:
        return household

    amount = row.get("serving_size")
    unit = str(row.get("serving_size_unit") or "").strip()

    if pd.notna(amount) and unit:
        return f"{amount:g} {unit}"
    if unit:
        return unit
    if pd.notna(amount):
        return f"{amount:g}"
    return "unspecified"


def make_unique_nutrient_column_names(nutrients: pd.DataFrame) -> pd.DataFrame:
    """Append the nutrient id to disambiguate duplicate nutrient names.

    Args:
        nutrients: DataFrame with at least 'id' and 'name' columns.

    Returns:
        Copy of the input with an added 'nutrient_column' column.
    """
    nutrients = nutrients.copy()
    duplicate_mask = nutrients["name"].duplicated(keep=False)
    nutrients["nutrient_column"] = nutrients["name"]
    nutrients.loc[duplicate_mask, "nutrient_column"] = nutrients.loc[
        duplicate_mask
    ].apply(lambda r: f"{r['name']} [id:{int(r['id'])}]", axis=1)
    log.info(
        "Resolved %d duplicate nutrient names with id suffix",
        int(duplicate_mask.sum()),
    )
    return nutrients


def load_serving_sizes(branded_food_path: Path) -> pd.DataFrame:
    """Load and format serving size information from branded_food.csv.

    Args:
        branded_food_path: Path to branded_food.csv.

    Returns:
        DataFrame with columns ['fdc_id', 'brand_owner', 'brand_name',
        'branded_food_category', 'ingredients', 'serving_size'].
    """
    log.info("Reading %s", branded_food_path.name)
    bf = pd.read_csv(
        branded_food_path,
        usecols=[
            "fdc_id",
            "brand_owner",
            "brand_name",
            "branded_food_category",
            "ingredients",
            "serving_size",
            "serving_size_unit",
            "household_serving_fulltext",
        ],
        low_memory=False,
    )
    bf["serving_size"] = bf.apply(format_serving_size, axis=1)
    log.info("Loaded %d branded food records", len(bf))
    return bf[
        [
            "fdc_id",
            "brand_owner",
            "brand_name",
            "branded_food_category",
            "ingredients",
            "serving_size",
        ]
    ]


def load_nutrient_lookup(nutrient_path: Path) -> pd.DataFrame:
    """Load nutrient reference data and assign unique column names.

    Args:
        nutrient_path: Path to nutrient.csv.

    Returns:
        DataFrame with columns ['nutrient_id', 'name', 'nutrient_column', 'unit_name'].
    """
    log.info("Reading %s", nutrient_path.name)
    nutrient_df = pd.read_csv(nutrient_path, usecols=["id", "name", "unit_name"])
    nutrient_df = make_unique_nutrient_column_names(nutrient_df)
    return nutrient_df.rename(columns={"id": "nutrient_id"})[
        ["nutrient_id", "name", "nutrient_column", "unit_name"]
    ]


def build_nutrient_wide(
    food_nutrient_path: Path, nutrient_lookup: pd.DataFrame
) -> pd.DataFrame:
    """Pivot food_nutrient rows into a wide DataFrame with one column per nutrient.

    Args:
        food_nutrient_path: Path to food_nutrient.csv.
        nutrient_lookup: DataFrame from load_nutrient_lookup.

    Returns:
        Wide DataFrame indexed by 'fdc_id' with one nutrient column per nutrient.
    """
    log.info("Reading %s", food_nutrient_path.name)
    food_nutrient_df = pd.read_csv(
        food_nutrient_path,
        usecols=["fdc_id", "nutrient_id", "amount"],
        low_memory=False,
    )
    log.info("Loaded %d food-nutrient records", len(food_nutrient_df))

    merged = food_nutrient_df.merge(
        nutrient_lookup[["nutrient_id", "nutrient_column"]],
        on="nutrient_id",
        how="inner",
    )
    log.info("Matched %d records after nutrient join", len(merged))

    # Aggregate duplicate (fdc_id, nutrient_column) pairs by mean before pivoting
    merged = merged.groupby(["fdc_id", "nutrient_column"], as_index=False)[
        "amount"
    ].mean()

    wide = merged.pivot(
        index="fdc_id", columns="nutrient_column", values="amount"
    ).reset_index()
    wide.columns.name = None
    return wide


def main() -> None:
    """Entry point: build and write the branded food-nutrient and unit-map tables."""
    args = parse_args()
    input_dir = args.input_dir.resolve()

    workbook_path = input_dir / "Download API Field Descriptions.xlsx"
    food_path = input_dir / "food.csv"
    branded_food_path = input_dir / "branded_food.csv"
    food_nutrient_path = input_dir / "food_nutrient.csv"
    nutrient_path = input_dir / "nutrient.csv"

    required_paths = [
        workbook_path,
        food_path,
        branded_food_path,
        food_nutrient_path,
        nutrient_path,
    ]
    missing = [p for p in required_paths if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Required input files are missing:\n" + "\n".join(str(p) for p in missing)
        )

    definitions = read_field_descriptions(workbook_path)
    validate_schema(
        definitions,
        required_fields={
            "food": {"fdc_id", "description"},
            "branded_food": {
                "fdc_id",
                "brand_owner",
                "brand_name",
                "branded_food_category",
                "ingredients",
                "serving_size",
                "serving_size_unit",
                "household_serving_fulltext",
            },
            "food_nutrient": {"fdc_id", "nutrient_id", "amount"},
            "nutrient": {"id", "name", "unit_name"},
        },
    )

    log.info("Reading %s", food_path.name)
    food_df = pd.read_csv(
        food_path, usecols=["fdc_id", "description"], low_memory=False
    )
    food_df = food_df.rename(columns={"description": "food_name"})

    branded_df = load_serving_sizes(branded_food_path)
    nutrient_lookup = load_nutrient_lookup(nutrient_path)
    nutrient_wide_df = build_nutrient_wide(food_nutrient_path, nutrient_lookup)

    log.info("Assembling final food table")
    final_food_table = food_df.merge(branded_df, on="fdc_id", how="left").merge(
        nutrient_wide_df, on="fdc_id", how="left"
    )

    nutrient_cols = sorted(c for c in final_food_table.columns if c not in FIXED_COLS)
    final_food_table = final_food_table[FIXED_COLS + nutrient_cols]

    nutrient_unit_map = (
        nutrient_lookup.rename(columns={"name": "nutrient_name"})[
            ["nutrient_id", "nutrient_name", "nutrient_column", "unit_name"]
        ]
        .sort_values("nutrient_column")
        .reset_index(drop=True)
    )

    args.output_food_table.parent.mkdir(parents=True, exist_ok=True)
    args.output_unit_map.parent.mkdir(parents=True, exist_ok=True)

    final_food_table.to_csv(args.output_food_table, index=False, encoding="utf-8")
    nutrient_unit_map.to_csv(args.output_unit_map, index=False, encoding="utf-8")

    log.info("Wrote food nutrient table: %s", args.output_food_table)
    log.info("Wrote nutrient unit map:   %s", args.output_unit_map)
    log.info("Food rows:        %d", len(final_food_table))
    log.info("Nutrient columns: %d", len(nutrient_cols))
    log.info("Nutrients mapped: %d", len(nutrient_unit_map))


if __name__ == "__main__":
    main()
