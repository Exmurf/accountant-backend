from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.notifications import (
    NotificationDeliveryModel,
)


class SqlAlchemyNotificationDeliveryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def was_delivered(self, user_id: UUID, kind: str, reference_key: str) -> bool:
        return (
            self._session.scalar(
                select(NotificationDeliveryModel.id).where(
                    NotificationDeliveryModel.user_id == user_id,
                    NotificationDeliveryModel.kind == kind,
                    NotificationDeliveryModel.reference_key == reference_key,
                )
            )
            is not None
        )

    def mark_delivered(
        self,
        user_id: UUID,
        kind: str,
        reference_key: str,
        delivered_at: datetime,
    ) -> None:
        self._session.add(
            NotificationDeliveryModel(
                user_id=user_id,
                kind=kind,
                reference_key=reference_key,
                delivered_at=delivered_at,
            )
        )
        self._session.commit()
