class CategoryNotFoundError(Exception):
    pass


class CategoryKindMismatchError(Exception):
    pass


class CategoryAlreadyExistsError(Exception):
    pass


class SubscriptionNotFoundError(Exception):
    pass


class BudgetNotFoundError(Exception):
    pass


class BudgetAlreadyExistsError(Exception):
    pass
