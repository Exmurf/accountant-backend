from uuid import UUID

from app.application.ledger.ports import CategoryRepository
from app.domain.ledger.models import Category, TransactionKind


class ListCategories:
    def __init__(self, categories: CategoryRepository) -> None:
        self._categories = categories

    def execute(
        self,
        user_id: UUID,
        kind: TransactionKind | None = None,
    ) -> list[Category]:
        return self._categories.list_available(user_id, kind)


class CreateCategory:
    def __init__(self, categories: CategoryRepository) -> None:
        self._categories = categories

    def execute(
        self,
        user_id: UUID,
        name: str,
        kind: TransactionKind,
        color: str,
    ) -> Category:
        return self._categories.add(
            user_id=user_id,
            name=name.strip(),
            kind=kind,
            color=color,
        )
