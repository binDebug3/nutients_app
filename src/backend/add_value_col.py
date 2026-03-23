"""
Add and normalize the Value column in the food nutrients CSV.

This script inserts a `Value` column in the second position and sets all
rows in that column to 1.
"""

from __future__ import annotations

import argparse
from logging import Logger
from pathlib import Path

import pandas as pd

from logging_setup import configure_backend_logging


VALUE_COLUMN_NAME = "Value"
VALUE_COLUMN_DEFAULT = 1
DEFAULT_CSV_RELATIVE_PATH = Path("data") / "nutrients" / "food_nutrients.csv"


log: Logger = configure_backend_logging("add_value_col")


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed command-line arguments namespace.
    """
    log.info("Parsing command-line arguments")
    script_path = Path(__file__).resolve()
    default_csv_path = script_path.parents[3] / DEFAULT_CSV_RELATIVE_PATH

    parser = argparse.ArgumentParser(
        description=(
            "Add a Value column in the second position and set all values in "
            "that column to 1."
        )
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=default_csv_path,
        help="Path to food_nutrients.csv.",
    )
    return parser.parse_args()


def add_value_column(csv_path: Path) -> None:
    """
    Add or normalize the Value column in the source CSV.

    Args:
        csv_path: Path to the CSV file to modify.
    """
    log.info("Loading CSV file: %s", csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    data_frame = pd.read_csv(csv_path, encoding="utf-8")

    data_frame[VALUE_COLUMN_NAME] = VALUE_COLUMN_DEFAULT
    ordered_columns = [
        column for column in data_frame.columns if column != VALUE_COLUMN_NAME
    ]
    insert_index = 1 if ordered_columns else 0
    ordered_columns.insert(insert_index, VALUE_COLUMN_NAME)
    data_frame = data_frame.loc[:, ordered_columns]

    log.info("Writing updated CSV with Value column at position %d", insert_index + 1)
    data_frame.to_csv(csv_path, index=False, encoding="utf-8")


def main() -> None:
    """
    Execute the Value-column update workflow.
    """
    log.info("Starting Value-column update workflow")
    arguments = parse_args()
    add_value_column(arguments.csv_path.resolve())
    log.info("Completed Value-column update workflow")


if __name__ == "__main__":
    main()
