"""Unit tests for neon/init_db.py."""

from __future__ import annotations

import types
from pathlib import Path

import pandas as pd

from conftest import NEON_DIR


def test_init_db_import_reads_secret_and_writes_table(
    load_module: object,
    monkeypatch: object,
) -> None:
    """Import the Neon bootstrap script under mocks and assert its side effects."""
    captured: dict[str, object] = {}
    food_frame = pd.DataFrame({"food_name": ["Apple"]})
    monkeypatch.setattr(Path, "read_text", lambda self, encoding: "postgres://db-url")
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: food_frame)

    def fake_create_engine(url: str) -> str:
        """Capture the engine URL and return a fake engine.

        Args:
            url: Connection string passed by the script.

        Returns:
            Fake engine token.
        """
        captured["url"] = url
        return "engine"

    def fake_to_sql(
        self: pd.DataFrame,
        table_name: str,
        engine: object,
        if_exists: str,
        index: bool,
    ) -> None:
        """Capture to_sql arguments.

        Args:
            self: DataFrame being written.
            table_name: Target table name.
            engine: Engine passed to pandas.
            if_exists: Replace behavior.
            index: Whether to write the index.
        """
        captured["table_name"] = table_name
        captured["engine"] = engine
        captured["if_exists"] = if_exists
        captured["index"] = index
        captured["row_count"] = len(self)

    monkeypatch.setattr(pd.DataFrame, "to_sql", fake_to_sql)
    sqlalchemy_module = types.ModuleType("sqlalchemy")
    sqlalchemy_module.create_engine = fake_create_engine

    module = load_module(
        "test_neon_init_db",
        NEON_DIR / "init_db.py",
        injected_modules={"sqlalchemy": sqlalchemy_module},
    )

    assert module.NEON_URL == "postgres://db-url"
    assert captured == {
        "url": "postgres://db-url",
        "table_name": "food_data",
        "engine": "engine",
        "if_exists": "replace",
        "index": False,
        "row_count": 1,
    }
