"""Streamlit rendering helpers for nutrient and dietary filter controls."""

from typing import Dict, List

from models import DIETARY_TOGGLE_LABELS, NutrientSpec
from state_manager import NutrientStateManager


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
        header_columns = self._st.columns([0.5, 0.25, 0.25])
        with header_columns[0]:
            self._st.subheader("Dietary Preferences")
        with header_columns[1]:
            if self._st.button("Apply All Nutrients"):
                self._state_manager.set_all_any_toggles(nutrient_specs, True)
        with header_columns[2]:
            if self._st.button("Remove Requirements"):
                self._state_manager.set_all_any_toggles(nutrient_specs, False)

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
        header_controls = self._st.columns([0.56, 0.1, 0.17, 0.17])

        with header_controls[0]:
            self._st.markdown(f"**{spec.label}**")

        with header_controls[1]:
            self._st.toggle(
                "",
                key=self._state_manager.any_key(spec),
                label_visibility="collapsed",
            )
            self._st.write(
                "Any"
                if self._st.session_state[self._state_manager.any_key(spec)]
                else ""
            )

        is_any_enabled = bool(self._st.session_state[self._state_manager.any_key(spec)])
        self._render_min_max_inputs(spec, is_any_enabled, header_controls)
        self._render_slider(spec, is_any_enabled)

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
        is_any_enabled: bool,
        header_controls: List[object],
    ) -> None:
        """
        Render min and max numeric controls for a nutrient.

        Args:
            spec: Nutrient specification.
            is_any_enabled: Whether manual controls are disabled.
            header_controls: Streamlit columns used in the header row.
        """
        self._log.info(
            "Rendering nutrient min and max controls",
            extra={"event": "ui.nutrient.min_max", "nutrient": spec.key},
        )
        with header_controls[2]:
            self._st.number_input(
                "Min",
                min_value=spec.bounds[0],
                max_value=spec.bounds[1],
                key=self._state_manager.min_key(spec),
                on_change=self._state_manager.sync_slider_from_inputs,
                args=(spec,),
                disabled=is_any_enabled,
            )

        with header_controls[3]:
            self._st.number_input(
                "Max",
                min_value=spec.bounds[0],
                max_value=spec.bounds[1],
                key=self._state_manager.max_key(spec),
                on_change=self._state_manager.sync_slider_from_inputs,
                args=(spec,),
                disabled=is_any_enabled,
            )

    def _render_slider(self, spec: NutrientSpec, is_any_enabled: bool) -> None:
        """
        Render range slider for a nutrient.

        Args:
            spec: Nutrient specification.
            is_any_enabled: Whether slider should be disabled.
        """
        self._log.info(
            "Rendering nutrient range slider",
            extra={"event": "ui.nutrient.slider", "nutrient": spec.key},
        )
        self._st.slider(
            "Range",
            min_value=spec.bounds[0],
            max_value=spec.bounds[1],
            key=self._state_manager.slider_key(spec),
            value=spec.defaults,
            on_change=self._state_manager.sync_inputs_from_slider,
            args=(spec,),
            disabled=is_any_enabled,
        )
