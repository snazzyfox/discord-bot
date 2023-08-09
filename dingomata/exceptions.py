class UserError(Exception):
    """Exceptions raised by the discord_bot due to user error."""

    pass


class CooldownError(UserError):
    """Exception raised when command cannot be used during cooldown period."""

    pass
