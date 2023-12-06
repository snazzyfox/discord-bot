# Discord Bot
A custom Discord bot with a bunch of random features for various discord servers.

## Getting Started

You will need 
- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation)
- A [postgres](https://postgresql.org) database host

To run the bot
- `git clone` this repository
- `poetry install`
- Copy `.env.template` to `.env` and place your database credentials in it.
- `poetry run python -m snoozybot`

On first start with a fresh database, the bot will create the necessary tables and fail to start (since it's not yet 
configured with the necessary tokens). You will need to manually place discord tokens in the database under the 
`config` table. This is also a good time to add any other config values. You can see the full list of configuration
keys in [the code](snoozybot/config/values.py).

Running the bot in production

- Instead of using a `.env` file, you may also pass database credentials directly as environment variables.
  Most tools you use to manage the bot process (such as `systemd` or if you put it inside a `docker` image) 
  can pass these environment variables in for you.

## Commands in the bot

All commands for the bot are created as slash (application) commands. To view the list of commands available, simply
type a `/` into discord's chat box after the bot has joined your server.

## Developing commands

Commands are added to the bot as hikari extensions under [the commands directory](snoozybot/discord_bot/commands).
