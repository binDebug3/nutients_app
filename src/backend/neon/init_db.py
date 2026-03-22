import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

SCRIPT_PATH = Path(__file__).resolve()
LOG_DIR = SCRIPT_PATH.parents[3] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGER = logging.getLogger("nutients_app.backend.neon.init_db")
if not LOGGER.handlers:
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )

    file_handler = RotatingFileHandler(
        LOG_DIR / "backend.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(module)s | %(message)s"
        )
    )

    LOGGER.addHandler(console_handler)
    LOGGER.addHandler(file_handler)

# Paste the string you copied in Step 2 here
SECRETS_FILE: Path = Path("../secrets/passwords/neon.txt")
LOGGER.info("Reading Neon connection string from %s", SECRETS_FILE)
NEON_URL: str = SECRETS_FILE.read_text(encoding="utf-8").strip()

# Load your 1.5 GB file
LOGGER.info("Loading food nutrients CSV")
df = pd.read_csv("../data/nutrients/food_nutrients.csv")

# This creates the database connection
LOGGER.info("Creating database engine")
engine = create_engine(NEON_URL)

# This pushes the data. It will create all 79 columns for you.
# Note: If your file is over 0.5 GB, this will likely error out when it hits the limit.
LOGGER.info("Writing DataFrame to SQL table food_data with if_exists=replace")
df.to_sql("food_data", engine, if_exists="replace", index=False)

LOGGER.info("Database initialization finished")
