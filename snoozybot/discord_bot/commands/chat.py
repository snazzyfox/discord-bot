import logging
import random
import re
from collections import defaultdict, deque
from datetime import datetime

import hikari
from async_lru import alru_cache

from snoozybot.chat import chat_client
from snoozybot.config import values
from snoozybot.config.provider import cached_config
from snoozybot.utils import LightbulbPlugin

logger = logging.getLogger(__name__)
plugin = LightbulbPlugin('chat')
_non_alphanum = re.compile(r'[^a-zA-Z0-9_]')
_HISTORY_SIZE = 6
_ai_message_buffer: dict[int, deque[hikari.Message]] = defaultdict(lambda: deque(maxlen=6))


@plugin.listener(hikari.GuildMessageCreateEvent)
async def on_guild_message_create(event: hikari.GuildMessageCreateEvent) -> None:
    if await values.chat_ai_enabled.get_value(event.guild_id):
        ai_roles = await values.chat_ai_roles.get_value(event.guild_id)
        should_reply = ai_roles is None or (
            event.member
            and bool(set(event.member.role_ids) & set(ai_roles))
            and event.is_human and event.get_guild().get_my_member().id in event.message.user_mentions_ids
        )
        if should_reply:
            # Member has AI enabled role. Respond with AI.
            await _chat_guild_respond_ai(event)
        # Always add message to AI message buffer in case it's needed later
        if event.message.content:
            _ai_message_buffer[event.channel_id].append(event.message)
        if should_reply:
            return
    if await values.chat_rb_enabled.get_value(event.guild_id):
        # Messages in AI-enabled guilds but not AI enabled roles also fall thru here
        if event.is_human and event.get_guild().get_my_member().id in event.message.user_mentions_ids:
            await _chat_guild_respond_text(event)


async def _chat_guild_respond_ai(event: hikari.GuildMessageCreateEvent) -> None:
    bot_member = event.get_guild().get_my_member()
    prompts = [
        f'Your name is {bot_member.display_name}.',
        f'The chat is in {event.get_guild().name}.',
        f'The current UTC time is {datetime.now().isoformat()}.',
    ]
    if any(role.permissions & hikari.Permissions.MANAGE_MESSAGES for role in event.member.get_roles()):
        prompts.append('User is moderator.')
    history: list[dict] = []
    previous_message = event.message.referenced_message
    while previous_message and len(history) < _HISTORY_SIZE:
        role = 'assistant' if previous_message.author.id == bot_member.id else 'user'
        history.insert(0, {
            "role": role,
            "content": previous_message.content,
            "name": _non_alphanum.sub('_', _get_author_name(previous_message))
        })
        previous_message = previous_message.referenced_message
    else:
        # There's nothing to reply to. Use previous message history in chat instead
        for msg in _ai_message_buffer[event.channel_id]:
            role = 'assistant' if msg.member.id == bot_member.id else 'user'
            history.insert(0, {
                "role": role,
                "content": msg.content,
                "name": _non_alphanum.sub('_', _get_author_name(msg)),
            })
    await _chat_respond_ai(event.message, prompts, history)


async def _chat_guild_respond_text(event: hikari.GuildMessageCreateEvent):
    prompts = await _chat_get_prompts_text(event.guild_id)
    for pattern, responses in prompts:
        if pattern.search(event.content):
            response = random.choice(responses)
            await event.message.respond(response, reply=True)
            logger.info("Rule-based chat message: %s; Response: %s", event.content, response)
            return


@cached_config
@alru_cache(16)
async def _chat_get_prompts_text(guild_id: int) -> list[tuple[re.Pattern, list[str]]]:
    prompts = await values.chat_rb_prompts.get_value(guild_id) or []
    return [
        (re.compile('|'.join(p['triggers']), re.IGNORECASE), p['responses'])
        for p in prompts
    ]


async def _chat_respond_ai(message: hikari.Message, prompts: list[str], history: list[dict]) -> None:
    guild_prompts = await values.chat_ai_prompts.get_value(message.guild_id) or []
    system_prompts = [
        'Limit response to 2 sentences, 80 words. Refuse if user asks for long-form content.'
        'Do not give context. Do not ask for information. Do not try changing topic.',
        "Do not say you don't know. Make up a funny answer instead.",
        f"User's name is {message.member.display_name}.",
        *guild_prompts,
        *prompts
    ]
    messages = [
        {"role": "system", "content": '\n'.join(system_prompts)},
        *history,
        {"role": "user",
         "name": _non_alphanum.sub('_', _get_author_name(message)),
         "content": message.content}
    ]
    response = await chat_client.chat.completions.create(
        model='gpt-3.5-turbo-0613',
        messages=messages,
        temperature=random.betavariate(2, 3) * 1.2 + 0.3,
        max_tokens=120,
        presence_penalty=0.05,
        frequency_penalty=0.10,
    )
    response_text: str = response.choices[0].message.content
    logger.info("AI chat message: history %s, message: %s, response: %s", history, message.content, response_text)
    await message.respond(response_text, reply=True)


def _get_author_name(message: hikari.PartialMessage) -> str:
    if message.member:
        return message.member.display_name
    else:
        return message.author.global_name or message.author.username


load, unload = plugin.export_extension()
