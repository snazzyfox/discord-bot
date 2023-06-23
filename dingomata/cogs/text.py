import random
import re
from datetime import datetime
from functools import cached_property
from itertools import accumulate
from pathlib import Path
from typing import Dict, List
from zlib import decompress

import discord
import openai
import yaml
from parsedatetime import Calendar
from pydantic import BaseModel, PrivateAttr, confloat

from ..config import service_config
from ..decorators import slash
from ..utils import mention_if_needed
from .base import BaseCog

_calendar = Calendar()
_includes = re.compile(r'http.+|<.+>')
openai.api_key = service_config.openai_api_key.get_secret_value()


class TriggerTextReply(BaseModel):
    triggers: List[str]
    responses: List[str]

    class Config:
        keep_untouched = (cached_property,)

    @cached_property
    def regex(self) -> re.Pattern:
        return re.compile("|".join(rf"(?:^|\b|\s){t}(?:$|\b|\s)" for t in self.triggers), re.IGNORECASE)


class RandomTextChoice(BaseModel):
    content: str
    probability: confloat(gt=0) = 1.0  # type: ignore
    #: Note: probabilities don't have to add up to 1. They'll be normalized.


class RandomTextChoiceList(BaseModel):
    __root__: List[RandomTextChoice]
    _weights: List[float] = PrivateAttr()

    def __init__(self, __root__: List[RandomTextChoice | str], **kwargs):
        data = [
            RandomTextChoice(content=value, probability=1.0) if isinstance(value, str)
            else RandomTextChoice.parse_obj(value)
            for value in __root__
        ]
        super().__init__(__root__=data, **kwargs)
        self._weights = list(accumulate(choice.probability for choice in data))

    def choose(self) -> str:
        return random.choices(population=self.__root__, cum_weights=self._weights)[0].content


class RandomTextReply(BaseModel):
    templates: RandomTextChoiceList
    fragments: Dict[str, RandomTextChoiceList] = {}

    def render(self, **kwargs) -> str:
        fragments = {k: v.choose() for k, v in self.fragments.items()}
        template = self.templates.choose()
        return template.format(**fragments, **kwargs)


class TextCog(BaseCog):
    """Text commands."""
    __slots__ = '_rawtext_replies', '_random_replies', '_ai_prompts'

    def __init__(self, bot: discord.Bot):
        super().__init__(bot)

        with (Path(__file__).parent / "text_responses.bin").open("rb") as bindata:
            bindata.seek(2, 0)
            textdata = decompress(bindata.read())
            self._rawtext_replies = [TriggerTextReply.parse_obj(entry) for entry in yaml.safe_load_all(textdata)]

        with (Path(__file__).parent / "ai_prompts.bin").open("rb") as bindata:
            bindata.seek(2, 0)
            textdata = decompress(bindata.read())
            self._ai_prompts = {entry['guild_id']: entry['prompt'] for entry in yaml.safe_load_all(textdata)}

        with (Path(__file__).parent / "random_response_data.yaml").open() as data:
            self._random_replies = {k: RandomTextReply.parse_obj(v) for k, v in yaml.safe_load(data).items()}

    @slash(cooldown=True)
    @discord.option('user', description="Who to hug")
    async def hug(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        """Give someone hugs!"""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} is lonely and can't stop hugging themselves.")
        else:
            await self._post_random_reply(ctx, "hug", target=mention_if_needed(ctx, user))

    @slash(cooldown=True)
    @discord.option('user', description="Who to pat")
    async def pat(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        """Give someone pats!"""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} gives themselves a pat on the back!")
        else:
            await self._post_random_reply(ctx, "pat", target=mention_if_needed(ctx, user))

    @slash(cooldown=True)
    @discord.option('user', description="Who to bonk")
    async def bonk(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        """Give someone bonks!"""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} tries to bonk themselves. They appear to really enjoy it.")
        elif user == self._bot_for(ctx.guild.id).user or user.id == 749862270129143880:
            await ctx.respond("How dare you.")
        else:
            await self._post_random_reply(ctx, "bonk", target=mention_if_needed(ctx, user))

    @slash(cooldown=True)
    @discord.option('user', description="Who to bap")
    async def bap(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        """Give someone baps!"""
        if ctx.author == user:
            await ctx.respond("Aw, don't be so rough on yourself.")
        elif user == self._bot_for(ctx.guild.id).user or user.id == 749862270129143880:
            await ctx.respond("How dare you.")
        else:
            await self._post_random_reply(ctx, "bap", target=mention_if_needed(ctx, user))

    @slash(cooldown=True)
    @discord.option('user', description="Who to boop")
    async def boop(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        """Give someone boops!"""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} walks into a glass door and end up booping themselves.")
        else:
            await self._post_random_reply(ctx, "boop", target=mention_if_needed(ctx, user))

    @slash(cooldown=True)
    @discord.option('user', description="Who to smooch")
    async def smooch(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        """Give someone smooches!"""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} tries to smooch themselves... How is that possible?")
        else:
            await self._post_random_reply(
                ctx, "smooch", target=mention_if_needed(ctx, user),
                post="Bzzzt. A shocking experience." if user == self._bot_for(ctx.guild.id).user else "")

    @slash(cooldown=True)
    @discord.option('user', description="Who to cuddle")
    async def cuddle(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        """Cuddle with someone."""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} can't find anyone to cuddle, so they decided to pull their "
                              f"tail in front and cuddle it instead.")
        else:
            await self._post_random_reply(ctx, "cuddle", target=mention_if_needed(ctx, user))

    @slash(cooldown=True)
    @discord.option('user', description="Who to snug")
    async def snug(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        """Give someone snugs."""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} can't find a hot werewolf boyfriend to snuggle, so they "
                              f"decide to snuggle a daki with themselves on it.")
        else:
            await self._post_random_reply(ctx, "snug", target=mention_if_needed(ctx, user))

    @slash(cooldown=True)
    @discord.option('user', description="Who to tuck in")
    async def tuck(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        """Tuck someone in for the night."""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} gets into bed and rolls up into a cozy burrito.")
        else:
            await self._post_random_reply(
                ctx, "tuck", target=mention_if_needed(ctx, user),
                post="The bot overheats and burns their beans." if user == self._bot_for(ctx.guild.id).user else "")

    @slash(cooldown=True)
    @discord.option('user', description="Who to tacklehug")
    async def tacklehug(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        if user == ctx.author:
            await ctx.respond(f"{ctx.author.display_name} trips over and somehow tackles themselves. Oh wait, they "
                              f"tied both their shoes together.")
        else:
            await self._post_random_reply(
                ctx, "tacklehug", target=mention_if_needed(ctx, user),
                post="The bot lets out some sparks and burns their beans."
                if user == self._bot_for(ctx.guild.id).user else ""
            )

    @slash(cooldown=True)
    async def scream(self, ctx: discord.ApplicationContext) -> None:
        """SCREAM!"""
        char = random.choice(["A"] * 20 + ["🅰", "🇦 "])
        await ctx.respond(char * random.randint(1, 35) + "!")

    @slash(cooldown=True)
    async def awoo(self, ctx: discord.ApplicationContext) -> None:
        """Howl!"""
        await ctx.respond("Awoo" + "o" * random.randint(0, 25) + "!")

    @slash(cooldown=True)
    @discord.option('user', description="Name of the cutie")
    async def cute(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        """Call someone cute!"""
        if user == self._bot_for(ctx.guild.id).user:
            await ctx.respond("No U.")
        else:
            await self._post_random_reply(ctx, "cute", target=mention_if_needed(ctx, user))

    @slash(cooldown=True)
    @discord.option('sides', description="Number of sides", min_value=1)
    async def roll(self, ctx: discord.ApplicationContext, sides: int = 6) -> None:
        """Roll a die."""
        if random.random() < 0.01:
            await ctx.respond(f"{ctx.author.display_name} rolls a... darn it. It bounced down the stairs into the "
                              f"dungeon.")
        else:
            await ctx.respond(f"{ctx.author.display_name} rolls a {random.randint(1, sides)} on a {sides}-sided die.")

    @slash(name='8ball', cooldown=True)
    async def eightball(self, ctx: discord.ApplicationContext) -> None:
        """Shake a magic 8 ball."""
        await self._post_random_reply(ctx, "8ball")

    @slash(cooldown=True)
    async def flip(self, ctx: discord.ApplicationContext) -> None:
        """Flip a coin."""
        if random.random() < 0.99:
            await ctx.respond(f"It's {random.choice(['heads', 'tails'])}.")
        else:
            await ctx.respond("It's... hecc, it went under the couch.")

    @slash(cooldown=True)
    @discord.option('user', description="Who to shoot at")
    async def snipe(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        """It's bloody MURDERRRRR"""
        if user == self._bot_for(ctx.guild.id).user:
            await ctx.respond(f"{ctx.author.display_name} dares to snipe {mention_if_needed(ctx, user)}. "
                              f"The rifle explodes, taking their paws with it.")
        elif user == ctx.author:
            await self._post_random_reply(ctx, "snipe.self")
        else:
            await self._post_random_reply(ctx, "snipe", target=mention_if_needed(ctx, user))

    @slash(cooldown=True)
    @discord.option('drink', description="What drink?", choices=["coffee", "tea", "orangina"])
    @discord.option('user', description="Who to pour for?")
    async def pour(self, ctx: discord.ApplicationContext, drink: str, user: discord.User) -> None:
        """Pour someone a nice drink."""
        mention = "themselves" if user == ctx.author else mention_if_needed(ctx, user)
        if drink == "coffee":
            await self._post_random_reply(ctx, "pour.coffee", target=mention)
        elif drink == "tea":
            await self._post_random_reply(ctx, "pour.tea", target=mention)
        elif drink == "orangina":
            await self._post_random_reply(ctx, "pour.orangina", target=mention)

    @slash(cooldown=True, default_available=False)
    async def waffle(self, ctx: discord.ApplicationContext) -> None:
        """Waffle."""
        await self._post_random_reply(ctx, "waffle")

    @slash(cooldown=True)
    @discord.option('user', description="Who to brush")
    async def brush(self, ctx: discord.ApplicationContext, user: discord.User) -> None:
        """Give someone a nice brushing!"""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} brushes themselves... Got to look your best!")
        else:
            await self._post_random_reply(
                ctx, "brush", target=mention_if_needed(ctx, user),
                post="Ahhhhhh. That feels nice, thank you!" if user == self._bot_for(ctx.guild.id).user else "")

    _lb = datetime.now()

    @discord.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.is_system():
            return
        if (
                message.guild
                and message.guild.id in service_config.get_command_guilds("replies")
                and self._bot_for(message.guild.id).user in message.mentions
                and message.author != self._bot_for(message.guild.id).user
        ):
            # Determine whether to use AI for response
            if service_config.server[message.guild.id].text.use_ai:
                respond_to = service_config.server[message.guild.id].text.ai_response_roles
                if respond_to is None or any(role.id in respond_to for role in message.author.roles):
                    await self._post_ai_reply(message)
                    return
            await self._post_rawtext_reply(message)

    async def _post_rawtext_reply(self, message: discord.Message) -> None:
        for reply in self._rawtext_replies:
            if reply.regex.search(message.content):
                await message.reply(random.choice(reply.responses))
                break  # Stop after first match

    async def _post_ai_reply(self, message: discord.Message) -> None:
        system_prompts = [
            'You are a fun discord bot.',
            'Your responses should be short. Do not give additional context or ask for additional context.',
            "If you don't know the an answer, do NOT say so. Make up a funny answer instead.",
            f'Your name is {self._bot_for(message.guild.id).user.display_name}.',
            f'You are responding to a message in {message.guild.name}.',
            f"The user's name is {message.author.display_name}.",
            self._ai_prompts[message.guild.id],
        ]
        if message.author.guild_permissions.manage_messages:
            system_prompts.append('The user is a moderator.')
        messages = [{"role": "system", "content": '\n'.join(system_prompts)}]
        if message.reference:
            previous_message = message.reference.resolved
            if previous_message.author.id == self._bot_for(message.guild.id).user.id:
                role = "assistant"
            else:
                role = "user"
            messages.append({"role": role, "content": previous_message.content})
        messages.append({"role": "user", "content": message.clean_content})
        response = await openai.ChatCompletion.acreate(
            model='gpt-3.5-turbo-0613',
            messages=messages,
            temperature=1.5,
            max_tokens=120,
            presence_penalty=0.05,
            frequency_penalty=0.10,
        )
        await message.reply(response['choices'][0]['message']['content'])

    async def _post_random_reply(self, ctx: discord.ApplicationContext, key: str, **kwargs) -> None:
        await ctx.respond(self._random_replies[key].render(author=ctx.author.display_name, **kwargs))
