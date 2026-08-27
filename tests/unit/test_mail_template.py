"""Turning a message into something a mail client will render."""

from app.application.notifications.message import (
    MailAction,
    MailFigure,
    MailMessage,
    MailRow,
)
from app.infrastructure.mail.template import render_html, render_text

MESSAGE = MailMessage(
    greeting="Merhaba Ahmet,",
    paragraphs=("Şifreni sıfırlamak için bir istek aldık.",),
    figure=MailFigure(label="Bu ay", value="2.485,00 TL"),
    rows_title="Kategori özeti",
    rows=(MailRow("Yemek", "1.200,00 TL"),),
    action=MailAction(label="Şifremi sıfırla", url="https://accountant.mail.dev/?reset_token=abc"),
    notice="Bu isteği sen yapmadıysan şifreni değiştir.",
    footnote="Bağlantı 1 saat geçerli.",
)


def test_the_text_part_carries_everything_the_reader_needs() -> None:
    """Sent alongside the markup rather than instead of it: a mail with no text
    part scores worse with spam filters, and some readers show nothing else."""
    text = render_text(MESSAGE)

    assert "Merhaba Ahmet," in text
    assert "Şifreni sıfırlamak için bir istek aldık." in text
    assert "https://accountant.mail.dev/?reset_token=abc" in text
    assert "Yemek: 1.200,00 TL" in text


def test_the_markup_carries_the_link_as_a_button_and_as_text() -> None:
    """Some clients strip the button, and people forward these to a machine
    where the address has to be copied by hand."""
    html = render_html(MESSAGE)

    assert 'href="https://accountant.mail.dev/?reset_token=abc"' in html
    assert html.count("https://accountant.mail.dev/?reset_token=abc") >= 2


def test_a_display_name_cannot_smuggle_markup_into_the_mail() -> None:
    """The greeting is built from a name the account holder chose. Without
    escaping, a name is a way to write markup into everything that account
    causes to be sent."""
    html = render_html(
        MailMessage(greeting="Merhaba <script>alert(1)</script>,")
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_a_link_cannot_break_out_of_its_attribute() -> None:
    html = render_html(
        MailMessage(
            greeting="Merhaba,",
            action=MailAction(label="Aç", url='https://a.dev/?x="><script>'),
        )
    )

    assert '"><script>' not in html


def test_a_message_with_only_a_greeting_still_renders() -> None:
    html = render_html(MailMessage(greeting="Merhaba,"))

    assert html.startswith("<!DOCTYPE html>")
    assert "Merhaba," in html
