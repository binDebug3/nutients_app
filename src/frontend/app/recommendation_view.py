"""Render optimization results for nutrient recommendations."""

from typing import Dict, List, Optional

import pandas as pd

from models import DIETARY_TOGGLE_LABELS
from optimize import OptimizationResult, SliderBounds
from ui_theme import SUMMARY_COLUMNS, safe_markdown


class RecommendationView:
    """
    Render recommendation summary and tabular outputs.

    Args:
        streamlit_module: Streamlit module or fake module in tests.
        logger: Logger used for recommendation rendering events.
    """

    def __init__(self, streamlit_module: object, logger: object) -> None:
        """
        Initialize view dependencies.

        Args:
            streamlit_module: Streamlit module-like object.
            logger: Logger for recommendation events.
        """
        self._st = streamlit_module
        self._log = logger

    def render_recommendation_summary(
        self,
        result: OptimizationResult,
        recommended_row_count: int,
        dietary_preferences: Dict[str, bool],
    ) -> None:
        """
        Render high-level recommendation metrics and active dietary preferences.

        Args:
            result: Optimization result from the solver.
            recommended_row_count: Number of selected food rows.
            dietary_preferences: Dietary toggle states.
        """
        self._log.info(
            "Rendering recommendation summary",
            extra={"event": "ui.recommendation.summary"},
        )
        summary_cols = self._st.columns(SUMMARY_COLUMNS)
        self._render_picks(summary_cols[0], recommended_row_count)
        self._render_total_value(summary_cols[1], result.objective_value)
        status_text = result.status or "unknown"
        status_class = (
            "status-ok" if status_text.lower() == "optimal" else "status-unknown"
        )
        with summary_cols[2]:
            safe_markdown(
                self._st,
                (
                    "<div class='metric-card'>"
                    "<div class='metric-label'>Solver Status</div>"
                    f"<div class='metric-value {status_class}'>{status_text}</div>"
                    "</div>"
                ),
                unsafe_html=True,
            )
        self._render_active_preferences(dietary_preferences)

    def render_recommended_foods(
        self,
        df: object,
        result: OptimizationResult,
        dietary_preferences: Dict[str, bool],
        active_nutrient_columns: Optional[List[str]] = None,
        nutrient_bounds: Optional[SliderBounds] = None,
    ) -> None:
        """
        Render ranked food recommendations with candidate fallback.

        Args:
            df: Candidate foods DataFrame returned by SQL query.
            result: Optimization result from the solver.
            dietary_preferences: Dietary toggle states.
            active_nutrient_columns: Active nutrient columns where Any is off.
            nutrient_bounds: Active nutrient min/max bounds.
        """
        self._log.info(
            "Rendering recommendations", extra={"event": "ui.recommendation.render"}
        )
        recommendation_df = self._build_recommendation_df(df, result)
        ranked_df = self._build_ranked_df(recommendation_df)

        self._st.markdown("## Recommended Foods")
        self.render_recommendation_summary(result, len(ranked_df), dietary_preferences)

        if ranked_df.empty:
            self._render_empty_state(recommendation_df)
            return

        self._render_ranked_table(
            ranked_df,
            active_nutrient_columns or [],
            nutrient_bounds,
        )
        top_foods = ranked_df["food_name"].tolist()[:8]
        safe_markdown(self._st, "<div class='top-picks'>", unsafe_html=True)
        self._st.write("Top picks: " + " | ".join(top_foods))
        safe_markdown(self._st, "</div>", unsafe_html=True)
        self._render_candidate_table(recommendation_df)

    def _build_recommendation_df(
        self, df: object, result: OptimizationResult
    ) -> object:
        """
        Build recommendation dataframe columns from optimization output.

        Args:
            df: Candidate foods DataFrame.
            result: Optimization result with serving decisions.

        Returns:
            DataFrame with derived recommendation columns.
        """
        self._log.info(
            "Building recommendation dataframe",
            extra={"event": "ui.recommendation.frame"},
        )
        recommendation_df = df.copy()
        recommendation_df["recommended_servings"] = result.servings
        recommendation_df["value_contribution"] = (
            recommendation_df["recommended_servings"] * recommendation_df["value"]
        )
        return recommendation_df

    def _build_ranked_df(self, recommendation_df: object) -> object:
        """
        Build ranked view of foods with positive servings.

        Args:
            recommendation_df: Recommendation dataframe.

        Returns:
            Ranked subset dataframe.
        """
        self._log.info(
            "Building ranked recommendation dataframe",
            extra={"event": "ui.recommendation.rank"},
        )
        ranked_df = recommendation_df[
            recommendation_df["recommended_servings"] > 1e-8
        ].copy()
        ranked_df = ranked_df.sort_values(
            by=["value_contribution", "recommended_servings"],
            ascending=False,
        )
        return ranked_df

    def _render_picks(self, column: object, recommended_row_count: int) -> None:
        """
        Render selected-food count summary tile.

        Args:
            column: Streamlit layout column.
            recommended_row_count: Count of selected foods.
        """
        self._log.info(
            "Rendering picks summary", extra={"event": "ui.recommendation.picks"}
        )
        with column:
            safe_markdown(
                self._st,
                (
                    "<div class='metric-card'>"
                    "<div class='metric-label'>Unique Foods</div>"
                    f"<div class='metric-value'>{recommended_row_count}</div>"
                    "</div>"
                ),
                unsafe_html=True,
            )

    def _render_total_value(
        self, column: object, objective_value: Optional[float]
    ) -> None:
        """
        Render objective value summary tile.

        Args:
            column: Streamlit layout column.
            objective_value: Objective value from optimizer.
        """
        self._log.info(
            "Rendering total value summary", extra={"event": "ui.recommendation.value"}
        )
        with column:
            total_value_text = (
                "n/a" if objective_value is None else f"{objective_value:.2f}"
            )
            safe_markdown(
                self._st,
                (
                    "<div class='metric-card'>"
                    "<div class='metric-label'>Total Servings</div>"
                    f"<div class='metric-value'>{total_value_text}</div>"
                    "</div>"
                ),
                unsafe_html=True,
            )

    def _render_active_preferences(self, dietary_preferences: Dict[str, bool]) -> None:
        """
        Render currently enabled dietary labels.

        Args:
            dietary_preferences: Dietary toggle states.
        """
        self._log.info(
            "Rendering active preferences", extra={"event": "ui.dietary.active"}
        )
        active_preferences = [
            label
            for key, label in DIETARY_TOGGLE_LABELS
            if dietary_preferences.get(key, False)
        ]
        if active_preferences:
            self._st.write("Dietary filters enabled: " + ", ".join(active_preferences))
        else:
            self._st.write("Dietary filters enabled: none")

    def _render_empty_state(self, recommendation_df: object) -> None:
        """
        Render UI when optimization selected no foods.

        Args:
            recommendation_df: Candidate dataframe with derived columns.
        """
        self._log.info(
            "Rendering empty recommendation state",
            extra={"event": "ui.recommendation.empty"},
        )
        self._st.warning(
            "No feasible foods were selected from the current constraints."
        )
        self._st.markdown("## Candidate Foods")
        self._st.table(recommendation_df)

    def _render_ranked_table(
        self,
        ranked_df: pd.DataFrame,
        active_nutrient_columns: List[str],
        nutrient_bounds: Optional[SliderBounds],
    ) -> None:
        """
        Render ranked recommendation table.

        Args:
            ranked_df: Ranked recommendation dataframe.
            active_nutrient_columns: Nutrient columns where Any is off.
            nutrient_bounds: Min and max nutrient bounds.
        """
        self._log.info(
            "Rendering ranked recommendation table",
            extra={"event": "ui.recommendation.table_ranked"},
        )

        display_columns = [
            "food_name",
            "serving_size",
            "recommended_servings",
        ]
        nutrient_columns = [
            column for column in active_nutrient_columns if column in ranked_df.columns
        ]
        display_columns.extend(nutrient_columns)

        display_df = ranked_df[display_columns].copy()
        display_df["recommended_servings"] = pd.to_numeric(
            display_df["recommended_servings"],
            errors="coerce",
        ).round(1)
        if nutrient_columns:
            for nutrient_column in nutrient_columns:
                nutrient_values = pd.to_numeric(
                    display_df[nutrient_column],
                    errors="coerce",
                )
                display_df[nutrient_column] = (
                    nutrient_values * display_df["recommended_servings"]
                ).round(1)
        if nutrient_columns and nutrient_bounds is not None:
            summary_rows = self._build_nutrient_summary_rows(
                ranked_df,
                nutrient_columns,
                nutrient_bounds,
            )
            display_df = pd.concat([display_df, summary_rows], ignore_index=True)

        safe_markdown(self._st, "<div class='app-surface'>", unsafe_html=True)

        if hasattr(self._st, "dataframe"):
            self._st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
            )
        else:
            self._st.table(display_df)
        safe_markdown(self._st, "</div>", unsafe_html=True)

    def _build_nutrient_summary_rows(
        self,
        ranked_df: pd.DataFrame,
        nutrient_columns: List[str],
        nutrient_bounds: SliderBounds,
    ) -> pd.DataFrame:
        """
        Build required/achieved summary rows for active nutrient columns.

        Args:
            ranked_df: Ranked recommendation dataframe with servings.
            nutrient_columns: Active nutrient columns in display order.
            nutrient_bounds: Min and max nutrient bounds.

        Returns:
            Dataframe containing summary rows appended to recommendation output.
        """
        summary_rows: List[Dict[str, object]] = []
        row_specs = [
            ("Required Min", nutrient_bounds.minimums),
            ("Recommended Sum", None),
            ("Required Max", nutrient_bounds.maximums),
        ]

        for label, bound_map in row_specs:
            row_data: Dict[str, object] = {
                "food_name": label,
                "serving_size": "",
                "recommended_servings": "",
            }
            for nutrient_column in nutrient_columns:
                if bound_map is None:
                    nutrient_total = (
                        ranked_df[nutrient_column] * ranked_df["recommended_servings"]
                    ).sum()
                    row_data[nutrient_column] = f"{float(nutrient_total):.1f}"
                    continue

                bound_value = bound_map.get(nutrient_column)
                row_data[nutrient_column] = (
                    "" if bound_value is None else f"{float(bound_value):.1f}"
                )
            summary_rows.append(row_data)

        summary_df = pd.DataFrame(summary_rows)
        summary_df = summary_df.astype(str)
        return summary_df

    def _render_candidate_table(self, recommendation_df: object) -> None:
        """
        Render complete candidate table beneath ranked recommendations.

        Args:
            recommendation_df: Candidate dataframe with derived columns.
        """
        self._log.info(
            "Rendering candidate recommendation table",
            extra={"event": "ui.recommendation.table_candidates"},
        )
        self._st.markdown("## Candidate Foods")
        safe_markdown(self._st, "<div class='app-surface'>", unsafe_html=True)
        self._st.table(
            recommendation_df[
                [
                    "food_name",
                    "serving_size",
                    "value",
                    "recommended_servings",
                    "value_contribution",
                ]
            ]
        )
        safe_markdown(self._st, "</div>", unsafe_html=True)
