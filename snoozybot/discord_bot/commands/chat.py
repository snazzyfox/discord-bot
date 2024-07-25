import logging
import random
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime

import google.api_core.exceptions
import google.generativeai as gemini
import hikari
import lightbulb
import openai
from async_lru import alru_cache

from snoozybot.chat import get_openai
from snoozybot.config import values
from snoozybot.config.provider import cached_config
from snoozybot.utils import CooldownManager, LightbulbPlugin

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
    try:
        if await values.chat_ai_enabled.get_value(event.guild_id):
            ai_roles = await values.chat_ai_roles.get_value(event.guild_id) or []
            should_reply = (
                event.member
                and (bool(set(event.member.role_ids) & set(ai_roles)) or not ai_roles)
                and event.is_human
                and event.get_guild().get_my_member().id in event.message.user_mentions_ids
            )
            if should_reply:
                await _check_cooldown(event)
                # Member has AI enabled role. Respond with AI.
                try:
                    await _chat_guild_respond_ai(event)
                except (openai.InternalServerError, google.api_core.exceptions.InternalServerError, ValueError):
                    await _chat_guild_respond_text(event)
            # Always add message to AI message buffer in case it's needed later
            if event.message.content:
                _ai_message_buffer[event.channel_id].append(event.message)
            if should_reply:
                return
        if await values.chat_rb_enabled.get_value(event.guild_id):
            # Messages in AI-enabled guilds but not AI enabled roles also fall thru here
            if event.is_human and event.get_guild().get_my_member().id in event.message.user_mentions_ids:
                await _check_cooldown(event)
                await _chat_guild_respond_text(event)
    except lightbulb.errors.CommandIsOnCooldown:
        message = await values.chat_cooldown_message.get_value(event.guild_id)
        await event.message.respond(message)


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
        model='gpt-4o-mini',
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
    system_prompt = '\n'.join([
        "--- General Information ---",
        "You are a discord bot responding to a message in a chat with many users. ",
        "Respond with just a few sentences. Avoid using line breaks. You may use emojis.",
        "Do not give context or offer information unasked. Do not try changing topic.",
        "Make up a something funny if you don't know the answer.",
        f"The user's name is {message.member.display_name}.",
        '\n --- Information about the current chat you are in ---',
        *guild_prompts,
        *prompts,
        "\n --- Instruction ---",
        "You will be given the conversation history in the next message. ",
        "Respond ONLY to the last message; use the rest as additional conversational context.",
    ])
    chat_history = '\n'.join([
        *(f"{h.author} said: {h.content}" for h in history),
        f"{message.member.display_name} said: {message.content}",
    ])
    prompt = [
        {"role": "user", "parts": system_prompt},
        {"role": "model", "parts": ["Got it. Please provide the conversation history next."]},
        {"role": "user", "parts": chat_history},
    ]
    response = await gemini.GenerativeModel("gemini-pro").generate_content_async(
        prompt,
        generation_config=gemini.types.GenerationConfig(
            candidate_count=1,
            max_output_tokens=300,
            temperature=0.95,
            top_k=12,
            top_p=0.85,
        ),
        safety_settings={
            'HARASSMENT': 'block_none',  # these are way too sensitive for twitch standards
        }
    )
    response_text: str = response.parts[0].text
    logger.info("Gemini chat message: response: %s", response_text)
    await message.respond(response_text, reply=True)


def _get_author_name(message: hikari.PartialMessage) -> str:
    if message.member:
        return message.member.display_name
    else:
        return message.author.global_name or message.author.username


bucket = lightbulb.ChannelBucket(length=300, max_usages=5)
_cooldown_manager = CooldownManager(lambda ctx: bucket)


async def _check_cooldown(event: hikari.GuildMessageCreateEvent):
    await _cooldown_manager.add_cooldown(event)

load, unload = plugin.export_extension()
