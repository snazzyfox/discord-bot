import typing

from .provider import ConfigValue


class RandomOption(typing.TypedDict):
    probability: float
    content: str


class RuleBasedPrompt(typing.TypedDict):
    triggers: list[str]
    responses: list[str]


cooldown_exempt_channels = ConfigValue[list[int]]('cooldown.exempt.channels', [])
cooldown_invocations = ConfigValue('cooldown.invocations', 2)
cooldown_time_sec = ConfigValue('cooldown.time_sec', 120)

logs_enabled = ConfigValue('logs.enabled', False)
logs_channel_id = ConfigValue[int]('logs.channel_id')

auto_unarchive_channels = ConfigValue[list[int]]('auto_unarchive.channels')

profile_birthday_channel = ConfigValue[int]('profile.birthday_channel')

roles_no_pings = ConfigValue[list[int]]('roles.no_pings', [])
roles_mod_add = ConfigValue[list[int]]('roles.mod_add', [])
roles_mod_add_remove_after_hours = ConfigValue[int]('roles.mod_add.remove_after_hours', None, True)  # spec: role id
roles_mod_add_min_messages = ConfigValue[int]('roles.mod_add.min_messages', None, True)  # spec: role id
roles_mod_add_min_days_in_guild = ConfigValue[int]('roles.mod_add.min_days_in_guild', None, True)  # spec: role id
roles_mod_add_min_days_active = ConfigValue[int]('roles.mod_add.min_days_active', None, True)  # spec: role id

text_template = ConfigValue[list[str | RandomOption]]('text.template', None, True)  # spec: command name[.self/.owner]
text_fragment = ConfigValue[list[str | RandomOption]]('text.fragment', None,
                                                      True)  # spec: command name[.self/.owner].fragment name

chat_rb_enabled = ConfigValue('chat.rb.enabled', True)
chat_rb_prompts = ConfigValue[list[RuleBasedPrompt]]('chat.rb.prompts', [])
chat_ai_enabled = ConfigValue('chat.ai.enabled', True)
chat_ai_model = ConfigValue[typing.Literal['gpt', 'gemini']]('chat.ai.model', 'gpt')
chat_ai_roles = ConfigValue[list[int]]('chat.ai.roles', [])
chat_ai_prompts = ConfigValue[list[str]]('chat.ai.prompts', [])

twitch_online_notif_enabled = ConfigValue('twitch.online_notif.enabled', False)
twitch_online_notif_channel_id = ConfigValue[int]('twitch.online_notif.channel_id')
twitch_online_notif_logins = ConfigValue[list[str]]('twitch.online_notif.logins')
twitch_online_notif_team = ConfigValue[list[str]]('twitch.online_notif.team')
twitch_online_notif_title_template = ConfigValue[str]('twitch.online_notif.title_template', '$channel is going live!')
twitch_online_notif_image_url = ConfigValue[str]('twitch.online_notif.image_url')  # overrides twitch thumbnails

bsky_post_notif_enabled = ConfigValue('bsky.post_notif.enabled', False)
bsky_post_notif_channel_id = ConfigValue[int]('bsky.post_notif.channel_id')
bsky_post_notif_users = ConfigValue[list[str]]('bsky.post_notif.users')
bsky_post_notif_title_template = ConfigValue[str]('bsky.post_notif.title_template',
                                                  '$display just [posted on bluesky!]($url)')

youtube_notif_enabled = ConfigValue('youtube.notif.enabled', False)
youtube_notif_channel_id = ConfigValue[int]('youtube.notif.channel_id')
youtube_notif_playlist_ids = ConfigValue[list[str]]('youtube.notif.playlist_ids')
youtube_notif_title_template = ConfigValue[str]('youtube.notif.title_template',
                                                '$channel just [uploaded a new YouTube video!]($url)')

report_channel_id = ConfigValue[int]('report.channel_id')
report_message = ConfigValue[str]('report.message', '')
