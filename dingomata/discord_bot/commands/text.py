import random
import string

import hikari
import lightbulb

from dingomata.config import values
from dingomata.utils import CooldownManager, LightbulbPlugin, mention_if_needed

plugin = LightbulbPlugin('text')


def text_command_with_target(
    name: str,
    description: str,
    target_description: str
):
    @plugin.command
    @lightbulb.add_cooldown(5, 2, lightbulb.GuildBucket, cls=CooldownManager)
    @lightbulb.option("target", description=target_description, type=hikari.Member)
    @lightbulb.command(name, description=description)
    @lightbulb.implements(lightbulb.SlashCommand)
    async def command(ctx: lightbulb.SlashContext) -> None:
        command_id = name
        message: str | None = None
        if ctx.options.target.id == ctx.author.id:
            message = await _try_generate_message(ctx, command_id + '.self')
        if not message and ctx.options.target.id in ctx.bot.owner_ids:
            message = await _try_generate_message(ctx, command_id + '.owner')
        if not message and ctx.options.target.id == ctx.bot.get_me().id:
            message = await _try_generate_message(ctx, command_id + '.bot')
        if not message:
            message = await _try_generate_message(ctx, command_id)
        await ctx.respond(message)

    return command


async def _try_generate_message(ctx: lightbulb.SlashContext, command_id: str) -> str | None:
    templates = await values.text_template.get_value(ctx.guild_id, command_id)
    if not templates:
        return None
    template = string.Template(_choose_from_options(templates))
    fragments = {
        'author': ctx.member.display_name,
        'target': await mention_if_needed(ctx, ctx.options.target)
    }
    config_fragment_keys = set(template.get_identifiers()) - set(fragments.keys())
    for frag in config_fragment_keys:
        fragment_options = await values.text_fragment.get_value(ctx.guild_id, command_id + '.' + frag)
        if fragment_options:
            fragments[frag] = _choose_from_options(fragment_options)
    message = template.safe_substitute(fragments)
    return message


def _choose_from_options(options: list[str | values.RandomOption]):
    return random.choices(
        population=[o['content'] if isinstance(o, dict) else o for o in options],
        weights=[o['probability'] if isinstance(o, dict) else 1 for o in options],
    )[0]


bap = text_command_with_target("bap", "Give someone baps!", "who to bap")
bonk = text_command_with_target("bonk", "Give someone bonks!", "who to bonk")
boop = text_command_with_target("boop", "Give someone boops!", "who to boop")
brush = text_command_with_target("brush", "Give someone a nice brushing!", "who to brush")
cuddle = text_command_with_target("cuddle", "Give someone cuddles!", "who to cuddle")
cute = text_command_with_target("cute", "Call someone cute!", "who is cute")
hug = text_command_with_target("hug", "Give someone big hugs!", "who to hug")
pat = text_command_with_target("pat", "Give someone pats!", "who to pat")
pour = text_command_with_target("pour", "Grab someone a drink!", "who to pour for")
smooch = text_command_with_target("smooch", "Give someone smooches!", "who to smooch")
snipe = text_command_with_target("snipe", "Try and take a shot!", "who to shoot")
tacklehug = text_command_with_target("tacklehug", "Tacklehug someone!", "who to tackle")
tuck = text_command_with_target("tuck", "Tuck someone in for the night.", "who to tuck in")


@plugin.command
@lightbulb.add_cooldown(5, 2, lightbulb.GuildBucket, cls=CooldownManager)
@lightbulb.command("awoo", description="HOWL!")
@lightbulb.implements(lightbulb.SlashCommand)
async def awoo(ctx: lightbulb.SlashContext) -> None:
    await ctx.respond("Awoo" + "o" * random.randint(0, 25) + "!")


@plugin.command
@lightbulb.add_cooldown(5, 2, lightbulb.GuildBucket, cls=CooldownManager)
@lightbulb.command("flip", description="Flip a coin.")
@lightbulb.implements(lightbulb.SlashCommand)
async def flip(ctx: lightbulb.SlashContext) -> None:
    if random.random() < 0.01:
        await ctx.respond("It's... hecc, it went under the couch.")
    else:
        await ctx.respond(f"It's {random.choice(['heads', 'tails'])}.")


@plugin.command
@lightbulb.add_cooldown(5, 2, lightbulb.GuildBucket, cls=CooldownManager)
@lightbulb.option('sides', description="Number of sides", min_value=1, default=6, type=int)
@lightbulb.command("roll", description="Roll a die.")
@lightbulb.implements(lightbulb.SlashCommand)
async def roll(ctx: lightbulb.SlashContext) -> None:
    if random.random() < 0.01:
        await ctx.respond(f"{ctx.member.display_name} rolls a... darn it. It bounced down the stairs into the "
                          f"dungeon.")
    else:
        await ctx.respond(f"{ctx.member.display_name} rolls a {random.randint(1, ctx.options.sides)} "
                          f"on a {ctx.options.sides}-sided die.")


@plugin.command
@lightbulb.add_cooldown(5, 2, lightbulb.GuildBucket, cls=CooldownManager)
@lightbulb.command("scream", description="SCREM!")
@lightbulb.implements(lightbulb.SlashCommand)
async def scream(ctx: lightbulb.SlashContext) -> None:
    char = random.choice(["A"] * 20 + ["🅰", "🇦 "])
    await ctx.respond(char * random.randint(1, 35) + "!")


load, unload = plugin.export_extension()
