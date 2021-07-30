# The Party Game Dingomata
A bot that randomly selects users and DM's them a message on Discord. This is intended for more fairly selecting 
players on stream. 

This bot is intended to be run on the host's machine. It can be hosted or ran by someone else, but it's probably not
necessary. It only works with one discord server at a time.

## Getting Started

Before you run the bot, you'll need 
- A channel where the bot posts messages
- A channel where admins control the bot (this should be hidden from public view, otherwise everyone will be able to 
  see the messages you're DMing winners via the bot)

When creating a bot user on the [Discord developer portal](https://discord.com/developers), you will need to enable
- Bot permissions: Send Messages, View Channels, Read Message History, and Add Reactions (68672)
- Enable server members intent. This is required for the bot to detect removal of reactions.

This bot is intended to be run locally instead of hosted. (Well, you can host it, but it works on one Discord server 
at a time.)

You will need 
- Python 3.9+ 
- [Poetry](https://python-poetry.org/docs/#installation) is the build system of choice.

To run the app
- `git clone` this repository
- `poetry install`
- `poetry run python app.py`

## How it works

The typical way this bot should be used is like this:

- A moderator opens the pool with `+open My Awesome Game`
- The bot posts a message in a channel
- Members join the pool by clicking on the provided reaction. They can leave the pool by un-reacting.
- Member receives a join successful message via DM. **Users whose DM is not open cannot join, because there will be no way to privately send them the game code.** 
- Mod closes the pool with `+close`.
- Mod issues a command like `+pick 8 Game code is ABCD`
- The bot DM's the secret message (game code) to selected users, and a public announcement listing the users selected

After that, mods can continue issuing `+pick` commands to select more and more users from the same pool, or they can
clear the pool and start over.

Optionally, the bot keeps track of which users selected in each round, and denies these users from joining after they've
been selected once.

Everything this bot does is stored in memory. If you close the app, all data will be lost. 

## Command List

All commands in this list requires moderator permissions (controlled by the `manager_roles` config), and are only 
accepted from moderator channels (controlled by `manage_channel` config).

| Command | Description |
| --- | --- |
| `+open <title>` | Opens the pool for entry. The title parameter is text that can be included in the bot's message. |
| `+close` | Closes the currently open pool. |
| `+pick <count> <message>` | Pick <count> users at random from the pool. These users will be removed from the pool after picking. The pool must be closed first. |
| `+resend <message>` | Send a message to everyone who was last picked. |
| `+clear pool` | Clears the current pool |
| `+clear selected` | Clears the history of selected users, making everyone eligible for the next pool. |
| `+list` | Lists all members who in the current pool. This will not actually mention the users to avoid being bonked by moderation bots.
| `+help` | Displays this list. |

## Configuration File Reference

Options in the `disqueue.cfg` configuration file control how the bot runs. If you change these settings, the bot must 
be restarted for them to take effect. See comments in the file for the meaning of each configuration option.

If necessary, you can also set these configurations using environment variables with the format 
`DINGOMATA_{SECTION}_{KEY}`, for example `DINGOMATA_BOT_TOKEN`. Note that environment variables must be all uppercase.
