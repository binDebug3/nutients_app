"""Optimization helpers for nutrient-constrained food selection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


log = logging.getLogger("nutients_app.optimize")


@dataclass(frozen=True)
class SliderBounds:
    """
    Min and max values collected from nutrient slider controls.

    Args:
        minimums: Per-nutrient minimum requirement values.
        maximums: Per-nutrient maximum requirement values.
    """

    minimums: Dict[str, Optional[float]]
    maximums: Dict[str, Optional[float]]


@dataclass(frozen=True)
class OptimizationResult:
    """
    Result payload returned by the optimizer.

    Args:
        status: Solver status string.
        objective_value: Optimal objective value or None when unavailable.
        servings: Optimized servings for each food in input order.
        selected_foods: Food names corresponding to strictly positive servings.
    """

    status: str
    objective_value: Optional[float]
    servings: np.ndarray
    selected_foods: List[str]


class Simplex:
    """
    Solve food selection with nutrient constraints and a value-maximizing objective.

    Args:
        data: Input table containing one row per food and nutrient/value columns.
        bounds: Min/max nutrient bounds built from the UI sliders.
    """

    _VALUE_COLUMN = "Value"
    _NAME_COLUMN = "food_name"

    def __init__(self, data: pd.DataFrame, bounds: SliderBounds) -> None:
        """
        Normalize incoming data and bounds for optimization.

        Args:
            data: Input food data with numeric nutrient columns and a `Value` column.
            bounds: Slider min/max values keyed by nutrient alias.

        Raises:
            ValueError: If required data columns are missing or if no rows are provided.
        """
        log.info("Initializing optimizer", extra={"event": "optimizer.init"})

        if data.empty:
            raise ValueError("Input data must contain at least one food row.")

        if self._VALUE_COLUMN not in data.columns:
            raise ValueError("Input data must include a Value column.")

        if self._NAME_COLUMN not in data.columns:
            raise ValueError("Input data must include a food_name column.")

        self.data = data.copy()
        self.bounds = bounds
        self.food_names = [str(name) for name in self.data[self._NAME_COLUMN].tolist()]
        self.value_vector = (
            pd.to_numeric(self.data[self._VALUE_COLUMN], errors="coerce")
            .fillna(0.0)
            .to_numpy(dtype=float)
        )

        (
            self.nutrient_columns,
            self.minimum_bounds,
            self.maximum_bounds,
        ) = self._prepare_bounds()

        if self.nutrient_columns:
            self.nutrient_matrix = (
                self.data[self.nutrient_columns]
                .apply(pd.to_numeric, errors="coerce")
                .fillna(0.0)
                .to_numpy(dtype=float)
            )
        else:
            self.nutrient_matrix = np.zeros((len(self.food_names), 0), dtype=float)

    def _prepare_bounds(self) -> tuple[List[str], np.ndarray, np.ndarray]:
        """
        Build ordered nutrient bounds aligned to data columns.

        Returns:
            Tuple of active nutrient column names, minimum bounds array, and maximum bounds array.

        Raises:
            ValueError: If a bounded nutrient column is missing from input data.
        """
        log.info(
            "Preparing nutrient bounds", extra={"event": "optimizer.prepare_bounds"}
        )

        minimum_items = self.bounds.minimums.items()
        maximum_items = self.bounds.maximums.items()
        nutrient_names = sorted(
            {name for name, _ in minimum_items} | {name for name, _ in maximum_items}
        )

        active_columns: List[str] = []
        minimum_bounds: List[float] = []
        maximum_bounds: List[float] = []

        for nutrient_name in nutrient_names:
            min_value = self.bounds.minimums.get(nutrient_name)
            max_value = self.bounds.maximums.get(nutrient_name)

            if min_value is None and max_value is None:
                continue

            if nutrient_name not in self.data.columns:
                raise ValueError(
                    f"Input data is missing nutrient column: {nutrient_name}"
                )

            active_columns.append(nutrient_name)
            minimum_bounds.append(float(min_value) if min_value is not None else np.nan)
            maximum_bounds.append(float(max_value) if max_value is not None else np.nan)

        return (
            active_columns,
            np.array(minimum_bounds, dtype=float),
            np.array(maximum_bounds, dtype=float),
        )

    def run(self) -> OptimizationResult:
        """
        Solve the cvxpy optimization problem and return selected foods.

        Returns:
            Optimization result including solver status, objective value, servings, and picks.
        """
        log.info("Running optimizer", extra={"event": "optimizer.run"})

        import cvxpy as cp

        servings = cp.Variable(len(self.food_names), nonneg=True)
        objective = cp.Maximize(self.value_vector @ servings)
        constraints = []

        for index, nutrient_name in enumerate(self.nutrient_columns):
            nutrient_values = self.nutrient_matrix[:, index]
            min_value = self.minimum_bounds[index]
            max_value = self.maximum_bounds[index]

            if not np.isnan(min_value):
                constraints.append(nutrient_values @ servings >= min_value)

            if not np.isnan(max_value):
                constraints.append(nutrient_values @ servings <= max_value)

            log.info(
                "Applied nutrient bounds",
                extra={"event": "optimizer.bound", "nutrient": nutrient_name},
            )

        problem = cp.Problem(objective, constraints)
        problem.solve()

        solved_servings = (
            np.array(servings.value, dtype=float)
            if servings.value is not None
            else np.zeros(len(self.food_names), dtype=float)
        )

        selected_foods = [
            food_name
            for food_name, servings_value in zip(self.food_names, solved_servings)
            if servings_value > 1e-8
        ]

        objective_value = (
            float(problem.value)
            if problem.value is not None and np.isfinite(problem.value)
            else None
        )

        return OptimizationResult(
            status=str(problem.status),
            objective_value=objective_value,
            servings=solved_servings,
            selected_foods=selected_foods,
        )
