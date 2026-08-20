from dataclasses import dataclass


def format_lira(amount_minor: int) -> str:
    """Turkish grouping: 2.485,00 TL, not the 2,485.00 TL Python defaults to."""
    sign = "-" if amount_minor < 0 else ""
    whole, fraction = divmod(abs(amount_minor), 100)
    return f"{sign}{f'{whole:,}'.replace(',', '.')},{fraction:02d} TL"


@dataclass(frozen=True, slots=True)
class MailAction:
    label: str
    url: str


@dataclass(frozen=True, slots=True)
class MailFigure:
    """The one number a message is really about."""

    label: str
    value: str


@dataclass(frozen=True, slots=True)
class MailRow:
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class MailMessage:
    """What a message says, carrying nothing about how it looks.

    Use cases build one of these, and the mail adapter turns it into markup, so
    changing the template never reaches into a business rule and a use case
    never has to know that Outlook still renders with Word.
    """

    greeting: str
    paragraphs: tuple[str, ...] = ()
    figure: MailFigure | None = None
    rows_title: str | None = None
    rows: tuple[MailRow, ...] = ()
    action: MailAction | None = None
    notice: str | None = None
    footnote: str | None = None
