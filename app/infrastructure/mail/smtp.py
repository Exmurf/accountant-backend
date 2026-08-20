import smtplib
import ssl
from email.message import EmailMessage

from app.application.notifications.message import MailMessage
from app.core.config import Settings
from app.infrastructure.mail.template import render_html, render_text


class SmtpMailSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, recipient: str, subject: str, message: MailMessage) -> None:
        mail = EmailMessage()
        mail["From"] = (
            f"{self._settings.mail_from_name} <{self._settings.mail_username}>"
        )
        mail["To"] = recipient
        mail["Subject"] = subject
        # Text first, then the markup as an alternative: the reader's client
        # picks the richest part it can render, and anything that cannot render
        # markup still has something to show.
        mail.set_content(render_text(message))
        mail.add_alternative(render_html(message), subtype="html")

        context = ssl.create_default_context()
        with smtplib.SMTP(
            self._settings.mail_smtp_host,
            self._settings.mail_smtp_port,
            timeout=20,
        ) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(
                self._settings.mail_username,
                self._settings.mail_app_password,
            )
            smtp.send_message(mail)
