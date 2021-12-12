class DingomataError(Exception):
    """Exceptions raised specifically by the bot."""
    pass


class DingomataUserError(Exception):
    """Exceptions raised by the bot due to user error."""
    pass


class CooldownError(DingomataUserError):
    """Exception raised when command cannot be used during cooldown period."""
    pass
