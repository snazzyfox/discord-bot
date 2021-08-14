# The Party Game Dingomata
A bot that randomly selects users and DM's them a message on Discord. This is intended for more fairly selecting 
players on stream. 

## Getting Started

When creating a bot user on the Discord developer portal, you will need to enable
- Bot permissions: Send Messages, View Channels, Read Message History
- Server members intent: This is required so that the bot can get information about users in your server
- Application commands to register slash commands on your server

You will need 
- Python 3.9+
- [Poetry](https://python-poetry.org/docs/#installation)

To run the app
- `git clone` this repository
- Copy the `.env.template` file to `.env` and fill in values
- `poetry install`
- `poetry run python -m dingomata`

## Cogs in the bot

All commands for the bot are created as slash (application) commands. To view the list of commands available, simply
type a `/` into discord's chat box after the bot has joined your server.

### Game Code Distributor

Randomly pick users to join games. All commands are under `/game` and restricted to mods only.

The typical way it's used:

- A moderator opens the pool with `/game open My Awesome Game`
- The bot responds by posting an announcement *in the same channel*
- Members join the pool by clicking on the provided "join" button
- Member receives a join successful message via DM. **Users whose DM is not open cannot join, because there will be no way to privately send them the game code.** 
- Mod closes the pool with `/game close`.
- Mod issues a command like `/game pick 7 Game code is ABCD`
- The bot DM's the secret message (game code) to selected users, and a public announcement listing the users selected

After that, mods can continue issuing `pick` commands to select more users from the same pool, or they can
clear the pool and start over.

Optionally, the bot keeps track of which users selected in each round, and denies these users from joining after they've
been selected once.

*Note: As of now, pool data is persisted, but recently picked members data is stored in memory. If the bot is restarted,
everyone will become eligible to be picked again.*

### Bedtime

Allows each user to set a time of day and a timezone as their bedtime. If the user talks after their bedtime, the bot 
will remind them to go to bed.

### Text

Fun text commands. May contain surprises and random variations.

### Gamba

A GAMBA bot similar to Twitch's predictions. There are two sets of commands: `/gamba` is for all users and allows them 
to interact with their own points and make bets, while `/gamble` is for admins to manage betting games.

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

## Configuration

There are multiple sources of configurations for the bot. 

- Secrets necessary for the bot to function are placed in the `.env` file in the current working directory. 
  You can also provide values for them directly through environment variables. These values are generally sensitive 
  and should be guarded with care.
- Logging configs control what the bot prints to STDOUT. This is a standard python logging file in config/logging.cfg.
- Server-specific settings affect the behavior of the bot. 
  + `config/server_defaults.yaml` lists default values used for all servers.
  + To override options for a particular server, add a file in `config/servers`. The actual filename doesn't matter, but
    you can only have one file for each server. (If you have more than one, the app will arbitrarily pick one and ignore 
    the rest.) Each of these files follow the same structure as `server_defaults.yaml` except each one must have an
    additional `guild_id` property with the server ID.

See comments in the config files for the meaning of each configuration option.

Because all configs are files at the moment, the bot must be restarted for new config options to take effect.