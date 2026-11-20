from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import Money

money = TypeAdapter(Money)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("125.50", "125.50"), ("15", "15.00"), ("0.5", "0.50"), ("0", "0.00")],
)
def test_parses_decimal_strings_to_two_places(raw: str, expected: str) -> None:
    value = money.validate_python(raw)

    assert isinstance(value, Decimal)
    assert str(value) == expected


@pytest.mark.parametrize("raw", ["-0.01", "1.005", "abc", "", None, "NaN", "1" * 17 + ".00"])
def test_rejects_invalid_amounts(raw: object) -> None:
    with pytest.raises(ValidationError):
        money.validate_python(raw)


def test_serialises_as_string_with_two_decimals() -> None:
    assert money.dump_json(Decimal("0")) == b'"0.00"'
    assert money.dump_python(Decimal("125.5"), mode="json") == "125.50"
    assert money.dump_python(Decimal("125.50")) == Decimal("125.50")


def test_arithmetic_stays_exact() -> None:
    assert money.validate_python("0.1") + money.validate_python("0.2") == Decimal("0.30")
