# The Dingomata
A fun Discord bot for the Dingo Den and various other places.

## Getting Started

When creating a bot user on the Discord developer portal, you will need to enable
- Bot permissions: Send Messages, View Channels, Read Message History
- Server members intent: required so that the bot can get information about users in your server
- Application commands to register slash commands on your server

You will need 
- Python 3.9+
- [Poetry](https://python-poetry.org/docs/#installation)

To run the bot
- `git clone` this repository
- `poetry install`
- Linux (posix): `ENV_FILE={dotenv file} poetry run python -m dingomata` <br/> 
  Windows (powershell): `$env:ENV_FILE="{dotenv file}"; poetry run python -m dingomata`

To configure the bot
- Create a new file under `config/` and add at least one server id and any config overrides
- Copy `.env.template` to a new file and fill in values (or pass them all as environment variables)
- Invite the bot to your server(s)

## Commands in the bot

All commands for the bot are created as slash (application) commands. To view the list of commands available, simply
type a `/` into discord's chat box after the bot has joined your server.

### Game Code Distributor

Randomly pick users to join games. All commands are under `/game` and restricted to mods only.

Typical flow of a game:

- A moderator opens a game. The bot responds with a "game is open" announcement
- Members click on the provided "join" button to join the game, and receive a join successful message via DM. 
  The DM makes sure they can receive DMs later. *Users with DM turned off cannot join, because 
  there will be no way to privately send them the game code.*
- Mod picks players using a command like `/game pick 7 Game code is ABCD`
- The bot DM's the secret message (game code) to selected users, and a public announcement listing the users selected

After that, mods can continue picking more users from the same pool, or they start a new game.

Optionally, the bot keeps track of which users selected in each round, and denies these users from joining after they've
been selected. A mod must manually clear the previous selected user list to make them eligible again.

### Gamba

A GAMBA bot similar to Twitch's predictions feature. There are two sets of commands: `/gamba` is for all users and 
allows them to interact with their own points and make bets, while `/gamble` is for admins to manage betting games.

Users earn server points by either:
- running the `/gamba daily` command to receive a fixed amount of points. This command can be run once every 24 hours.
- being manually given points by a mod

Once users have points, they can participate in bets:
- A mod can start a bet with `/gamble start`
- While the bet is open, users can place bets using either `/gamba believe` or `/gamba doubt`
- After the bet closes, a mod can pay out either option using `/gamba payour`, or cancel it using `/gamba refund`

Users can check their point balance using `/gamba balance`.
Points can't be used for anything right now, but if mods want to allow people to redeem points for anything, they 
can manually deduct points using `/gamble deduct`

### Bedtime

Allows each user to set a time of day and a timezone as their bedtime. If the user talks within a few 
hours (configurable) after their bedtime, the bot will remind them to go to bed.

### Text

Fun text commands. May contain surprises and random variations.

### Quote

Allow mods to add quotes for users in the server and everyone to pick random quotes from other users.

Because all configs are files at the moment, the bot must be restarted for new config options to take effect. This repo 
is configured to automatically upload `main` to the server and restart bots there.