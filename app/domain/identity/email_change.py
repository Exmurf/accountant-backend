from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PendingEmailChange:
    user_id: UUID
    new_email: str
