import csv
from datetime import datetime
from io import StringIO
from typing import List, Dict, Literal, Optional
from collections import Counter
import aiohttp
from dateutil.parser import parse
from discord import File
from discord.ext.commands import Bot, Cog
from discord_slash import SlashContext
from discord_slash.cog_ext import cog_subcommand
from discord_slash.utils.manage_commands import create_option
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from dingomata.config import get_guilds, get_mod_permissions
from dingomata.exceptions import DingomataUserError

_BASE_MOD_COMMAND = dict(base='twitch', guild_ids=get_guilds(), base_default_permission=False)


class SubEvent(BaseModel):
    time: datetime
    type: Literal['submysterygift', 'subgift', 'sub', 'resub']
    tier: Literal['Tier 1', 'Tier 2', 'Tier 3', 'Prime']
    user: str
    gift_id: Optional[str]
    count: int


class TwitchCog(Cog, name='Twitch Commands'):
    """Commands relating to twitch."""

    def __init__(self, bot: Bot, engine: AsyncEngine):
        self._bot = bot
        self._engine = engine
        self._session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    @cog_subcommand(
        name='subdata',
        description='Get the list of all subs and gifted subs during a particular stream.',
        options=[
            create_option(name='vod_url', description='Link to a twitch VOD.', option_type=str, required=True),
            create_option(name='download', description='If true, the full sub list will be sent via DM.',
                          option_type=bool, required=False),
        ],
        base_permissions=get_mod_permissions(),
        **_BASE_MOD_COMMAND,
    )
    async def subdata(self, ctx: SlashContext, vod_url: str, download: bool = False) -> None:
        await ctx.defer(hidden=True)
        sub_data = await self._get_sub_data(vod_url)

        total_subs = sum(sub.count for sub in sub_data)
        total_gifts = sum(sub.count for sub in sub_data if sub.type.endswith('gift'))
        tier_counts = Counter()
        gifters = Counter()
        for sub in sub_data:
            tier_counts[sub.tier] += sub.count
            if sub.type in {'submysterygift', 'subgift'}:
                gifters[sub.user] += sub.count

        message = (f'This stream has {total_subs} new subs total, of which {total_gifts} are gifted.\n\n'
                   f'__Sub Tiers__\n'
                   + '\n'.join(f'{k}: {v}' for k, v in tier_counts.items()) + '\n\n'
                   + '__Top Gifters__\n'
                   + '\n'.join(f'{k}: {v} gifteds' for k, v in gifters.most_common(5)) + '\n'
                   )

        if download:
            message += '\nFull sub data will be sent to you via DM momentarily.'
        await ctx.reply(message, hidden=True)
        if download:
            # Write the sub data into a in-memory file
            with StringIO() as buffer:
                writer = csv.DictWriter(buffer, fieldnames=['time', 'type', 'tier', 'user', 'count'],
                                        delimiter='\t', lineterminator='\n')
                writer.writeheader()
                writer.writerows(row.dict() for row in sub_data)
                buffer.seek(0)
                file = File(buffer, filename='twitch_sublist.tsv')
                await ctx.author.send(f"Here's the full sub data for {vod_url}.", file=file)

    @classmethod
    async def _get_sub_data(cls, vod_url: str) -> List[SubEvent]:
        try:
            video_id = int(vod_url.rsplit('/', 1)[1])
        except (IndexError, ValueError):
            raise DingomataUserError(f"That's not a valid VOD URL. It should look something like "
                                     f"`https://www.twitch.tv/videos/1234567890`")
        headers = {'Accept': 'application/vnd.twitchtv.v5+json', 'client-id': "jzkbprff40iqj646a697cyrvl0zt2m6"}
        url = f'https://api.twitch.tv/v5/videos/{video_id}/comments'
        sub_data: List[SubEvent] = []
        async with aiohttp.ClientSession(headers=headers) as session:
            params = {'content_offset_seconds': 0}
            while params:
                async with session.get(url, params=params) as resp:
                    if not resp.ok:
                        raise DingomataUserError(f"Failed to fetch chat logs from Twitch. The video URL may be "
                                                 f"incorrect or chat log is not available for this video.")
                    data = await resp.json()
                    sub_data += cls._parse_sub_messages(data['comments'])
                    if '_next' in data:
                        params = {'cursor': data['_next']}
                    else:
                        params = None

        # Community subs (multi packs) generate both a submysterygift message and many subgift messages. When it's a
        # pack of more than 10 the list of subgifts are incomplete so unusable. Remove all those messages.
        community_sub_ids = {sub.gift_id for sub in sub_data if sub.type == 'submysterygift'}
        sub_data = [sub for sub in sub_data if sub.type != 'subgift' or sub.gift_id not in community_sub_ids]
        return sub_data

    @staticmethod
    def _parse_sub_messages(messages: List[Dict]) -> List[SubEvent]:
        return [SubEvent(
            time=parse(msg['created_at']),
            type=msg['message']['user_notice_params']['msg-id'],
            tier={'1000': 'Tier 1', '2000': 'Tier 2', '3000': 'Tier 3', 'Prime': 'Prime'}[
                msg['message']['user_notice_params']['msg-param-sub-plan']],
            user=msg['commenter']['name'],
            gift_id=msg['message']['user_notice_params'].get('msg-param-origin-id', ''),
            count=int(msg['message']['user_notice_params'].get('msg-param-mass-gift-count', 1)),
        ) for msg in messages
            if msg['message']['user_notice_params']
               and msg['message']['user_notice_params']['msg-id'] in {'submysterygift', 'subgift', 'sub', 'resub'}]
