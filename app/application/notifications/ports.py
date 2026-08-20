from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.application.notifications.message import MailMessage


class MailSender(Protocol):
    def send(self, recipient: str, subject: str, message: MailMessage) -> None: ...


class NotificationDeliveryRepository(Protocol):
    def was_delivered(self, user_id: UUID, kind: str, reference_key: str) -> bool: ...

    def mark_delivered(
        self,
        user_id: UUID,
        kind: str,
        reference_key: str,
        delivered_at: datetime,
    ) -> None: ...
