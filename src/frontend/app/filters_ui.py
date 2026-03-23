"""Streamlit rendering helpers for nutrient and dietary filter controls."""

from typing import Dict, List

from models import DIETARY_TOGGLE_LABELS, NutrientSpec
from state_manager import NutrientStateManager
from ui_theme import FILTER_HEADER_COLUMNS, FILTER_ROW_COLUMNS, safe_markdown


class FilterPanel:
    """
    Render nutrient and dietary filter controls.

    Args:
        streamlit_module: Streamlit module or a fake module in tests.
        logger: Logger used for UI rendering events.
        state_manager: Manager for nutrient control session-state.
    """

    def __init__(
        self,
        streamlit_module: object,
        logger: object,
        state_manager: NutrientStateManager,
    ) -> None:
        """
        Store dependencies for filter rendering.

        Args:
            streamlit_module: Streamlit module-like object.
            logger: Logger for rendering events.
            state_manager: Session-state manager.
        """
        self._st = streamlit_module
        self._log = logger
        self._state_manager = state_manager

    def render_dietary_toggles(
        self,
        nutrient_specs: List[NutrientSpec],
    ) -> Dict[str, bool]:
        """
        Render top-of-page dietary preference toggles and nutrient bulk actions.

        Args:
            nutrient_specs: Nutrient specifications controlled by the bulk buttons.

        Returns:
            Mapping of dietary preference keys to enabled states.
        """
        self._log.info(
            "Rendering dietary toggles", extra={"event": "ui.dietary.render"}
        )
        safe_markdown(self._st, "<div class='app-surface'>", unsafe_html=True)
        header_columns = self._st.columns(FILTER_HEADER_COLUMNS)
        with header_columns[0]:
            self._st.subheader("Dietary Preferences")
        with header_columns[1]:
            if self._st.button("Remove Constraints"):
                self._state_manager.set_all_any_toggles(nutrient_specs, False)
        with header_columns[2]:
            if self._st.button("Apply All Nutrients"):
                self._state_manager.set_all_any_toggles(nutrient_specs, True)

        preference_columns = self._st.columns([1.0] * len(DIETARY_TOGGLE_LABELS))
        dietary_preferences: Dict[str, bool] = {}

        for column, (preference_key, label) in zip(
            preference_columns, DIETARY_TOGGLE_LABELS
        ):
            with column:
                toggle_key = f"dietary_{preference_key}"
                dietary_preferences[preference_key] = self._st.toggle(
                    label,
                    key=toggle_key,
                    value=False,
                )

        safe_markdown(self._st, "</div>", unsafe_html=True)
        return dietary_preferences

    def render_nutrient_filter(self, spec: NutrientSpec) -> bool:
        """
        Render one nutrient filter row and return invalid-state status.

        Args:
            spec: Nutrient specification.

        Returns:
            True when the filter has an invalid min/max pair.
        """
        self._log.info(
            "Rendering nutrient filter",
            extra={"event": "ui.nutrient.render", "nutrient": spec.key},
        )
        self._state_manager.initialize_nutrient_state(spec)
        row_controls = self._st.columns(FILTER_ROW_COLUMNS)

        with row_controls[0]:
            self._st.markdown(f"**{spec.label}**")

        with row_controls[1]:
            is_requirement_enabled = self._st.toggle(
                "Apply",
                key=self._state_manager.any_key(spec),
                label_visibility="collapsed",
            )

        controls_disabled = not is_requirement_enabled
        self._render_slider(spec, controls_disabled, row_controls[2])
        self._render_min_max_inputs(spec, controls_disabled, row_controls[3:])

        has_invalid_range = self._state_manager.is_invalid_range(spec)
        if has_invalid_range:
            self._st.warning(f"{spec.label}: min must be less than max.")
        return has_invalid_range

    def render_all_nutrients(self, specs: List[NutrientSpec]) -> Dict[str, bool]:
        """
        Render all nutrient filters and return per-filter validity state.

        Args:
            specs: Nutrient specifications.

        Returns:
            Mapping of nutrient key to invalid-range status.
        """
        self._log.info(
            "Rendering all nutrient controls",
            extra={"event": "ui.nutrient.render_all"},
        )
        invalid_ranges: Dict[str, bool] = {}
        for nutrient in specs:
            invalid_ranges[nutrient.key] = self.render_nutrient_filter(nutrient)
        return invalid_ranges

    def _render_min_max_inputs(
        self,
        spec: NutrientSpec,
        controls_disabled: bool,
        input_columns: List[object],
    ) -> None:
        """
        Render min and max numeric controls for a nutrient.

        Args:
            spec: Nutrient specification.
            controls_disabled: Whether nutrient requirements are disabled.
            input_columns: Streamlit columns used for the min and max inputs.
        """
        self._log.info(
            "Rendering nutrient min and max controls",
            extra={"event": "ui.nutrient.min_max", "nutrient": spec.key},
        )
        with input_columns[0]:
            self._st.number_input(
                "Min",
                min_value=spec.bounds[0],
                max_value=spec.bounds[1],
                key=self._state_manager.min_key(spec),
                on_change=self._state_manager.sync_slider_from_inputs,
                args=(spec,),
                disabled=controls_disabled,
            )

        with input_columns[1]:
            self._st.number_input(
                "Max",
                min_value=spec.bounds[0],
                max_value=spec.bounds[1],
                key=self._state_manager.max_key(spec),
                on_change=self._state_manager.sync_slider_from_inputs,
                args=(spec,),
                disabled=controls_disabled,
            )

    def _render_slider(
        self,
        spec: NutrientSpec,
        controls_disabled: bool,
        slider_column: object,
    ) -> None:
        """
        Render range slider for a nutrient.

        Args:
            spec: Nutrient specification.
            controls_disabled: Whether slider should be disabled.
            slider_column: Streamlit column used for the slider.
        """
        self._log.info(
            "Rendering nutrient range slider",
            extra={"event": "ui.nutrient.slider", "nutrient": spec.key},
        )
        with slider_column:
            self._st.slider(
                "Range",
                min_value=spec.bounds[0],
                max_value=spec.bounds[1],
                key=self._state_manager.slider_key(spec),
                on_change=self._state_manager.sync_inputs_from_slider,
                args=(spec,),
                disabled=controls_disabled,
            )
