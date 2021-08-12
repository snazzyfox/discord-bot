# The Party Game Dingomata
A bot that randomly selects users and DM's them a message on Discord. This is intended for more fairly selecting 
players on stream. 

## Getting Started

When creating a bot user on the Discord developer portal, you will need to enable
- Bot permissions: Send Messages, View Channels, Read Message History
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

Randomly pick users to join games.

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

*Note: As of now, pool data is stored in memory. If the bot is restarted, all data will be lost.* 

### Bedtime

Allows each user to set a time of day (in their own timezone) as bedtime. The bot will remind the user to go to bed if
the user posts anything after their bedtime.

### 

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