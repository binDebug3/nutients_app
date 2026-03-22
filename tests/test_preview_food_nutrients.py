"""Unit tests for preview_food_nutrients.py."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def test_load_food_nutrients_raises_for_missing_csv(
    load_backend_module: object,
    tmp_path: Path,
) -> None:
    """Raise FileNotFoundError when the preview input CSV is missing."""
    module = load_backend_module("preview_food_nutrients")

    with pytest.raises(FileNotFoundError):
        module.load_food_nutrients(tmp_path / "missing.csv")


def test_build_output_text_includes_row_count_and_preview(
    load_backend_module: object,
) -> None:
    """Build preview text with row count and a rendered head block."""
    module = load_backend_module("preview_food_nutrients")
    frame = pd.DataFrame({"fdc_id": [1, 2], "food_name": ["Apple", "Pear"]})

    output_text = module.build_output_text(frame)

    assert "Number of rows: 2" in output_text
    assert "First 20 rows:" in output_text
    assert "Apple" in output_text


def test_write_output_writes_expected_text(
    load_backend_module: object,
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    """Write output text with a trailing newline to the target path."""
    module = load_backend_module("preview_food_nutrients")
    output_path = tmp_path / "rows.txt"
    captured: dict[str, str] = {}

    def capture_write_text(self: Path, text: str, encoding: str) -> int:
        """Capture text written by Path.write_text.

        Args:
            self: Output path instance.
            text: Text being written.
            encoding: Output encoding.

        Returns:
            Mocked byte count.
        """
        _ = (self, encoding)
        captured["text"] = text
        return len(text)

    monkeypatch.setattr(Path, "write_text", capture_write_text)

    module.write_output("preview", output_path)

    assert captured["text"] == "preview\n"


def test_main_prints_and_writes_preview(
    load_backend_module: object,
    monkeypatch: object,
) -> None:
    """Run the main workflow and send the built preview to print and file output."""
    module = load_backend_module("preview_food_nutrients")
    frame = pd.DataFrame({"fdc_id": [1], "food_name": ["Apple"]})
    monkeypatch.setattr(module, "load_food_nutrients", lambda _path: frame)

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        module, "write_output", lambda text, path: captured.update({"text": text})
    )
    monkeypatch.setattr(
        "builtins.print", lambda text: captured.update({"printed": text})
    )

    module.main()

    assert captured["printed"] == captured["text"]
