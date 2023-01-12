import logging
from typing import Dict, List

import discord
import tweepy.asynchronous

from ..config import service_config

_log = logging.getLogger(__name__)


class TwitterStream(tweepy.asynchronous.AsyncStreamingClient):
    __slots__ = '_discord_bots', '_computed_rules',

    def __init__(self, bots: List[discord.Bot]):
        if not service_config.twitter_bearer_token:
            _log.warning('TWITTER_BEARER_TOKEN is unset. Twitter integration will not be enabled.')
            return
        token = service_config.twitter_bearer_token.get_secret_value()
        super(TwitterStream, self).__init__(token, wait_on_rate_limit=True)

        self._discord_bots: Dict[int, discord.Bot] = {}
        for bot in bots:
            bot.add_listener(self._register_bot(bot), 'on_ready')

        self._computed_rules = {
            tweepy.StreamRule(rule_config.filter, tag=str(guild_id) + ':' + str(index))
            for guild_id, guild_config in service_config.server.items()
            for index, rule_config in enumerate(guild_config.twitter.rules)
        }

    def _register_bot(self, bot):
        async def on_ready():
            for guild in bot.guilds:
                self._discord_bots[guild.id] = bot

        return on_ready

    async def sync_rules(self):
        response = await self.get_rules()
        existing_rules: List[tweepy.StreamRule] = response.data or []
        # Compare existing rules to computed rules
        # Note: twitter has a limit of 5 rules per app
        rules_to_delete = [
            rule for rule in existing_rules
            if tweepy.StreamRule(value=rule.value, tag=rule.tag) not in self._computed_rules
        ]
        rules_to_add = list(self._computed_rules - {
            tweepy.StreamRule(value=rule.value, tag=rule.tag) for rule in existing_rules
        })
        if rules_to_delete:
            _log.debug(f'Deleting twitter rules: {rules_to_delete}')
            await self.delete_rules(ids=rules_to_delete)
        if rules_to_add:
            _log.debug(f'Adding twitter rules: {rules_to_add}')
            await self.add_rules(rules_to_add)

    async def run(self):
        await self.sync_rules()
        self.filter(expansions=['author_id'])
        _log.info('Twitter stream connected.')

    async def on_response(self, response: tweepy.StreamResponse) -> None:
        tweet: tweepy.Tweet = response.data
        users: List[tweepy.User] = response.includes['users']
        tweet_author = next(user for user in users if user.id == tweet.author_id)
        url = f'https://twitter.com/{tweet_author.username}/status/{tweet.id}'

        # Find out which rules triggered this
        for rule in response.matching_rules:
            guild, index = rule.tag.split(':', 1)
            try:
                discord_rule = service_config.server[int(guild)].twitter.rules[int(index)]
                channel = self._discord_bots[int(guild)].get_channel(discord_rule.channel)
                _log.info(f'Forwarding tweet from {tweet_author} to channel {channel}')
                await channel.send(content=discord_rule.message + '\n' + url)
            except KeyError:
                # server not found - none of the bots running access that server
                pass
