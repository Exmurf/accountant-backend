class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


class PasswordUnchangedError(Exception):
    pass


class InvalidPasswordResetTokenError(Exception):
    pass


class InvalidEmailChangeTokenError(Exception):
    pass


class EmailUnchangedError(Exception):
    pass


class UnreachableEmailError(Exception):
    pass
