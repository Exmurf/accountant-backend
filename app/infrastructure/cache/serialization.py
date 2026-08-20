import json
from datetime import date, datetime
from uuid import UUID

from app.domain.ledger.models import AccountBalance, Transaction, TransactionKind


def dump_transactions(transactions: list[Transaction]) -> str:
    return json.dumps([_transaction_to_dict(item) for item in transactions])


def load_transactions(payload: str) -> list[Transaction]:
    return [_transaction_from_dict(item) for item in json.loads(payload)]


def dump_balance(balance: AccountBalance) -> str:
    return json.dumps(
        {
            "total_income_minor": balance.total_income_minor,
            "total_expense_minor": balance.total_expense_minor,
            "opening_balance_minor": balance.opening_balance_minor,
        }
    )


def load_balance(payload: str) -> AccountBalance:
    return AccountBalance(**json.loads(payload))


def _transaction_to_dict(item: Transaction) -> dict:
    return {
        "id": str(item.id),
        "user_id": str(item.user_id),
        "category_id": str(item.category_id),
        "category_name": item.category_name,
        "category_color": item.category_color,
        "kind": item.kind.value,
        "amount_minor": item.amount_minor,
        "description": item.description,
        "occurred_at": item.occurred_at.isoformat(),
        "created_at": item.created_at.isoformat(),
        "subscription_id": (
            None if item.subscription_id is None else str(item.subscription_id)
        ),
        "subscription_charge_date": (
            None
            if item.subscription_charge_date is None
            else item.subscription_charge_date.isoformat()
        ),
    }


def _transaction_from_dict(raw: dict) -> Transaction:
    return Transaction(
        id=UUID(raw["id"]),
        user_id=UUID(raw["user_id"]),
        category_id=UUID(raw["category_id"]),
        category_name=raw["category_name"],
        category_color=raw["category_color"],
        kind=TransactionKind(raw["kind"]),
        amount_minor=raw["amount_minor"],
        description=raw["description"],
        occurred_at=datetime.fromisoformat(raw["occurred_at"]),
        created_at=datetime.fromisoformat(raw["created_at"]),
        subscription_id=(
            None if raw["subscription_id"] is None else UUID(raw["subscription_id"])
        ),
        subscription_charge_date=(
            None
            if raw["subscription_charge_date"] is None
            else date.fromisoformat(raw["subscription_charge_date"])
        ),
    )
