from enum import Enum


class ConfigKey(str, Enum):
    COOLDOWN__EXEMPT_CHANNELS = 'cooldown.exempt_channels'
    COOLDOWN__TIME_SEC = 'cooldown.time_sec'
    COOLDOWN__INVOCATIONS = 'cooldown.invocations'
    LOGS__ENABLED = 'logs.enabled'
    LOGS__CHANNEL_ID = 'logs.channel_id'
    PROFILE__BIRTHDAY_CHANNEL = 'profile.birthday_channel'
    ROLES__NO_PINGS = 'roles.no_pings'
    ROLES__MOD_ADD = 'roles.mod_add'
    ROLES__MOD_ADD__REMOVE_AFTER_HOURS = 'roles.mod_add.remove_after_hours'  # suffix: role id
    ROLES__MOD_ADD__MIN_MESSAGES = 'roles.mod_add.min_messages'  # suffix: role id
    ROLES__MOD_ADD__MIN_DAYS_IN_GUILD = 'roles.mod_add.min_days_in_guild'  # suffix: role id
    ROLES__MOD_ADD__MIN_DAYS_ACTIVE = 'roles.mod_add.min_days_active'  # suffix: role id

    TEXT__TEMPLATE = 'text.template'  # suffix: command name[.self/.owner]
    TEXT__FRAGMENT = 'text.fragment'  # suffix: command name[.self/.owner].fragment name

    CHAT__RB__ENABLED = 'chat.rb.enabled'
    CHAT__RB__PROMPTS = 'chat.rb.prompts'
    CHAT__AI__ENABLED = 'chat.ai.enabled'
    CHAT__AI__ROLES = 'chat.ai.roles'
    CHAT__AI__PROMPTS = 'chat.ai.prompts'


class SecretConfigKey(str, Enum):
    DISCORD_TOKEN = 'secret.discord.token'  # noqa: S105
    OPENAI_API_KEY = 'secret.openai.apikey'


defaults = {
    ConfigKey.COOLDOWN__EXEMPT_CHANNELS: [],
    ConfigKey.COOLDOWN__INVOCATIONS: 2,
    ConfigKey.COOLDOWN__TIME_SEC: 120,
    ConfigKey.LOGS__ENABLED: False,
    ConfigKey.ROLES__MOD_ADD: [],
    ConfigKey.ROLES__NO_PINGS: [],
    ConfigKey.CHAT__RB__ENABLED: True,
    ConfigKey.CHAT__AI__ENABLED: False,
    ConfigKey.CHAT__AI__ROLES: [],
}
