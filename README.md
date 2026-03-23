# Nutients App

A Streamlit web application that uses the **Simplex optimization method** to generate
optimal daily meal recommendations based on custom macro and micronutrient targets and
dietary restrictions. Food data is sourced from the USDA FoodData Central database and
hosted on a Neon PostgreSQL database.

---

## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Usage](#usage)
- [File Architecture](#file-architecture)
- [License](#license)
- [Contributors](#contributors)

---

## Introduction

Nutients App is designed for dietetics students and anyone who wants to take the guesswork
out of daily meal planning. A user logs in, enters their nutrient requirement ranges (e.g.,
protein 50–100 g, vitamin C 75–120 mg) and any dietary restrictions, and the app solves a
linear program using the Simplex method to return an optimized set of food recommendations
that satisfies all constraints for the day. The underlying food data spans branded and
generic products from the USDA FoodData Central dataset, processed and loaded into a
cloud-hosted Neon PostgreSQL database.

---

## Features

- **Optimized meal recommendations** — Uses the Simplex method to find the combination of
  foods that best satisfies user-defined macro and micronutrient ranges for a full day.
- **Custom nutrient targets** — Users specify their own minimum and maximum bounds for any
  combination of macro and micronutrients.
- **Dietary restriction filtering** — Supports common restrictions including vegan,
  vegetarian, gluten-free, and allergen-based exclusions.
- **USDA FoodData Central data** — Covers thousands of branded and generic food items with
  detailed nutrient profiles.
- **Built-in authentication** — Account creation and login are handled in-app; no external
  identity provider required.
- **Structured logging** — Backend and frontend activity is logged to rotating log files
  for observability and debugging.

---

## Usage

### Prerequisites

- [Conda](https://docs.conda.io/) with the `lila` environment created from `environment.yml`
- A Neon PostgreSQL connection string stored at `secrets/passwords/neon.txt`

### Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/binDebug3/nutients_app.git
   cd nutients_app
   ```

2. Create and activate the conda environment:

   ```bash
   conda env create -f environment.yml
   conda activate lila
   ```

3. Download the USDA FoodData Central CSV files and place them under `data/nutrients/`.

4. Process and load the data into the Neon database:

   ```bash
   # Build food nutrient tables for each dataset folder
   python src/backend/construct_tables.py
   python src/backend/construct_branded_tables.py

   # Deduplicate nutrients across datasets
   python src/backend/dedup_nutrs.py

   # Resolve any nutrient-unit map discrepancies
   python src/backend/compare.py

   # Merge all processed tables into one CSV
   python src/backend/join.py

   # Push the merged CSV to the Neon PostgreSQL database
   python src/backend/neon/init_db.py
   ```

5. Run the Streamlit app:

   ```bash
   cd src/frontend/app
   streamlit run app.py
   ```

6. Open the URL shown in the terminal, create an account, and start generating meal plans.

### Running Tests

```bash
conda activate lila
pytest tests/
```

---

## File Architecture

```
nutients_app/
├── environment.yml             # Conda environment specification
├── requirements.txt            # Pinned package versions
├── LICENSE                     # Apache 2.0 license
├── README.md
├── logs/                       # Rotating log files (backend + frontend)
├── data/
│   └── nutrients/              # USDA FoodData Central CSVs and processed outputs
├── src/
│   ├── backend/
│   │   ├── compare.py          # Compares and resolves nutrient-unit map discrepancies
│   │   ├── construct_branded_tables.py  # Processes branded food datasets
│   │   ├── construct_tables.py          # Processes generic food datasets
│   │   ├── dedup_nutrs.py      # Deduplicates nutrients across dataset folders
│   │   ├── join.py             # Merges processed tables into a single CSV
│   │   ├── logging_setup.py    # Backend logging configuration
│   │   ├── preview_food_nutrients.py    # Utility to preview processed data
│   │   └── neon/
│   │       └── init_db.py      # Loads the merged CSV into the Neon PostgreSQL database
│   └── frontend/
│       └── app/
│           ├── app.py          # Streamlit entry point with authentication and UI
│           └── logging_setup.py  # Frontend logging configuration
└── tests/                      # Pytest test suite mirroring src/ structure
    ├── conftest.py
    ├── test_backend_logging_setup.py
    ├── test_compare.py
    ├── test_construct_branded_tables.py
    ├── test_construct_tables.py
    ├── test_dedup_nutrs.py
    ├── test_frontend_app.py
    ├── test_frontend_logging_setup.py
    ├── test_join.py
    ├── test_neon_init_db.py
    └── test_preview_food_nutrients.py
```

---

## License

This project is licensed under the [Apache License 2.0](LICENSE).

---

## Contributors

- **Dallin Stewart** — [github.com/binDebug3](https://github.com/binDebug3)

## Authentication
The Streamlit frontend supports login with credentials defined in `.streamlit/secrets.toml`.
New users can also create accounts from the login screen, and those passwords are stored as
PBKDF2 hashes in `src/frontend/app/.streamlit/users.db`.
