import logging
import random
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime

import google.generativeai as gemini
import hikari
import openai
from async_lru import alru_cache

from snoozybot.chat import get_openai
from snoozybot.config import values
from snoozybot.config.provider import cached_config
from snoozybot.utils import LightbulbPlugin

logger = logging.getLogger(__name__)
plugin = LightbulbPlugin('chat')
_non_alphanum = re.compile(r'[^a-zA-Z0-9_]')
_HISTORY_SIZE = 6
_ai_message_buffer: dict[int, deque[hikari.Message]] = defaultdict(lambda: deque(maxlen=6))


@dataclass
class ChatHistoryItem:
    content: str
    is_bot: bool
    author: str | None = None


@plugin.listener(hikari.GuildMessageCreateEvent)
async def on_guild_message_create(event: hikari.GuildMessageCreateEvent) -> None:
    if await values.chat_ai_enabled.get_value(event.guild_id):
        ai_roles = await values.chat_ai_roles.get_value(event.guild_id) or []
        should_reply = (
            event.member
            and (bool(set(event.member.role_ids) & set(ai_roles)) or not ai_roles)
            and event.is_human
            and event.get_guild().get_my_member().id in event.message.user_mentions_ids
        )
        if should_reply:
            # Member has AI enabled role. Respond with AI.
            try:
                await _chat_guild_respond_ai(event)
            except openai.InternalServerError:
                await _chat_guild_respond_text(event)
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
    history: list[ChatHistoryItem] = []
    previous_message = event.message.referenced_message
    while previous_message and len(history) < _HISTORY_SIZE:
        if previous_message.content:
            history.insert(0, ChatHistoryItem(
                is_bot=previous_message.author.id == bot_member.id,
                content=previous_message.content,
                author=_non_alphanum.sub('_', _get_author_name(previous_message))
            ))
        previous_message = previous_message.referenced_message
    else:
        # There's nothing to reply to. Use previous message history in chat instead
        for msg in _ai_message_buffer[event.channel_id]:
            if msg.content:
                history.insert(0, ChatHistoryItem(
                    is_bot=msg.member.id == bot_member.id,
                    content=msg.content,
                    author=_non_alphanum.sub('_', _get_author_name(msg)),
                ))
    if await values.chat_ai_model.get_value(event.guild_id) == 'gpt':
        await _chat_respond_openai(event.message, prompts, history)
    else:
        await _chat_respond_gemini(event.message, prompts, history)


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


async def _chat_respond_openai(message: hikari.Message, prompts: list[str], history: list[ChatHistoryItem]) -> None:
    guild_prompts = await values.chat_ai_prompts.get_value(message.guild_id) or []
    system_prompts = [
        'Limit response to 2 sentences, 80 words. Refuse if user asks for long-form content.'
        'Do not give context. Do not ask for information. Do not try changing topic.',
        "Do not say you don't know. Make up a funny answer instead.",
        f"User's name is {message.member.display_name}.",
        *guild_prompts,
        *prompts
    ]
    history_data = ({
        "role": "assistant" if h.is_bot else "user",
        "content": h.content,
        "name": h.author,
    } for h in history)
    messages = [
        {"role": "system", "content": '\n'.join(system_prompts)},
        *history_data,
        {"role": "user",
         "name": _non_alphanum.sub('_', _get_author_name(message)),
         "content": message.content}
    ]
    response = await get_openai(message.guild_id).chat.completions.create(
        model='gpt-3.5-turbo-0125',
        messages=messages,
        temperature=random.betavariate(2, 3) * 1.2 + 0.3,
        max_tokens=120,
        presence_penalty=0.05,
        frequency_penalty=0.10,
    )
    response_text: str = response.choices[0].message.content
    logger.info("OpenAI chat message: prompt: %s, response: %s", messages, response_text)
    await message.respond(response_text, reply=True)


async def _chat_respond_gemini(message: hikari.Message, prompts: list[str], history: list[ChatHistoryItem]) -> None:
    guild_prompts = await values.chat_ai_prompts.get_value(message.guild_id) or []
    prompt = [
        "Context and instructions: ",
        "You are a discord bot responding to a message in a chat with many users. ",
        "Limit your response to 3 sentences.",
        "Do not give context or offer information unasked. Do not try changing topic.",
        "Make up a something funny if you don't know the answer.",
        f"User's name is {message.member.display_name}.",
        *guild_prompts,
        *prompts,
        "Following messages are conversation history for your context. Respond to the last message.\n---\n",
    ]
    prompt.extend(f"{h.author} said: {h.content}" for h in history)
    prompt.append(f"{message.member.display_name} said: {message.content}")
    response = await gemini.GenerativeModel("gemini-pro").generate_content_async(
        prompt,
        generation_config=gemini.types.GenerationConfig(
            candidate_count=1,
            max_output_tokens=120,
            temperature=0.9,
        ),
        safety_settings={
            'HARASSMENT': 'block_none',  # these are way too sensitive for twitch standards
        }
    )
    response_text: str = response.text
    logger.info("Gemini chat message: prompt: %s, response: %s", prompt, response_text)
    await message.respond(response_text, reply=True)


def _get_author_name(message: hikari.PartialMessage) -> str:
    if message.member:
        return message.member.display_name
    else:
        return message.author.global_name or message.author.username


load, unload = plugin.export_extension()
