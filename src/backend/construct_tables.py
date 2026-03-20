from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    project_root = script_path.parents[2]
    default_input_dir = (
        script_path.parents[3]
        / "data"
        / "nutrients"
        / "FoodData_Central_branded_food_csv_2025-12-18"
    )

    parser = argparse.ArgumentParser(
        description=(
            "Build (1) a wide food nutrient table with one nutrient per column and "
            "(2) a nutrient-to-unit mapping table from FoodData Central survey files."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=default_input_dir,
        help="Directory containing survey CSV files and the field descriptions workbook.",
    )
    parser.add_argument(
        "--output-food-table",
        type=Path,
        default=project_root / "processed_food_nutrients.csv",
        help="Output CSV path for the wide food nutrient table.",
    )
    parser.add_argument(
        "--output-unit-map",
        type=Path,
        default=project_root / "nutrient_unit_map.csv",
        help="Output CSV path for the nutrient-unit mapping table.",
    )
    return parser.parse_args()


def read_field_descriptions(xlsx_path: Path) -> dict[str, set[str]]:
    """Parse table/field definitions from the provided workbook for schema validation."""
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
            continue

        if current_table and not table_name and field_name:
            definitions[current_table].add(field_name)

    return definitions


def format_serving_size(row: pd.Series) -> str:
    portion_description = str(row.get("portion_description") or "").strip()
    measure_unit_name = str(row.get("measure_unit_name") or "").strip()
    modifier = str(row.get("modifier") or "").strip()
    amount = row.get("amount")
    gram_weight = row.get("gram_weight")

    if portion_description:
        base = portion_description
    elif pd.notna(amount) and measure_unit_name:
        base = f"{amount:g} {measure_unit_name}"
    elif measure_unit_name:
        base = measure_unit_name
    else:
        base = "unspecified"

    if modifier:
        base = f"{base}, {modifier}"

    if pd.notna(gram_weight):
        base = f"{base} ({gram_weight:g} g)"

    return base


def make_unique_nutrient_column_names(nutrients: pd.DataFrame) -> pd.DataFrame:
    """Ensure one unique output column name per nutrient id."""
    nutrients = nutrients.copy()
    duplicate_name_mask = nutrients["name"].duplicated(keep=False)
    nutrients["nutrient_column"] = nutrients["name"]
    nutrients.loc[duplicate_name_mask, "nutrient_column"] = nutrients.loc[
        duplicate_name_mask
    ].apply(lambda r: f"{r['name']} [id:{int(r['id'])}]", axis=1)
    return nutrients


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir.resolve()

    workbook_path = input_dir / "Download API Field Descriptions.xlsx"
    food_path = input_dir / "food.csv"
    food_portion_path = input_dir / "food_portion.csv"
    food_nutrient_path = input_dir / "food_nutrient.csv"
    nutrient_path = input_dir / "nutrient.csv"
    measure_unit_path = input_dir / "measure_unit.csv"

    required_paths = [
        workbook_path,
        food_path,
        food_portion_path,
        food_nutrient_path,
        nutrient_path,
        measure_unit_path,
    ]
    missing_paths = [p for p in required_paths if not p.exists()]
    if missing_paths:
        missing_list = "\n".join(str(p) for p in missing_paths)
        raise FileNotFoundError(f"Required input files are missing:\n{missing_list}")

    definitions = read_field_descriptions(workbook_path)
    required_fields = {
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
        "nutrient": {"id", "name", "unit_name"},
        "measure_unit": {"id", "name"},
    }

    for table_name, fields in required_fields.items():
        defined_fields = definitions.get(table_name, set())
        missing_from_definitions = fields - defined_fields
        if missing_from_definitions:
            missing_str = ", ".join(sorted(missing_from_definitions))
            print(f"Warning: table '{table_name}' missing fields in workbook definitions: "
                  + missing_str)

    food_df = pd.read_csv(food_path, usecols=["fdc_id", "description"])
    food_portion_df = pd.read_csv(
        food_portion_path,
        usecols=[
            "fdc_id",
            "seq_num",
            "amount",
            "measure_unit_id",
            "portion_description",
            "modifier",
            "gram_weight",
        ],
    )
    food_nutrient_df = pd.read_csv(
        food_nutrient_path, usecols=["fdc_id", "nutrient_id", "amount"]
    )
    nutrient_df = pd.read_csv(
        nutrient_path, usecols=["id", "name", "unit_name", "nutrient_nbr"]
    )
    nutrient_df = nutrient_df.dropna(subset=["nutrient_nbr"]).copy()
    nutrient_df["nutrient_nbr"] = nutrient_df["nutrient_nbr"].astype(int)
    measure_unit_df = pd.read_csv(measure_unit_path, usecols=["id", "name"])

    measure_unit_df = measure_unit_df.rename(
        columns={"id": "measure_unit_id", "name": "measure_unit_name"}
    )
    food_portion_df = food_portion_df.merge(
        measure_unit_df, on="measure_unit_id", how="left"
    )

    serving_df = (
        food_portion_df.sort_values(["fdc_id", "seq_num"], na_position="last")
        .drop_duplicates(subset=["fdc_id"], keep="first")
        .copy()
    )
    serving_df["serving_size"] = serving_df.apply(format_serving_size, axis=1)
    serving_df = serving_df[["fdc_id", "serving_size"]]

    nutrient_df = make_unique_nutrient_column_names(nutrient_df)
    nutrient_lookup = nutrient_df.rename(columns={"nutrient_nbr": "nutrient_id"})[
        ["nutrient_id", "name", "nutrient_column", "unit_name"]
    ]

    nutrient_values = food_nutrient_df.merge(
        nutrient_lookup[["nutrient_id", "nutrient_column"]],
        on="nutrient_id",
        how="inner",
    )
    nutrient_wide_df = nutrient_values.pivot(
        index="fdc_id", columns="nutrient_column", values="amount"
    ).reset_index()

    final_food_table = food_df.merge(serving_df, on="fdc_id", how="left").merge(
        nutrient_wide_df, on="fdc_id", how="left"
    )
    final_food_table = final_food_table.rename(columns={"description": "food_name"})

    fixed_cols = ["fdc_id", "food_name", "serving_size"]
    nutrient_cols = sorted(c for c in final_food_table.columns if c not in fixed_cols)
    final_food_table = final_food_table[fixed_cols + nutrient_cols]

    nutrient_unit_map = nutrient_lookup.rename(columns={"name": "nutrient_name"})[
        ["nutrient_id", "nutrient_name", "nutrient_column", "unit_name"]
    ]
    nutrient_unit_map = nutrient_unit_map.sort_values("nutrient_column").reset_index(
        drop=True
    )

    args.output_food_table.parent.mkdir(parents=True, exist_ok=True)
    args.output_unit_map.parent.mkdir(parents=True, exist_ok=True)

    final_food_table.to_csv(args.output_food_table, index=False)
    nutrient_unit_map.to_csv(args.output_unit_map, index=False)

    print(f"Wrote food nutrient table: {args.output_food_table}")
    print(f"Wrote nutrient unit map: {args.output_unit_map}")
    print(f"Food rows: {len(final_food_table):,}")
    print(f"Nutrients mapped: {len(nutrient_unit_map):,}")


if __name__ == "__main__":
    main()
