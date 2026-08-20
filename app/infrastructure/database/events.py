import logging

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.infrastructure.cache.factory import get_cache
from app.infrastructure.cache.keys import ledger_namespace
from app.infrastructure.database.models.ledger import CategoryModel, TransactionModel

logger = logging.getLogger(__name__)

TOUCHED_LEDGERS = "accountant.touched_ledgers"
TOUCHED_EVERYTHING = "accountant.touched_everything"


@event.listens_for(Session, "before_flush")
def note_pending_changes(session: Session, flush_context, instances) -> None:  # type: ignore[no-untyped-def]
    """Watch what is about to be written, without acting on it yet."""
    touched = session.info.setdefault(TOUCHED_LEDGERS, set())
    for instance in (*session.new, *session.dirty, *session.deleted):
        if isinstance(instance, TransactionModel):
            touched.add(instance.user_id)
        elif isinstance(instance, CategoryModel):
            # A cached transaction carries the name and colour of its category,
            # so renaming one has to reach every entry that quotes it.
            if instance.user_id is None:
                session.info[TOUCHED_EVERYTHING] = True
            else:
                touched.add(instance.user_id)


@event.listens_for(Session, "after_commit")
def publish_changes(session: Session) -> None:
    """Invalidate once the new rows are actually visible to other readers.

    Doing this during the flush would open a window where a concurrent reader
    still sees the old rows, misses the cache, and writes what it read under the
    version that was supposed to replace it — leaving stale data behind the new
    number, which is the one shape of this bug that does not heal.
    """
    touched = session.info.pop(TOUCHED_LEDGERS, set())
    everything = session.info.pop(TOUCHED_EVERYTHING, False)
    if not touched and not everything:
        return

    cache = get_cache()
    if everything:
        cache.invalidate_everything()
        return
    for user_id in touched:
        cache.invalidate(ledger_namespace(user_id))


@event.listens_for(Session, "after_rollback")
@event.listens_for(Session, "after_soft_rollback")
def forget_pending_changes(session: Session, *_: object) -> None:
    """Nothing was written, so nothing needs throwing away."""
    session.info.pop(TOUCHED_LEDGERS, None)
    session.info.pop(TOUCHED_EVERYTHING, None)
