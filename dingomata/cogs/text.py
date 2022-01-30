import random
import re
from datetime import datetime
from functools import cached_property
from itertools import accumulate
from pathlib import Path
from typing import Dict, List
from zlib import decompress

import discord
import pytz
import yaml
from parsedatetime import Calendar
from pydantic import BaseModel, PrivateAttr, confloat

from ..config import service_config
from ..decorators import slash
from ..exceptions import DingomataUserError
from ..utils import mention_if_needed

_calendar = Calendar()


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
    probability: confloat(gt=0) = 1.0  #: Note: probabilities don't have to add up to 1. They'll be normalized.


class RandomTextChoiceList(BaseModel):
    __root__: List[RandomTextChoice | str]
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


class TextCog(discord.Cog):
    """Text commands."""

    def __init__(self, bot: discord.Bot):
        self._bot = bot

        with (Path(__file__).parent / "text_responses.bin").open("rb") as bindata:
            bindata.seek(2, 0)
            textdata = decompress(bindata.read())
            self._rawtext_replies = [TriggerTextReply.parse_obj(entry) for entry in yaml.safe_load_all(textdata)]

        with (Path(__file__).parent / "random_response_data.yaml").open() as data:
            self._random_replies = {k: RandomTextReply.parse_obj(v) for k, v in yaml.safe_load(data).items()}

    @slash(cooldown=True)
    async def hug(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, "Who to hug"),
    ) -> None:
        """Give someone hugs!"""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} is lonely and can't stop hugging themselves.")
        else:
            await self._post_random_reply(ctx, "hug", target=mention_if_needed(ctx, user))

    @slash(cooldown=True)
    async def pat(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, "Who to pat"),
    ) -> None:
        """Give someone pats!"""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} gives themselves a pat on the back!")
        else:
            await self._post_random_reply(ctx, "pat", target=mention_if_needed(ctx, user))

    @slash(cooldown=True)
    async def bonk(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, "Who to bonk"),
    ) -> None:
        """Give someone bonks!"""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} tries to bonk themselves. They appear to really enjoy it.")
        elif user == self._bot.user:
            await ctx.respond("How dare you.")
        else:
            await self._post_random_reply(ctx, "bonk", target=mention_if_needed(ctx, user))

    @slash(cooldown=True)
    async def bap(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, "Who to bap"),
    ) -> None:
        """Give someone baps!"""
        if ctx.author == user:
            await ctx.respond("Aw, don't be so rough on yourself.")
        elif user == self._bot.user:
            await ctx.respond("How dare you.")
        else:
            await self._post_random_reply(ctx, "bonk", target=mention_if_needed(ctx, user))

    @slash(cooldown=True)
    async def boop(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, "Who to boop"),
    ) -> None:
        """Give someone boops!"""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} walks into a glass door and end up booping themselves.")
        else:
            await self._post_random_reply(ctx, "boop", target=mention_if_needed(ctx, user))

    @slash(
        cooldown=True,
    )
    async def smooch(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, "Who to smooch"),
    ) -> None:
        """Give someone smooches!"""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} tries to smooch themselves... How is that possible?")
        else:
            await self._post_random_reply(ctx, "smooch", target=mention_if_needed(ctx, user),
                                          post="Bzzzt. A shocking experience." if user == self._bot.user else "")

    @slash(cooldown=True)
    async def cuddle(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, "Who to cuddle"),
    ) -> None:
        """Cuddle with someone."""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} can't find anyone to cuddle, so they decided to pull their "
                              f"tail in front and cuddle it instead.")
        else:
            await self._post_random_reply(ctx, "cuddle", target=mention_if_needed(ctx, user))

    @slash(cooldown=True)
    async def snug(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, "Who to snug"),
    ) -> None:
        """Give someone snugs."""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} can't find a hot werewolf boyfriend to snuggle, so they "
                              f"decide to snuggle a daki with themselves on it.")
        else:
            await self._post_random_reply(ctx, "snug", target=mention_if_needed(ctx, user))

    @slash(cooldown=True)
    async def tuck(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, "Who to tuck in"),
    ) -> None:
        """Tuck someone in for the night."""
        if ctx.author == user:
            await ctx.respond(f"{ctx.author.display_name} gets into bed and rolls up into a cozy burrito.")
        else:
            await self._post_random_reply(
                ctx, "tuck", target=mention_if_needed(ctx, user),
                post="The bot overheats and burns their beans." if user == self._bot.user else "")

    @slash(cooldown=True)
    async def tacklehug(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, "Who to tacklehug"),
    ) -> None:
        if user == ctx.author:
            await ctx.respond(f"{ctx.author.display_name} trips over and somehow tackles themselves. Oh wait, they "
                              f"tied both their shoes together.")
        else:
            await self._post_random_reply(
                ctx, "tacklehug", target=mention_if_needed(ctx, user),
                post="The bot lets out some sparks and burns their beans." if user == self._bot.user else "")

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
    async def cute(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, "The cutie"),
    ) -> None:
        """Call someone cute!"""
        if user == self._bot.user:
            await ctx.respond("No U.")
        else:
            await self._post_random_reply(ctx, "cute", target=mention_if_needed(ctx, user))

    @slash(cooldown=True)
    async def roll(
            self,
            ctx: discord.ApplicationContext,
            sides: discord.Option(int, "Number of sides", default=6),
    ) -> None:
        """Roll a die."""
        if sides <= 1:
            await ctx.respond(f"{ctx.author.display_name} tries to roll a {sides}-sided die, but created a black hole "
                              f"instead, because it can't possibly exist. ")
        elif random.random() < 0.01:
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
    async def snipe(
            self,
            ctx: discord.ApplicationContext,
            user: discord.Option(discord.User, "Who to shoot"),
    ) -> None:
        """It's bloody MURDERRRRR"""
        if user == self._bot.user:
            await ctx.respond(f"{ctx.author.display_name} dares to snipe {mention_if_needed(ctx, user)}. "
                              f"The rifle explodes, taking their paws with it.")
        elif user == ctx.author:
            await self._post_random_reply(ctx, "snipe.self")
        else:
            await self._post_random_reply(ctx, "snipe", target=mention_if_needed(ctx, user))

    @slash()
    async def localtime(
            self,
            ctx: discord.ApplicationContext,
            time: discord.Option(str, "A date and/or time, e.g. 2020/01/01 00:00:00"),
            timezone: discord.Option(str, "Time zone you are in"),
    ) -> None:
        """Display a time you enter for everyone as their local time."""
        try:
            tz = pytz.timezone(timezone.strip())
        except pytz.UnknownTimeZoneError as e:
            raise DingomataUserError(
                f'{timezone} is not a recognized timezone. Please use one of the "TZ Database Name"s listed here: '
                f"https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
            ) from e
        time_obj, status = _calendar.parseDT(time, datetime.utcnow().astimezone(tz), tzinfo=tz)
        if status != 3:
            raise DingomataUserError(
                f"Can't interpret {time} as a valid date/time. Try using something like `today 5pm`, or for a "
                f"full date, `2021-12-20 01:05`"
            )
        await ctx.respond(f"{time} in {tz} is <t:{int(time_obj.timestamp())}:f> your local time.")

    @slash()
    async def pour(
            self,
            ctx: discord.ApplicationContext,
            drink: discord.Option(str, "What drink?", choices=["coffee", "tea", "orangina"]),
            user: discord.Option(discord.User, "Who to pour for?"),
    ) -> None:
        mention = "themselves" if user == ctx.author else mention_if_needed(ctx, user)
        if drink == "coffee":
            await self._post_random_reply(ctx, "pour.coffee", target=mention)
        elif drink == "tea":
            await self._post_random_reply(ctx, "pour.tea", target=mention)
        elif drink == "orangina":
            await self._post_random_reply(ctx, "pour.orangina", target=mention)

    @discord.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if (
                message.guild
                and message.guild.id in service_config.get_command_guilds("replies")
                and self._bot.user in message.mentions
                and message.author != self._bot.user
        ):
            for reply in self._rawtext_replies:
                if reply.regex.search(message.content):
                    await message.reply(random.choice(reply.responses))
                    break  # Stop after first match

    async def _post_random_reply(self, ctx: discord.ApplicationContext, key: str, **kwargs) -> None:
        await ctx.respond(self._random_replies[key].render(author=ctx.author.display_name, **kwargs))
