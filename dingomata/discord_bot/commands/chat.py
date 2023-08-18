import logging
import random
import re
from collections import defaultdict, deque
from copy import deepcopy

import hikari
import lightbulb
import openai

from dingomata.config import values
from dingomata.utils import LightbulbPlugin

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
        _ai_message_buffer[event.guild_id].append(event.message)
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
        f'You are responding to a message in {event.get_guild().name}.',
    ]
    if any(role.permissions & hikari.Permissions.MANAGE_MESSAGES for role in event.member.get_roles()):
        prompts.append('The user is a moderator.')
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
        for msg in _ai_message_buffer[event.guild_id]:
            role = 'assistant' if msg.member.id == bot_member.id else 'user'
            history.insert(0, {
                "role": role,
                "content": msg.content,
                "name": _non_alphanum.sub('_', _get_author_name(msg)),
            })
    await _chat_respond_ai(event.message, prompts, history)


async def _chat_guild_respond_text(event: hikari.GuildMessageCreateEvent):
    prompts = await values.chat_rb_prompts.get_value(event.guild_id) or []
    for prompt in prompts:
        if re.search('|'.join(prompt['triggers']), event.content):
            response = random.choice(prompt['responses'])
            await event.message.respond(response, reply=True)
            logger.info("Rule-based chat message: %s; Response: %s", event.content, response)
            return


async def _chat_respond_ai(message: hikari.Message, prompts: list[str], history: list[dict]) -> None:
    guild_prompts = await values.chat_ai_prompts.get_value(message.guild_id) or []
    system_prompts = [
        'Respond with no more than 80 words.'
        'Do not give additional context, ask for additional information, or try to change the topic.',
        "If you don't know the an answer, do NOT say so. Make up a funny answer instead.",
        f"The user's name is {message.member.display_name}.",
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
    response = await openai.ChatCompletion.acreate(
        model='gpt-3.5-turbo-0613',
        messages=messages,
        temperature=random.betavariate(2, 3) * 2,
        max_tokens=120,
        presence_penalty=0.05,
        frequency_penalty=0.10,
    )
    response_text: str = response['choices'][0]['message']['content']
    response_text = response_text.split('<|im_sep|>', 1)[-1]  # remove openai artifacts
    logger.info("AI chat message: history %s, message: %s, response: %s", history, message.content, response_text)
    await message.respond(response_text, reply=True)


def _get_author_name(message: hikari.PartialMessage) -> str:
    if message.member:
        return message.member.display_name
    else:
        return message.author.name


def load(bot: lightbulb.BotApp):
    bot.add_plugin(deepcopy(plugin))


def unload(bot: lightbulb.BotApp):
    bot.remove_plugin(plugin.name)
