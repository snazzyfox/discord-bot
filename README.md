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
