"""Unit tests for the frontend optimization module."""

from __future__ import annotations

from types import ModuleType

import pandas as pd

from conftest import FRONTEND_APP_DIR


def _load_frontend_optimize(load_module: object, module_name: str) -> ModuleType:
    """Import the frontend optimize module.

    Args:
        load_module: Shared file-based module loader fixture.
        module_name: Unique module name for the import.

    Returns:
        Imported optimize module.
    """
    return load_module(
        module_name,
        FRONTEND_APP_DIR / "optimize.py",
        prepend_paths=[FRONTEND_APP_DIR],
    )


def test_simplex_init_normalizes_input_arrays(load_module: object) -> None:
    """Normalize values and nutrient arrays in optimizer initialization."""
    module = _load_frontend_optimize(load_module, "test_frontend_optimize_init")
    data = pd.DataFrame(
        {
            "food_name": ["A", "B"],
            "Value": [2.5, "3.0"],
            "protein": [10.0, 20.0],
            "carbs": [15.0, 30.0],
        }
    )
    bounds = module.SliderBounds(
        minimums={"protein": 12.0, "carbs": None},
        maximums={"protein": 40.0, "carbs": 45.0},
    )

    optimizer = module.Simplex(data=data, bounds=bounds)

    assert optimizer.food_names == ["A", "B"]
    assert optimizer.nutrient_columns == ["carbs", "protein"]
    assert optimizer.value_vector.tolist() == [2.5, 3.0]
    assert optimizer.nutrient_matrix.shape == (2, 2)


def test_simplex_init_raises_when_value_column_missing(load_module: object) -> None:
    """Reject data that does not provide the required Value column."""
    module = _load_frontend_optimize(
        load_module,
        "test_frontend_optimize_missing_value",
    )
    data = pd.DataFrame(
        {
            "food_name": ["A"],
            "protein": [10.0],
        }
    )
    bounds = module.SliderBounds(minimums={"protein": 5.0}, maximums={"protein": 15.0})

    try:
        module.Simplex(data=data, bounds=bounds)
        assert False, "Expected ValueError when Value column is missing."
    except ValueError as exc:
        assert "Value column" in str(exc)
