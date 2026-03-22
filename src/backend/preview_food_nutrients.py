"""Print and persist row details for the food nutrients dataset.

This script reads `data/nutrients/food_nutrients.csv`, prints the number of rows,
prints the first 20 rows, and writes the same output to
`data/nutrients/rows.txt`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from logging_setup import configure_backend_logging

log = configure_backend_logging("preview_food_nutrients")

SCRIPT_PATH = Path(__file__).resolve()
DATA_DIR = SCRIPT_PATH.parents[3] / "data" / "nutrients"
INPUT_CSV = DATA_DIR / "hidden_food_nutrients.csv"
OUTPUT_TXT = DATA_DIR / "rows.txt"
FIRST_ROWS_COUNT = 20
CSV_ENCODING = "utf-8"
TXT_ENCODING = "utf-8"


def load_food_nutrients(csv_path: Path) -> pd.DataFrame:
    """Load the food nutrients CSV into a DataFrame.

    Args:
        csv_path: Path to the input CSV file.

    Returns:
        Parsed food nutrients DataFrame.
    """
    log.info("Loading CSV from %s", csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Input CSV was not found: {csv_path}")

    return pd.read_csv(csv_path, encoding=CSV_ENCODING, low_memory=False)


def build_output_text(food_nutrients_df: pd.DataFrame) -> str:
    """Build the output text containing row count and first rows preview.

    Args:
        food_nutrients_df: DataFrame loaded from food_nutrients.csv.

    Returns:
        Formatted text output for console and file writing.
    """
    log.info("Building output text for %d total rows", len(food_nutrients_df))
    row_count_line = f"Number of rows: {len(food_nutrients_df)}"
    header_line = f"First {FIRST_ROWS_COUNT} rows:"
    rows_preview = food_nutrients_df.head(FIRST_ROWS_COUNT).to_string(index=False)
    return "\n".join([row_count_line, "", header_line, rows_preview])


def write_output(output_text: str, output_path: Path) -> None:
    """Write output text to the destination file.

    Args:
        output_text: Text to persist.
        output_path: Destination text file path.
    """
    log.info("Writing output to %s", output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output_text + "\n", encoding=TXT_ENCODING)


def main() -> None:
    """Run the script to print and save food nutrient row information."""
    log.info("Starting food nutrients row preview script")
    food_nutrients_df = load_food_nutrients(INPUT_CSV)
    output_text = build_output_text(food_nutrients_df)

    print(output_text)
    write_output(output_text, OUTPUT_TXT)

    log.info("Completed successfully")


if __name__ == "__main__":
    main()
