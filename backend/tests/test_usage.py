import pytest

pytest.importorskip("fastapi")

from app.services.usage import current_year_month, get_or_create_usage


def test_current_year_month_shape():
    ym = current_year_month()
    assert len(ym) == 7
    assert ym[4] == "-"


def test_get_or_create_usage_symbol_present():
    assert callable(get_or_create_usage)
