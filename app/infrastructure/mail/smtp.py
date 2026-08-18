import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import Settings


class SmtpMailSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, recipient: str, subject: str, text_body: str) -> None:
        message = EmailMessage()
        message["From"] = (
            f"{self._settings.mail_from_name} <{self._settings.mail_username}>"
        )
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(text_body)

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
            smtp.send_message(message)
