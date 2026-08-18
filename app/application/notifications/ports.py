from datetime import datetime
from typing import Protocol
from uuid import UUID


class MailSender(Protocol):
    def send(self, recipient: str, subject: str, text_body: str) -> None: ...


class NotificationDeliveryRepository(Protocol):
    def was_delivered(self, user_id: UUID, kind: str, reference_key: str) -> bool: ...

    def mark_delivered(
        self,
        user_id: UUID,
        kind: str,
        reference_key: str,
        delivered_at: datetime,
    ) -> None: ...
