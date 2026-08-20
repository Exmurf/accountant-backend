from uuid import UUID


def ledger_namespace(user_id: UUID) -> str:
    """Everything cached about one user's money lives under one name.

    Invalidation works at this level rather than per query, because a single
    new transaction changes almost every answer about that user at once and
    working out exactly which ones would cost more than reading them again.
    """
    return f"ledger:{user_id}"
