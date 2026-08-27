"""Amounts as a Turkish reader expects to see them."""

import pytest

from app.application.notifications.message import format_lira


@pytest.mark.parametrize(
    ("amount_minor", "expected"),
    [
        (0, "0,00 TL"),
        (5, "0,05 TL"),
        (100, "1,00 TL"),
        (248_500, "2.485,00 TL"),
        (1_234_567_89, "1.234.567,89 TL"),
        (-40_000, "-400,00 TL"),
    ],
)
def test_the_separators_are_the_turkish_way_round(
    amount_minor: int,
    expected: str,
) -> None:
    """A dot groups the thousands and a comma opens the kuruş. Python's own
    formatting does exactly the opposite."""
    assert format_lira(amount_minor) == expected
