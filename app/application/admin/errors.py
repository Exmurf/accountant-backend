class AdminUserNotFoundError(Exception):
    pass


class CannotDeactivateSelfError(Exception):
    pass


class CannotRemoveOwnAdminRoleError(Exception):
    pass
